import pymupdf

from src.processing.scanned_image import _reading_order

def process_native_page(page: pymupdf.Page) -> dict:
    """
    Extracts text and normalized bounding boxes from a native PDF page.
    """
    width = page.rect.width
    height = page.rect.height
    
    # get_text("words") returns: (x0, y0, x1, y1, "word", block_no, line_no, word_no), positioned
    # on the unrotated page; a page with /Rotate is displayed (and rendered for review) rotated.
    # Lines are found on the unrotated page, where the text runs left to right.
    to_display = page.rotation_matrix
    positioned = []
    for w in page.get_text("words"):
        x0, y0, x1, y1, text = w[:5]
        rect = pymupdf.Rect(x0, y0, x1, y1) * to_display
        # Normalize to 0.0 - 1.0 of the displayed page, clamped
        norm = [
            rect.x0 / width if width else 0.0,
            rect.y0 / height if height else 0.0,
            rect.width / width if width else 0.0,
            rect.height / height if height else 0.0,
        ]
        word = {
            "text": text,
            "confidence": 100.0,  # Native text is considered 100% confident
            "bbox": [max(0.0, min(1.0, v)) for v in norm],
        }
        positioned.append(((y0 + y1) / 2, y1 - y0, x0, word))
    words_data = [word for _, _, _, word in _reading_order(positioned)]

    full_text = page.get_text("text").strip()
    
    return {
        "page_number": page.number + 1,  # 1-indexed
        "width": width,
        "height": height,
        "source_type": "PDF_NATIVE",
        "ocr_used": False,
        "text": full_text,
        "words": words_data
    }
