from pydantic import BaseModel, field_validator
from typing import List, Optional

CLINICAL_EXTRACTION_PROMPT_VERSION = "v1.1"

# The exact field names the validation engine expects. AI prompts must request these
# names verbatim, otherwise every field is reported as MISSING.
CLINICAL_FIELD_SPECS = {
    "patient_name": "Full patient name as printed",
    "date_of_birth": "Patient date of birth, as printed (e.g. 1980-01-15 or 01/15/1980)",
    "patient_id": "Patient / medical record identifier",
    "specimen_type": "Specimen type, e.g. Blood, Serum, Plasma, Urine",
    "collection_date": "Specimen collection date, as printed",
    "received_date": "Date the specimen was received by the lab, as printed",
    "glucose": "Glucose result value (number only; unit in `unit`)",
    "hemoglobin": "Hemoglobin result value (number only; unit in `unit`)",
    "hematocrit": "Hematocrit result value (number only; unit in `unit`)",
    "white_blood_cell_count": "White blood cell (WBC) count value (number only; unit in `unit`)",
    "platelet_count": "Platelet count value (number only; unit in `unit`)",
}

def build_field_instructions() -> str:
    lines = [f'- "{name}": {desc}' for name, desc in CLINICAL_FIELD_SPECS.items()]
    return (
        "Return one entry in `fields` per item below, using the field_name EXACTLY as written:\n"
        + "\n".join(lines)
        + "\nFor each field: `value` is the text exactly as it appears (null if absent), "
        "`unit` is the printed unit or null, `confidence` is your confidence from 0 to 100, "
        "`page_num` is the 1-based page number, and `bbox_normalized` is null unless the "
        "location is known precisely as [x, y, width, height] fractions of the page."
    )

class ExtractedFieldData(BaseModel):
    field_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
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
