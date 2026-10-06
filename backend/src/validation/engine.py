from typing import List, Dict, Any, Tuple, Optional, Iterable
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.validation.rules import validate_date, validate_numeric_and_range, check_date_consistency
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

# States that mean the value itself is unusable and must be corrected before a human can
# approve the document. Every other non-VALID state (OUTSIDE_REFERENCE_RANGE,
# UNRECOGNIZED_UNIT, INCONSISTENT_DATES, SOURCE_MISMATCH) forces human review but can be
# confirmed as-is: an abnormal lab value is a clinical finding, not an extraction error.
BLOCKING_STATES = {"MISSING", "INVALID_FORMAT", "IMPLAUSIBLE_VALUE"}

class ValidationEngine:
    def __init__(self, auto_accept_threshold: float = 0.90):
        self.auto_accept_threshold = auto_accept_threshold

    def validate_field(self, field_name: str, value: str, unit: Optional[str] = None) -> Tuple[str, List[str], Dict[str, Any], str]:
        """
        Validates a single field value, returning state, messages, meta, normalized_value.
        """
        messages = []
        state = "VALID"
        meta = {}
        norm_val = value

        if value is None or value.strip() == "":
            state = "MISSING"
            messages.append("Required field missing")
        else:
            if field_name in DATE_FIELDS:
                st, n_val = validate_date(value)
                norm_val = n_val
                if st == "INVALID_FORMAT":
                    state = st
                    messages.append(f"Invalid date format: {value}")
                elif st == "IMPLAUSIBLE_VALUE":
                    state = st
                    messages.append(f"Date is in the future: {value}")

            elif field_name in NUMERIC_FIELDS:
                st, n_val, m = validate_numeric_and_range(field_name, value, unit)
                norm_val = n_val
                if m:
                    meta = m
                if st != "VALID":
                    state = st
                    if st == "INVALID_FORMAT":
                        messages.append(f"Invalid numeric format: {value}")
                    elif st == "OUTSIDE_REFERENCE_RANGE":
                        messages.append(f"Value {n_val} is outside reference range ({meta.get('lower')} - {meta.get('upper')} {meta.get('canonical_unit', '')})".rstrip() )
                    elif st == "UNRECOGNIZED_UNIT":
                        messages.append(f"Unrecognized unit '{unit}'; expected {meta.get('expected_unit')}")
        return state, messages, meta, norm_val

    def check_cross_field(self, fields: Iterable[Tuple[str, str, Optional[str]]]) -> Dict[str, str]:
        """
        fields: iterable of (field_name, validation_state, normalized_value).
        Returns {field_name: message} for date fields that are individually valid but
        inconsistent with each other.
        """
        dates = {name: norm for name, state, norm in fields if name in DATE_FIELDS and state == "VALID"}
        return check_date_consistency(dates)

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
        for req_field in sorted(MANDATORY_FIELDS):
            if req_field not in extracted_fields_map:
                # Add a MISSING field entry so we track it
                new_field = ExtractedField(
                    extraction_id=extraction.id,
                    field_name=req_field,
                    value=None,
                    confidence=0.0,
                    is_valid=False,
                    is_corrected=False,
                    validation_state="MISSING",
                    validation_messages=["Required field missing"],
                    confidence_category="LOW"
                )
                extraction.extracted_fields.append(new_field)
                extracted_fields_map[req_field] = new_field

        mandatory = [f for f in extraction.extracted_fields if f.field_name in MANDATORY_FIELDS]

        # Pass 1: per-field validation
        for field in mandatory:
            state, messages, meta, norm_val = self.validate_field(field.field_name, field.value, field.unit)

            if document_data and document_data.get("mock_mismatch", {}).get(field.field_name):
                state = "SOURCE_MISMATCH"
                messages.append("Extracted value does not match source text")

            field.normalized_value = norm_val
            field.validation_state = state
            field.validation_messages = messages
            field.validation_metadata = meta

        # Pass 2: cross-field date consistency (only downgrades fields that were VALID)
        inconsistencies = self.check_cross_field((f.field_name, f.validation_state, f.normalized_value) for f in mandatory)
        for field in mandatory:
            if field.field_name in inconsistencies and field.validation_state == "VALID":
                field.validation_state = "INCONSISTENT_DATES"
                field.validation_messages = list(field.validation_messages or []) + [inconsistencies[field.field_name]]

        # Pass 3: confidence and decision
        for field in mandatory:
            state = field.validation_state
            source_mismatch = state == "SOURCE_MISMATCH"

            base_conf = field.confidence if field.confidence is not None else 0.0
            new_conf = calculate_field_confidence(base_conf, state, source_mismatch)
            field.confidence = new_conf # store as 0.0-1.0
            field.confidence_category = categorize_confidence(new_conf)
            field.is_valid = state == "VALID"

            if field.confidence_category == "LOW":
                field.validation_messages = list(field.validation_messages or []) + ["Low confidence extraction"]

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
