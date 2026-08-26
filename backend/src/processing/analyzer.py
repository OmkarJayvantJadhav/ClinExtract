import fitz
from datetime import datetime
from src.processing.native_pdf import process_native_page
from src.processing.scanned_image import process_scanned_page

class DocumentAnalyzer:
    """
    Orchestrates the analysis of a document.
    Determines native PDF text vs Scanned image per page.
    """
    
    @staticmethod
    def process(file_bytes: bytes, mime_type: str, document_id: str, job_id: str) -> dict:
        pages_data = []
        
        if mime_type == "application/pdf":
            # Open PDF from bytes
            doc = fitz.Document(stream=file_bytes, filetype="pdf")
            
            for page in doc:
                text = page.get_text("text").strip()
                
                # Heuristic: if text length > 20 chars, assume it's a native PDF page
                if len(text) > 20:
                    page_data = process_native_page(page)
                else:
                    # Scanned PDF page: render to image
                    # Default PyMuPDF matrix (72 DPI). We can scale up for better OCR.
                    zoom = 2.0  # 144 DPI
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Get image bytes
                    img_bytes = pix.tobytes("png")
                    page_data = process_scanned_page(img_bytes, page.number + 1)
                    
                pages_data.append(page_data)
                
            doc.close()
            
        elif mime_type in ["image/png", "image/jpeg"]:
            # Image file
            page_data = process_scanned_page(file_bytes, 1)
            pages_data.append(page_data)
            
        else:
            raise ValueError(f"Unsupported mime_type: {mime_type}")
            
        # Construct the versioned JSON artifact
        artifact = {
            "schema_version": "1.0",
            "document_id": document_id,
            "processing_job_id": job_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "pages": pages_data
        }
        
        return artifact
