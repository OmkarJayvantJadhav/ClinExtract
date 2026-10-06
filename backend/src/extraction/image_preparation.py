import base64
import fitz  # PyMuPDF
from typing import List, Dict, Any
import filetype

def prepare_page_images(file_bytes: bytes, mime_type: str = None) -> List[Dict[str, Any]]:
    """
    Takes raw document bytes and returns one image per page (raw bytes plus base64).
    Returns [{"page_num": int, "bytes": bytes, "base64": str, "mime_type": str}]
    """
    if mime_type is None:
        kind = filetype.guess(file_bytes)
        mime_type = kind.mime if kind else "application/pdf"
        
    pages = []
    
    if mime_type == "application/pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Zoom to approx 150-200 DPI (72 DPI is default, so 2.0 or 2.5)
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Constraints: ensure it doesn't get ridiculously large
            max_dimension = 2048
            if pix.width > max_dimension or pix.height > max_dimension:
                scale = max_dimension / max(pix.width, pix.height)
                mat = fitz.Matrix(zoom * scale, zoom * scale)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            
            pages.append({
                "page_num": page_num + 1,
                "bytes": img_bytes,
                "base64": b64,
                "mime_type": "image/jpeg"
            })
        doc.close()
    elif mime_type in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        pages.append({
            "page_num": 1,
            "bytes": file_bytes,
            "base64": b64,
            "mime_type": mime_type
        })
    else:
        # Fallback for unsupported types if they reach here, just try PyMuPDF as standard
        try:
            doc = fitz.open(stream=file_bytes)
            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("jpeg")
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                pages.append({
                    "page_num": page_num + 1,
                    "bytes": img_bytes,
                    "base64": b64,
                    "mime_type": "image/jpeg"
                })
            doc.close()
        except Exception:
            pass # Return empty if it completely fails
            
    return pages
