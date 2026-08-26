import cv2
import numpy as np
import pytesseract

def deskew(image: np.ndarray) -> np.ndarray:
    """
    Conservative deskewing using minAreaRect.
    Converts to grayscale, thresholds, and finds the angle of text blocks.
    Only rotates if the angle is between 0.5 and 45 degrees to avoid aggressive/wrong rotations.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Invert the grayscale image so text is white
    gray = cv2.bitwise_not(gray)
    
    # Threshold the image
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Grab the (x, y) coordinates of all pixel values that are greater than zero
    coords = np.column_stack(np.where(thresh > 0))
    
    if len(coords) == 0:
        return image
        
    angle = cv2.minAreaRect(coords)[-1]
    
    # minAreaRect returns values in the range [-90, 0)
    # As the rectangle rotates clockwise, angle goes to 0
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        
    # Only rotate if the skew is meaningful but not extreme
    if 0.5 < abs(angle) < 45.0:
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
    return image

def process_scanned_page(image_bytes: bytes, page_number: int) -> dict:
    """
    Extracts text and normalized bounding boxes from a scanned image using OpenCV and Tesseract.
    """
    # Load image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Could not decode image bytes")
        
    # Preprocessing
    deskewed = deskew(image)
    
    # For OCR, converting to grayscale often helps
    gray = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
    
    # We can also add some light median blur or thresholding if needed, 
    # but Tesseract usually handles grayscale well.
    # We'll stick to a conservative grayscale for now.
    
    height, width = gray.shape[:2]
    
    # Run Tesseract OCR getting data dictionary
    # output includes: level, page_num, block_num, par_num, line_num, word_num, left, top, width, height, conf, text
    ocr_data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    
    words_data = []
    full_text_parts = []
    
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        conf = float(ocr_data['conf'][i])
        
        # Filter out empty text and low confidence (-1 means no confidence value)
        if text and conf > -1:
            x0 = ocr_data['left'][i]
            y0 = ocr_data['top'][i]
            w = ocr_data['width'][i]
            h = ocr_data['height'][i]
            
            # Normalize to 0.0 - 1.0
            norm_x0 = x0 / width if width else 0.0
            norm_y0 = y0 / height if height else 0.0
            norm_w = w / width if width else 0.0
            norm_h = h / height if height else 0.0
            
            norm_x0 = max(0.0, min(1.0, norm_x0))
            norm_y0 = max(0.0, min(1.0, norm_y0))
            norm_w = max(0.0, min(1.0, norm_w))
            norm_h = max(0.0, min(1.0, norm_h))
            
            words_data.append({
                "text": text,
                "confidence": conf,
                "bbox": [norm_x0, norm_y0, norm_w, norm_h]
            })
            full_text_parts.append(text)
            
    full_text = " ".join(full_text_parts)
    
    return {
        "page_number": page_number,
        "width": width,
        "height": height,
        "source_type": "OCR",
        "ocr_used": True,
        "text": full_text,
        "words": words_data
    }
