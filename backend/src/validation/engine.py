from typing import List, Dict, Any, Tuple
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.validation.rules import validate_date, validate_numeric_and_range
from src.validation.confidence import calculate_field_confidence, categorize_confidence

MANDATORY_FIELDS = {
    "patient_name", "date_of_birth", "patient_id", "specimen_type", 
    "collection_date", "received_date", "glucose", "hemoglobin", 
    "hematocrit", "white_blood_cell_count", "platelet_count"
}

NUMERIC_FIELDS = {
    "glucose", "hemoglobin", "hematocrit", "white_blood_cell_count", "platelet_count"
}

DATE_FIELDS = {
    "date_of_birth", "collection_date", "received_date"
}

class ValidationEngine:
    def __init__(self, auto_accept_threshold: float = 0.90):
        self.auto_accept_threshold = auto_accept_threshold

    def validate_field(self, field_name: str, value: str) -> Tuple[str, List[str], Dict[str, Any], str]:
        """
        Validates a single field value, returning state, messages, meta, normalized_value.
        """
        messages = []
        state = "VALID"
        meta = {}
        norm_val = value

        if value is None or value == "":
            state = "MISSING"
            messages.append("Required field missing")
        else:
            if field_name in DATE_FIELDS:
                st, n_val = validate_date(value)
                norm_val = n_val
                if st != "VALID":
                    state = st
                    messages.append(f"Invalid date format: {value}")
                    
            elif field_name in NUMERIC_FIELDS:
                st, n_val, m = validate_numeric_and_range(field_name, value)
                norm_val = n_val
                if m:
                    meta = m
                if st != "VALID":
                    state = st
                    if st == "INVALID_FORMAT":
                        messages.append(f"Invalid numeric format: {value}")
                    elif st == "OUTSIDE_REFERENCE_RANGE":
                        messages.append(f"Value {n_val} is outside reference range ({meta.get('lower')} - {meta.get('upper')})")
        return state, messages, meta, norm_val

    def validate_extraction(self, extraction: Extraction, document_data: Dict[str, Any] = None) -> None:
        """
        Idempotently validates fields on the extraction object.
        Updates extraction and extracted_fields in place.
        """
        extracted_fields_map = {f.field_name: f for f in extraction.extracted_fields}
        
        all_field_confidences = []
        is_auto_accepted = True
        overall_validation_messages = []
        
        # Check all mandatory fields
        for req_field in MANDATORY_FIELDS:
            if req_field not in extracted_fields_map:
                # Add a MISSING field entry so we track it
                new_field = ExtractedField(
                    extraction_id=extraction.id,
                    field_name=req_field,
                    value=None,
                    confidence=0.0,
                    is_valid=False,
                    validation_state="MISSING",
                    validation_messages=["Required field missing"],
                    confidence_category="LOW"
                )
                extraction.extracted_fields.append(new_field)
                extracted_fields_map[req_field] = new_field

        for field in extraction.extracted_fields:
            if field.field_name not in MANDATORY_FIELDS:
                continue

            source_mismatch = False
            if document_data and document_data.get("mock_mismatch", {}).get(field.field_name):
                source_mismatch = True

            # In review correction, current value might not be field.value, but here it's initial extraction
            state, messages, meta, norm_val = self.validate_field(field.field_name, field.value)

            if source_mismatch:
                state = "SOURCE_MISMATCH"
                messages.append("Extracted value does not match source text")

            field.normalized_value = norm_val
            field.validation_state = state
            field.validation_messages = messages
            field.validation_metadata = meta

            # Calculate confidence
            base_conf = field.confidence if field.confidence is not None else 0.0
            new_conf = calculate_field_confidence(base_conf, state, source_mismatch)
            field.confidence = new_conf # store as 0.0-1.0
            field.confidence_category = categorize_confidence(new_conf)

            if field.confidence_category == "LOW":
                messages.append("Low confidence extraction")
                
            all_field_confidences.append(new_conf)

            # Decision Engine Rules
            if state != "VALID":
                is_auto_accepted = False
                overall_validation_messages.append(f"{field.field_name}: {state}")
            if field.confidence_category == "LOW":
                is_auto_accepted = False

        # Overall confidence
        if all_field_confidences:
            extraction.overall_confidence = sum(all_field_confidences) / len(all_field_confidences)
        else:
            extraction.overall_confidence = 0.0

        if extraction.overall_confidence < self.auto_accept_threshold:
            is_auto_accepted = False
            
        extraction.decision = "AUTO_ACCEPTED" if is_auto_accepted else "REVIEW_REQUIRED"
        extraction.validation_status = "VALID" if is_auto_accepted else "INVALID"
        extraction.validation_summary = {"messages": overall_validation_messages}

