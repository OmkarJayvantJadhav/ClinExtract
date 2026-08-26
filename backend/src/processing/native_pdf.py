import fitz

def process_native_page(page: fitz.Page) -> dict:
    """
    Extracts text and normalized bounding boxes from a native PDF page.
    """
    width = page.rect.width
    height = page.rect.height
    
    words_data = []
    
    # get_text("words") returns: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
    words = page.get_text("words")
    for w in words:
        x0, y0, x1, y1, text, block_no, line_no, word_no = w
        
        # Normalize to 0.0 - 1.0
        # Prevent division by zero just in case (though page dimensions shouldn't be 0)
        norm_x0 = x0 / width if width else 0.0
        norm_y0 = y0 / height if height else 0.0
        norm_w = (x1 - x0) / width if width else 0.0
        norm_h = (y1 - y0) / height if height else 0.0
        
        # Clamp to 0-1
        norm_x0 = max(0.0, min(1.0, norm_x0))
        norm_y0 = max(0.0, min(1.0, norm_y0))
        norm_w = max(0.0, min(1.0, norm_w))
        norm_h = max(0.0, min(1.0, norm_h))
        
        words_data.append({
            "text": text,
            "confidence": 100.0,  # Native text is considered 100% confident
            "bbox": [norm_x0, norm_y0, norm_w, norm_h]
        })
        
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
