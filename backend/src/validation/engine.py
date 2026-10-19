from typing import List, Dict, Any, Tuple, Optional, Iterable
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.validation.rules import (
    validate_date, validate_numeric_and_range, check_date_consistency, normalize_sex, normalize_date,
    age_in_years, validate_source_agreement, is_ambiguous_date, date_order, normalize_flag, name_looks_misread,
    document_date_order, UNKNOWN_SEX, normalize_text,
)
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

# Validated when present, but not required (no MISSING entry is created).
OPTIONAL_FIELDS = {"patient_sex"}
VALIDATED_FIELDS = MANDATORY_FIELDS | OPTIONAL_FIELDS

# Fields where a misread matters most: lab results and patient identity. These must be read
# with high confidence (not just "review recommended") for a document to skip review.
CRITICAL_FIELDS = NUMERIC_FIELDS | {"patient_name", "patient_id", "date_of_birth"}

# States that mean the value itself is unusable and must be corrected before a human can
# approve the document. Every other non-VALID state (OUTSIDE_REFERENCE_RANGE,
# UNRECOGNIZED_UNIT, INCONSISTENT_DATES, SOURCE_MISMATCH, EXTREME_VALUE, FLAG_MISMATCH,
# POSSIBLE_MISREAD) forces human review but can be
# confirmed as-is: an abnormal lab value is a clinical finding, not an extraction error.
BLOCKING_STATES = {"MISSING", "INVALID_FORMAT", "IMPLAUSIBLE_VALUE"}

# Abnormal-but-plausible results are clinical findings, not doubts about the extraction. They
# stay flagged on the field, but only hold the document for review when the review policy asks
# for it (review_abnormal_results). EXTREME_VALUE is not in this set: it always goes to review.
ABNORMAL_STATES = {"OUTSIDE_REFERENCE_RANGE"}

class ValidationEngine:
    def __init__(self, auto_accept_threshold: float = 0.90, review_recommended: float = 0.90, low_confidence: float = 0.70,
                 review_abnormal_results: bool = False):
        self.auto_accept_threshold = auto_accept_threshold
        self.high_threshold = review_recommended
        self.low_threshold = low_confidence
        self.auto_acceptable_states = {"VALID"} if review_abnormal_results else {"VALID"} | ABNORMAL_STATES

    @classmethod
    def from_thresholds(cls, thresholds: dict, review_policy: Optional[dict] = None) -> "ValidationEngine":
        return cls(
            auto_accept_threshold=thresholds["auto_accept"],
            review_recommended=thresholds["review_recommended"],
            low_confidence=thresholds["low_confidence"],
            review_abnormal_results=bool((review_policy or {}).get("review_abnormal_results", False)),
        )

    @staticmethod
    def build_context(values: Dict[str, Optional[str]], printed: Optional[Dict[str, Optional[str]]] = None) -> Dict[str, Any]:
        """
        Document context: the order its day/month dates are read in (taken from any of its dates
        that can only be read one way, else the configured DATE_ORDER), and the patient's sex and
        age at collection, used to pick reference ranges. `printed` are the values as read from the
        page: when a reviewer's correction (e.g. a date retyped as 1985-05-25) removes the date that
        fixed the order, the page's own dates still decide it, so the other dates are not re-read.
        """
        order = (
            document_date_order(values.get(name) for name in sorted(DATE_FIELDS))
            or document_date_order((printed or {}).get(name) for name in sorted(DATE_FIELDS))
            or date_order()
        )
        collected = normalize_date(values.get("collection_date") or "", order) if values.get("collection_date") else None
        return {
            "sex": normalize_sex(values.get("patient_sex")),
            "age": age_in_years(values.get("date_of_birth"), collected, order),
            "date_order": order,
        }

    def validate_field(self, field_name: str, value: str, unit: Optional[str] = None, context: Optional[Dict[str, Any]] = None,
                       printed_range: Optional[str] = None, printed_flag: Optional[str] = None) -> Tuple[str, List[str], Dict[str, Any], str]:
        """
        Validates a single field value, returning state, messages, meta, normalized_value.
        `context` ({"sex", "age"}) selects sex/age-appropriate reference ranges; the report's own
        printed range and abnormal flag, when extracted, take precedence over them.
        """
        context = context or {}
        messages = []
        state = "VALID"
        meta = {}
        norm_val = value

        if (value is None or value.strip() == "") and field_name in OPTIONAL_FIELDS:
            return "VALID", messages, meta, None
        if value is None or value.strip() == "":
            state = "MISSING"
            messages.append("Required field missing")
        else:
            if field_name in DATE_FIELDS:
                order = context.get("date_order") or date_order()
                st, n_val = validate_date(value, order=order)
                norm_val = n_val
                if st == "INVALID_FORMAT":
                    state = st
                    messages.append(f"Invalid date format: {value}")
                elif st == "IMPLAUSIBLE_VALUE":
                    state = st
                    messages.append(f"Date is in the future: {value}")
                if n_val and is_ambiguous_date(value):
                    # Valid either way round: record how it was read so a reviewer can check it
                    meta = {"ambiguous_date": True, "read_as": "day first" if order == "DMY" else "month first"}

            elif field_name == "patient_sex":
                norm_val = normalize_sex(value)
                if norm_val is None and normalize_text(value).lower() not in UNKNOWN_SEX:
                    state = "INVALID_FORMAT"
                    messages.append(f"Unrecognized sex value: {value}")

            elif field_name in NUMERIC_FIELDS:
                st, n_val, m = validate_numeric_and_range(
                    field_name, value, unit, context.get("sex"), context.get("age"), printed_range, printed_flag
                )
                norm_val = n_val
                if m:
                    meta = m
                if st != "VALID":
                    state = st
                    if st == "INVALID_FORMAT":
                        messages.append(f"Invalid numeric format: {value}")
                    elif st == "OUTSIDE_REFERENCE_RANGE":
                        messages.append(self._abnormal_message(n_val, meta))
                    elif st == "EXTREME_VALUE" and meta.get("reason") == "far_outside_range":
                        messages.append(
                            f"Value {n_val} is far outside the reference range ({meta.get('lower')} - {meta.get('upper')}); "
                            "check for a misread digit or decimal point"
                        )
                    elif st == "EXTREME_VALUE":
                        messages.append(
                            f"Value {n_val} {meta.get('canonical_unit', '')} is outside any plausible result "
                            f"({meta.get('plausible_lower')} - {meta.get('plausible_upper')}); "
                            "check for a misread digit or decimal point"
                        )
                    elif st == "UNRECOGNIZED_UNIT" and not unit:
                        messages.append(f"No unit printed with the result; expected {meta.get('expected_unit')}")
                    elif st == "UNRECOGNIZED_UNIT":
                        messages.append(f"Unrecognized unit '{unit}'; expected {meta.get('expected_unit')}")
                    elif st == "NO_REFERENCE_RANGE":
                        messages.append(f"Adult reference ranges do not apply (age {context.get('age')}); verify against the report's own range")
        return state, messages, meta, norm_val

    @staticmethod
    def _abnormal_message(value: Optional[str], meta: Dict[str, Any]) -> str:
        unit = meta.get("canonical_unit", "")
        lower, upper = meta.get("lower"), meta.get("upper")
        outside = (lower is not None and float(value) < lower) or (upper is not None and float(value) > upper)
        if meta.get("printed_flag") and not outside:
            word = "high" if meta["printed_flag"] == "H" else "low"
            return f"Value {value} {unit} is flagged {word} on the report".replace("  ", " ")
        if meta.get("range_basis") == "report":
            return f"Value {value} {unit} is outside the report's reference range ({meta['printed_range']})".replace("  ", " ")
        return f"Value {value} is outside the {meta.get('range_basis', 'adult')} reference range ({lower} - {upper} {unit})".rstrip()

    @staticmethod
    def _flag_mismatch(field: ExtractedField) -> Optional[str]:
        meta = field.validation_metadata or {}
        if field.field_name not in NUMERIC_FIELDS or field.validation_state not in ("VALID", "OUTSIDE_REFERENCE_RANGE"):
            return None
        printed = normalize_flag(field.abnormal_flag)
        words = {"H": "high", "L": "low", None: "normal"}
        if meta.get("range_basis") == "report":
            actual = meta.get("printed_direction")
            if printed == actual:
                return None
            range_text = meta.get("printed_range")
        else:
            # Against a built-in range only an opposite flag is a contradiction: the lab's own
            # range may differ, so a flag on a value that looks normal here is not.
            actual = meta.get("direction")
            if not printed or not actual or printed == actual:
                return None
            range_text = f"{meta.get('range_basis')} range {meta.get('lower')} - {meta.get('upper')}"
        return (
            f"The report marks this result {words[printed]}, but the value read ({field.normalized_value}) is "
            f"{words[actual]} for its range ({range_text}); check for a misread digit or decimal point"
        )

    @staticmethod
    def _read_by_ocr(field: ExtractedField, document_data: Optional[Dict[str, Any]]) -> bool:
        pages = (document_data or {}).get("pages") or []
        page = next((p for p in pages if p.get("page_number") == field.page_num), None)
        return bool(page and page.get("ocr_used"))

    @staticmethod
    def _found_in_source(field: ExtractedField, document_data: Optional[Dict[str, Any]]) -> bool:
        """
        Checks the value against the OCR/native text of the field's page (all pages when the
        page is unknown). Without page text (e.g. review re-validation) the check is skipped.
        """
        pages = (document_data or {}).get("pages") or []
        if not pages or not field.value:
            return True
        relevant = [p for p in pages if field.page_num and p.get("page_number") == field.page_num] or pages
        text = " ".join(
            " ".join(w.get("text", "") for w in p.get("words", [])) or p.get("text", "") for p in relevant
        )
        if not text.strip():
            return True
        return validate_source_agreement(field.value, text, field.field_name)

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

        mandatory = [f for f in extraction.extracted_fields if f.field_name in VALIDATED_FIELDS]
        values = {}
        for f in extraction.extracted_fields:
            values.setdefault(f.field_name, f.value)
        context = self.build_context(values)

        # Pass 1: per-field validation
        for field in mandatory:
            state, messages, meta, norm_val = self.validate_field(
                field.field_name, field.value, field.unit, context, field.reference_range, field.abnormal_flag
            )

            if document_data and document_data.get("mock_mismatch", {}).get(field.field_name):
                state = "SOURCE_MISMATCH"
                messages.append("Extracted value does not match source text")
            elif state != "MISSING" and not self._found_in_source(field, document_data):
                state = "SOURCE_MISMATCH"
                messages.append("Extracted value was not found in the document text")
            elif (field.field_name == "patient_name" and state == "VALID"
                  and self._read_by_ocr(field, document_data) and name_looks_misread(field.value)):
                state = "POSSIBLE_MISREAD"
                messages.append("The name looks misread by OCR (e.g. a lowercase l for a capital I); check it against the document")

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

        # Pass 2b: on reports that print H/L flags, the flag must agree with the value we read.
        # A disagreement usually means a misread digit or decimal point.
        if any(f.abnormal_flag for f in mandatory if f.field_name in NUMERIC_FIELDS):
            for field in mandatory:
                message = self._flag_mismatch(field)
                if message:
                    field.validation_state = "FLAG_MISMATCH"
                    field.validation_messages = [message]

        # Pass 3: confidence and decision
        for field in mandatory:
            state = field.validation_state
            source_mismatch = state == "SOURCE_MISMATCH"

            base_conf = field.confidence if field.confidence is not None else 0.0
            new_conf = calculate_field_confidence(base_conf, state, source_mismatch)
            field.confidence = new_conf # store as 0.0-1.0
            field.confidence_category = categorize_confidence(new_conf, self.high_threshold, self.low_threshold)
            field.is_valid = state == "VALID"

            if field.confidence_category == "LOW":
                field.validation_messages = list(field.validation_messages or []) + ["Low confidence extraction"]

            all_field_confidences.append(new_conf)

            # Decision Engine Rules
            if state != "VALID":
                overall_validation_messages.append(f"{field.field_name}: {state}")
            if state not in self.auto_acceptable_states:
                is_auto_accepted = False
            if field.confidence_category == "LOW":
                is_auto_accepted = False
            if field.field_name in CRITICAL_FIELDS and field.confidence_category != "HIGH":
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
