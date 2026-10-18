import fitz
from datetime import datetime, timezone
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

def _image_regions(page: fitz.Page) -> list:
    """Page areas covered by embedded images large enough to hold text worth reading."""
    page_rect = page.rect
    page_area = page_rect.width * page_rect.height
    regions = []
    for info in page.get_image_info():
        rect = fitz.Rect(info["bbox"]) & page_rect
        if rect.is_empty or not page_area:
            continue
        if rect.width * rect.height / page_area < MIN_OCR_IMAGE_FRACTION:
            continue
        if any(rect in seen for seen in regions):
            continue  # the same image drawn twice, or one nested in another
        regions.append(rect)
    return regions

def _add_image_region_ocr(page: fitz.Page, page_data: dict) -> None:
    """
    OCRs the large images on a native-text page and appends their words to `page_data`, with
    bounding boxes in the page's frame. Words that sit on top of native text (e.g. a text layer
    over the image) are skipped so nothing is read twice.
    """
    regions = _image_regions(page)
    if not regions:
        return

    page_w, page_h = page.rect.width, page.rect.height
    native_boxes = [w["bbox"] for w in page_data["words"]]

    def overlaps_native(cx: float, cy: float) -> bool:
        return any(x <= cx <= x + w and y <= cy <= y + h for x, y, w, h in native_boxes)

    zoom = OCR_RENDER_DPI / 72.0
    added = []
    deskewed = False
    for clip in regions:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        try:
            ocr = process_scanned_page(pix.tobytes("png"), page.number + 1)
        except ValueError as e:
            # The native text is still usable; don't fail the document over one image.
            logger.warning(f"Skipping OCR of an image region on page {page.number + 1}: {e}")
            continue
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
                doc = fitz.Document(stream=file_bytes, filetype="pdf")
            except Exception as e:
                raise DocumentProcessingError(f"Could not open PDF: {e}") from e

            try:
                if doc.needs_pass:
                    raise DocumentProcessingError("PDF is password protected")
                if doc.page_count > settings.MAX_DOCUMENT_PAGES:
                    raise DocumentProcessingError(
                        f"PDF has {doc.page_count} pages; the maximum is {settings.MAX_DOCUMENT_PAGES}"
                    )

                for page in doc:
                    text = page.get_text("text").strip()

                    if len(text) > MIN_NATIVE_TEXT_CHARS:
                        page_data = process_native_page(page)
                        _add_image_region_ocr(page, page_data)
                    else:
                        # Scanned PDF page: render to image at OCR resolution
                        zoom = OCR_RENDER_DPI / 72.0
                        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                        page_data = process_scanned_page(pix.tobytes("png"), page.number + 1)

                    pages_data.append(page_data)
            finally:
                doc.close()

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
