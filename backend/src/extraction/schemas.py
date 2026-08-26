from pydantic import BaseModel, field_validator
from typing import List, Optional

CLINICAL_EXTRACTION_PROMPT_VERSION = "v1.0"

class ExtractedFieldData(BaseModel):
    field_name: str
    value: Optional[str] = None
    confidence: Optional[float] = None
    page_num: Optional[int] = None
    bbox_normalized: Optional[List[float]] = None

    @field_validator('bbox_normalized')
    def validate_bbox(cls, v):
        if v is None:
            return v
        if not isinstance(v, list) or len(v) != 4:
            raise ValueError("Bounding box must be a list of 4 floats [x, y, w, h]")
        for coord in v:
            if not isinstance(coord, (int, float)) or coord < 0.0 or coord > 1.0:
                raise ValueError("Bounding box coordinates must be between 0.0 and 1.0")
        return [float(c) for c in v]

class ExtractionResult(BaseModel):
    extractor_type: str
    model_version: Optional[str] = None
    provider: str
    prompt_version: Optional[str] = None
    fallback_metadata: Optional[dict] = None
    fields: List[ExtractedFieldData]
