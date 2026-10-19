import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pymupdf
from src.core.config import settings
from src.processing.native_pdf import process_native_page
from src.processing.scanned_image import process_scanned_page
from src.core.logging import get_logger

logger = get_logger(__name__)

# Tesseract is tuned for ~300 DPI input; PDF user space is 72 DPI.
OCR_RENDER_DPI = 300
# Pages with less native text than this are treated as scanned and OCR'd in full.
MIN_NATIVE_TEXT_CHARS = 20
# On a text page, embedded images covering at least this share of the page are OCR'd too:
# lab results are often a scanned or pasted picture under a typed header. Smaller images
# (logos, signatures) are skipped.
MIN_OCR_IMAGE_FRACTION = 0.05

class DocumentProcessingError(ValueError):
    """The document itself cannot be processed (corrupt, encrypted, too large). Retrying will not help."""

def _image_regions(page: pymupdf.Page) -> list:
    """Page areas covered by embedded images large enough to hold text worth reading."""
    page_rect = page.rect
    page_area = page_rect.width * page_rect.height
    regions = []
    for info in page.get_image_info():
        rect = pymupdf.Rect(info["bbox"]) & page_rect
        if rect.is_empty or not page_area:
            continue
        if rect.width * rect.height / page_area < MIN_OCR_IMAGE_FRACTION:
            continue
        if any(rect in seen for seen in regions):
            continue  # the same image drawn twice, or one nested in another
        regions.append(rect)
    return regions

def _render_image_regions(page: pymupdf.Page) -> list:
    """(clip rect, PNG) for each large image on a native-text page, rendered for OCR."""
    zoom = OCR_RENDER_DPI / 72.0
    return [
        (clip, page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False).tobytes("png"))
        for clip in _image_regions(page)
    ]

def _merge_region_words(page_data: dict, page_w: float, page_h: float, regions: list) -> None:
    """
    Appends the OCR'd words of a native-text page's large images (`regions`: (clip rect, OCR
    result)) with bounding boxes in the page's frame. Words that sit on top of native text
    (e.g. a text layer over the image) are skipped so nothing is read twice.
    """
    native_boxes = [w["bbox"] for w in page_data["words"]]

    def overlaps_native(cx: float, cy: float) -> bool:
        return any(x <= cx <= x + w and y <= cy <= y + h for x, y, w, h in native_boxes)

    added = []
    deskewed = False
    for clip, ocr in regions:
        deskewed = deskewed or ocr.get("deskew_applied", False)
        for word in ocr["words"]:
            # Region-relative fractions -> page-relative fractions
            rx, ry, rw, rh = word["bbox"]
            x = (clip.x0 + rx * clip.width) / page_w
            y = (clip.y0 + ry * clip.height) / page_h
            w = rw * clip.width / page_w
            h = rh * clip.height / page_h
            if overlaps_native(x + w / 2, y + h / 2):
                continue
            added.append({"text": word["text"], "confidence": word["confidence"], "bbox": [x, y, w, h]})

    if added:
        page_data["words"].extend(added)
        page_data["text"] = (page_data["text"] + "\n" + " ".join(w["text"] for w in added)).strip()
        page_data["source_type"] = "MIXED"
        page_data["ocr_used"] = True
        page_data["deskew_applied"] = deskewed

def _ocr_workers() -> int:
    return settings.OCR_WORKERS if settings.OCR_WORKERS > 0 else min(4, os.cpu_count() or 1)

def _run_ocr(tasks: list) -> list:
    """
    OCRs (png, page_number) tasks in parallel, returning results in order (a ValueError for
    an undecodable image is returned in place of its result). Tesseract runs as a separate
    process per call, so threads give real parallelism (each Tesseract uses one OpenMP thread,
    see scanned_image: 8 pages on 4 CPUs took 22 s this way and over 9 minutes without it).
    """
    def one(task):
        png, page_number = task
        try:
            return process_scanned_page(png, page_number)
        except ValueError as e:
            return e

    workers = min(_ocr_workers(), len(tasks))
    if workers <= 1:
        return [one(t) for t in tasks]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, tasks))

class DocumentAnalyzer:
    """
    Orchestrates the analysis of a document.
    Determines native PDF text vs Scanned image per page.
    """

    @staticmethod
    def process(file_bytes: bytes, mime_type: str, document_id: str, job_id: str) -> dict:
        pages_data = []

        if mime_type == "application/pdf":
            try:
                doc = pymupdf.Document(stream=file_bytes, filetype="pdf")
            except Exception as e:
                raise DocumentProcessingError(f"Could not open PDF: {e}") from e

            try:
                if doc.needs_pass:
                    raise DocumentProcessingError("PDF is password protected")
                if doc.page_count > settings.MAX_DOCUMENT_PAGES:
                    raise DocumentProcessingError(
                        f"PDF has {doc.page_count} pages; the maximum is {settings.MAX_DOCUMENT_PAGES}"
                    )

                # 1. Read native text and render whatever needs OCR (PyMuPDF is not thread-safe)
                plans, tasks = [], []
                for page in doc:
                    number = page.number + 1
                    if len(page.get_text("text").strip()) > MIN_NATIVE_TEXT_CHARS:
                        regions = _render_image_regions(page)
                        plans.append(("native", process_native_page(page), page.rect, [
                            (clip, len(tasks) + i) for i, (clip, _) in enumerate(regions)
                        ]))
                        tasks += [(png, number) for _, png in regions]
                    else:
                        # Scanned PDF page: render to image at OCR resolution
                        zoom = OCR_RENDER_DPI / 72.0
                        plans.append(("scanned", None, None, len(tasks)))
                        tasks.append((page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png"), number))
            finally:
                doc.close()

            # 2. OCR every rendered page and image region in parallel
            results = _run_ocr(tasks)

            # 3. Assemble the pages in order
            for kind, page_data, rect, ref in plans:
                if kind == "scanned":
                    if isinstance(results[ref], ValueError):
                        raise DocumentProcessingError(str(results[ref])) from results[ref]
                    page_data = results[ref]
                else:
                    regions = []
                    for clip, index in ref:
                        if isinstance(results[index], ValueError):
                            # The native text is still usable; don't fail the document over one image.
                            logger.warning(f"Skipping OCR of an image region on page {page_data['page_number']}: {results[index]}")
                        else:
                            regions.append((clip, results[index]))
                    _merge_region_words(page_data, rect.width, rect.height, regions)
                pages_data.append(page_data)

        elif mime_type in ["image/png", "image/jpeg"]:
            try:
                pages_data.append(process_scanned_page(file_bytes, 1))
            except ValueError as e:
                raise DocumentProcessingError(str(e)) from e

        else:
            raise DocumentProcessingError(f"Unsupported mime_type: {mime_type}")

        # Construct the versioned JSON artifact
        artifact = {
            "schema_version": "1.0",
            "document_id": document_id,
            "processing_job_id": job_id,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "pages": pages_data
        }

        return artifact
