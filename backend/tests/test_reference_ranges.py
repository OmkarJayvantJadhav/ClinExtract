"""The report's own reference ranges and abnormal flags: extraction and validation."""
import uuid

import pytest

from src.db.models.extracted_field import ExtractedField
from src.db.models.extraction import Extraction
from src.extraction.rule_based import RuleBasedExtractor
from src.validation.engine import ValidationEngine
from src.validation.rules import parse_printed_range, validate_numeric_and_range


def _extract(text):
    words = [{"text": w, "confidence": 99.0, "bbox": [0, 0, 0.01, 0.01]} for w in text.split()]
    result = RuleBasedExtractor().extract({"pages": [{"page_number": 1, "words": words}]})
    return {f.field_name: f for f in result.fields}


@pytest.mark.parametrize("text, field, expected", [
    ("Glucose, Fasting 182 H mg/dL 70 - 100", "glucose", ("182", "mg/dL", "H", "70 - 100")),
    ("Hemoglobin: 10.9 g/dL L (12.0-15.5)", "hemoglobin", ("10.9", "g/dL", "L", "12.0-15.5")),
    ("Hematocrit 0.39 L/L 0.36 - 0.46", "hematocrit", ("0.39", "L/L", None, "0.36 - 0.46")),
    ("Platelet Count 265 x10^3/uL 150 - 450", "platelet_count", ("265", "x10^3/uL", None, "150 - 450")),
    ("Glucose 92 mg/dL <100", "glucose", ("92", "mg/dL", None, "<100")),
    ("WBC 13.2 HIGH K/uL 4.5 to 11.0", "white_blood_cell_count", ("13.2", "K/uL", "HIGH", "4.5 to 11.0")),
])
def test_printed_range_and_flag_are_captured(text, field, expected):
    f = _extract(text)[field]
    assert (f.value, f.unit, f.abnormal_flag, f.reference_range) == expected


def test_no_range_when_none_is_printed():
    fields = _extract("Glucose 92 mg/dL Hemoglobin 14.1 g/dL")
    assert fields["glucose"].reference_range is None and fields["glucose"].abnormal_flag is None
    assert fields["hemoglobin"].value == "14.1"


def test_parse_printed_range():
    assert parse_printed_range("70 - 100") == (70.0, 100.0)
    assert parse_printed_range("(4.5 to 11.0)") == (4.5, 11.0)
    assert parse_printed_range("150,000-450,000") == (150000.0, 450000.0)
    assert parse_printed_range("<200") == (None, 200.0)
    assert parse_printed_range(">= 60") == (60.0, None)
    assert parse_printed_range("see note") is None


def test_printed_range_overrides_built_in_range():
    # 110 mg/dL is above the built-in fasting range but normal for this report's random glucose range
    assert validate_numeric_and_range("glucose", "110", "mg/dL", printed_range="70 - 140")[0] == "VALID"
    state, _, meta = validate_numeric_and_range("glucose", "95", "mg/dL", printed_range="70 - 90")
    assert state == "OUTSIDE_REFERENCE_RANGE" and meta["range_basis"] == "report"


def test_printed_range_is_converted_with_the_value():
    # 6.1 mmol/L = 109.9 mg/dL, above the printed 3.9 - 5.5 mmol/L (70.3 - 99.1 mg/dL)
    state, norm, meta = validate_numeric_and_range("glucose", "6.1", "mmol/L", printed_range="3.9 - 5.5")
    assert state == "OUTSIDE_REFERENCE_RANGE" and meta["upper"] == pytest.approx(99.088)
    # Raw cell counts are scaled down together with their range
    assert validate_numeric_and_range("platelet_count", "250000", None, printed_range="150000 - 450000")[0] == "VALID"


def test_printed_flag_marks_value_abnormal():
    state, _, meta = validate_numeric_and_range("hemoglobin", "13.6", "g/dL", printed_range="13.5 - 17.5", printed_flag="L")
    assert state == "OUTSIDE_REFERENCE_RANGE" and meta["printed_flag"] == "L"
    assert validate_numeric_and_range("hemoglobin", "14.0", "g/dL", printed_flag="?")[0] == "VALID"


def test_children_use_the_printed_range():
    # No built-in pediatric ranges, but the report's own range applies
    assert validate_numeric_and_range("hemoglobin", "12.5", "g/dL", age=8, printed_range="11.5 - 15.5")[0] == "VALID"
    assert validate_numeric_and_range("hemoglobin", "12.5", "g/dL", age=8)[0] == "NO_REFERENCE_RANGE"


def test_engine_uses_printed_range_and_explains_it():
    values = {
        "patient_name": "A B", "date_of_birth": "2016-04-12", "patient_id": "P-1", "specimen_type": "Blood",
        "collection_date": "2026-10-01", "received_date": "2026-10-02", "glucose": "92",
        "hemoglobin": "10.1", "hematocrit": "38", "white_blood_cell_count": "7.5", "platelet_count": "250",
    }
    ranges = {"glucose": "70 - 100", "hemoglobin": "11.5 - 15.5", "hematocrit": "35 - 45",
              "white_blood_cell_count": "4.5 - 13.5", "platelet_count": "150 - 450"}
    e = Extraction(id=uuid.uuid4(), model_version="t", provider="t", prompt_version="t")
    e.extracted_fields = [
        ExtractedField(field_name=k, value=v, confidence=100.0, reference_range=ranges.get(k)) for k, v in values.items()
    ]
    ValidationEngine().validate_extraction(e)
    fields = {f.field_name: f for f in e.extracted_fields}

    # A 10-year-old: every result is checked against the report's ranges, none routed to review for lack of one
    assert fields["glucose"].validation_state == "VALID"
    assert fields["hemoglobin"].validation_state == "OUTSIDE_REFERENCE_RANGE"
    assert fields["hemoglobin"].validation_messages[0] == "Value 10.1 g/dL is outside the report's reference range (11.5 - 15.5)"
    assert e.decision == "AUTO_ACCEPTED"


def _engine_fields(rows, **extra):
    """rows: field -> (value, unit, printed range, flag)"""
    values = {"patient_name": "A B", "date_of_birth": "1980-04-12", "patient_id": "P-1", "specimen_type": "Blood",
              "collection_date": "2026-10-01", "received_date": "2026-10-02", **extra}
    e = Extraction(id=uuid.uuid4(), model_version="t", provider="t", prompt_version="t")
    e.extracted_fields = [ExtractedField(field_name=k, value=v, confidence=100.0) for k, v in values.items()] + [
        ExtractedField(field_name=k, value=v, unit=u, reference_range=r, abnormal_flag=fl, confidence=100.0)
        for k, (v, u, r, fl) in rows.items()
    ]
    ValidationEngine().validate_extraction(e)
    return e, {f.field_name: f for f in e.extracted_fields}

NORMAL_ROWS = {
    "glucose": ("92", "mg/dL", "70 - 100", None), "hemoglobin": ("14.8", "g/dL", "13.5 - 17.5", None),
    "hematocrit": ("44.1", "%", "41 - 50", None), "white_blood_cell_count": ("7.2", "K/uL", "4.5 - 11.0", None),
    "platelet_count": ("265", "K/uL", "150 - 450", None),
}


def test_decimal_misread_far_outside_range_goes_to_review():
    e, f = _engine_fields({**NORMAL_ROWS, "white_blood_cell_count": ("73", "K/uL", "4.5 - 11.0", None)})
    assert f["white_blood_cell_count"].validation_state == "EXTREME_VALUE"
    assert "decimal point" in f["white_blood_cell_count"].validation_messages[0]
    assert e.decision == "REVIEW_REQUIRED"


def test_flag_mismatch_on_reports_that_print_flags():
    # The report flags glucose high, so it uses flags; WBC 13.0 reads high but is not flagged
    rows = {**NORMAL_ROWS, "glucose": ("182", "mg/dL", "70 - 100", "H"),
            "white_blood_cell_count": ("13.0", "K/uL", "4.5 - 11.0", None)}
    e, f = _engine_fields(rows)
    assert f["glucose"].validation_state == "OUTSIDE_REFERENCE_RANGE"  # flag agrees
    assert f["white_blood_cell_count"].validation_state == "FLAG_MISMATCH"
    assert "marks this result normal" in f["white_blood_cell_count"].validation_messages[0]
    assert e.decision == "REVIEW_REQUIRED"

    # Flagged low, but the value read is normal
    _, f = _engine_fields({**NORMAL_ROWS, "hemoglobin": ("14.0", "g/dL", "13.5 - 17.5", "L")})
    assert f["hemoglobin"].validation_state == "FLAG_MISMATCH"


def test_no_flag_check_on_reports_without_flags():
    e, f = _engine_fields({**NORMAL_ROWS, "glucose": ("120", "mg/dL", "70 - 100", None)})
    assert f["glucose"].validation_state == "OUTSIDE_REFERENCE_RANGE"
    assert e.decision == "AUTO_ACCEPTED"
