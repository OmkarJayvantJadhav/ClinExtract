import fitz
from datetime import datetime, timezone
from src.core.config import settings
from src.processing.native_pdf import process_native_page
from src.processing.scanned_image import process_scanned_page

# Tesseract is tuned for ~300 DPI input; PDF user space is 72 DPI.
OCR_RENDER_DPI = 300

class DocumentProcessingError(ValueError):
    """The document itself cannot be processed (corrupt, encrypted, too large). Retrying will not help."""

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

                    # Heuristic: if text length > 20 chars, assume it's a native PDF page
                    if len(text) > 20:
                        page_data = process_native_page(page)
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
