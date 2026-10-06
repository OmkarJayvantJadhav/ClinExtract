import io
import cv2
import numpy as np
import pytesseract
from typing import Optional, Tuple
from PIL import Image

# Refuse to decode images larger than this many pixels (decompression-bomb protection).
MAX_IMAGE_PIXELS = 60_000_000

def estimate_skew_angle(image: np.ndarray) -> float:
    """
    Returns the rotation (degrees, OpenCV convention: positive = counter-clockwise)
    that straightens the text in `image`. Works with both the pre-4.5 [-90, 0) and the
    newer (0, 90] minAreaRect angle conventions by folding the angle into (-45, 45].
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Invert so text is white, then threshold
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    # findNonZero yields (x, y) points, which is what minAreaRect expects
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return 0.0

    angle = cv2.minAreaRect(coords)[-1]
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90
    return float(angle)

def deskew(image: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Conservative deskewing. Only rotates when the skew is meaningful (> 0.5 degrees).
    Returns (image, M) where M is the 2x3 affine matrix that was applied, or None.
    """
    angle = estimate_skew_angle(image)
    if 0.5 < abs(angle) < 45.0:
        (h, w) = image.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated, M
    return image, None

def _box_to_original(x0: float, y0: float, w: float, h: float, inv_M: Optional[np.ndarray]) -> Tuple[float, float, float, float]:
    """Maps a box from deskewed-image pixels back to original-image pixels (axis-aligned bounds)."""
    if inv_M is None:
        return x0, y0, w, h
    corners = np.array([[x0, y0], [x0 + w, y0], [x0, y0 + h], [x0 + w, y0 + h]], dtype=np.float64)
    mapped = cv2.transform(corners.reshape(-1, 1, 2), inv_M).reshape(-1, 2)
    min_x, min_y = mapped.min(axis=0)
    max_x, max_y = mapped.max(axis=0)
    return float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y)

def _check_image_size(image_bytes: bytes) -> None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as probe:
            width, height = probe.size
    except Exception:
        # Let OpenCV report undecodable data below
        return
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"Image too large to process ({width}x{height} pixels)")

def process_scanned_page(image_bytes: bytes, page_number: int) -> dict:
    """
    Extracts text and normalized bounding boxes from a scanned image using OpenCV and Tesseract.
    Bounding boxes are expressed relative to the ORIGINAL image so they line up with what
    the reviewer sees, even when the page was deskewed for OCR.
    """
    _check_image_size(image_bytes)

    # Load image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image bytes")

    # Preprocessing
    deskewed, M = deskew(image)
    inv_M = cv2.invertAffineTransform(M) if M is not None else None

    # Tesseract handles grayscale well; keep preprocessing conservative.
    gray = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)

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

        # Filter out empty text and boxes without a confidence value (-1)
        if text and conf > -1:
            x0, y0, w, h = _box_to_original(
                ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i], inv_M
            )

            # Normalize to 0.0 - 1.0 and clamp
            norm_x0 = max(0.0, min(1.0, x0 / width if width else 0.0))
            norm_y0 = max(0.0, min(1.0, y0 / height if height else 0.0))
            norm_w = max(0.0, min(1.0 - norm_x0, w / width if width else 0.0))
            norm_h = max(0.0, min(1.0 - norm_y0, h / height if height else 0.0))

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
        "deskew_applied": M is not None,
        "text": full_text,
        "words": words_data
    }
