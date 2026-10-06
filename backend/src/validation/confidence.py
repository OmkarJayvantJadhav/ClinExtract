
def calculate_field_confidence(
    source_confidence: float, 
    validation_state: str, 
    source_mismatch: bool = False
) -> float:
    """
    field_confidence = source_confidence * extraction_quality * validation_factor * source_agreement
    """
    # Normalize source_confidence from 0-100 to 0.0-1.0
    if source_confidence > 1.0:
        src_conf = source_confidence / 100.0
    else:
        src_conf = source_confidence

    extraction_quality = 1.0 # For rule-based, if it matched, it's 1.0
    
    validation_factor = 1.0
    if validation_state in ["INVALID_FORMAT", "MISSING", "IMPLAUSIBLE_VALUE"]:
        validation_factor = 0.5
    elif validation_state == "OUTSIDE_REFERENCE_RANGE":
        # Out of range doesn't mean low confidence in the extraction itself, but it implies abnormality
        # The prompt says: "Do not treat an abnormal clinical value as a malformed value... 
        # The important point is that the confidence score should be explainable, not a collection of arbitrary penalties."
        # We will keep validation_factor = 1.0 for out of range.
        validation_factor = 1.0

    source_agreement = 0.5 if source_mismatch else 1.0
    
    final_conf = src_conf * extraction_quality * validation_factor * source_agreement
    return round(min(max(final_conf, 0.0), 1.0), 4)

def categorize_confidence(conf: float, high_threshold: float = 0.90, low_threshold: float = 0.70) -> str:
    if conf >= high_threshold:
        return "HIGH"
    if conf >= low_threshold:
        return "REVIEW_RECOMMENDED"
    return "LOW"
