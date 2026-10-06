import uuid
from datetime import date, timedelta

import cv2
import numpy as np
import pytest

from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.extraction.rule_based import RuleBasedExtractor
from src.processing.scanned_image import estimate_skew_angle, deskew, _box_to_original
from src.validation.engine import ValidationEngine, BLOCKING_STATES
from src.validation.rules import validate_numeric_and_range, validate_date, normalize_numeric


# --- numeric / unit handling -------------------------------------------------

def test_glucose_mmol_is_converted_before_range_check():
    state, norm, meta = validate_numeric_and_range("glucose", "5.0", "mmol/L")
    assert state == "VALID"
    assert norm == "90.08"
    assert meta["original_unit"] == "mmol/L"

def test_hemoglobin_g_per_l_is_converted():
    state, norm, _ = validate_numeric_and_range("hemoglobin", "145", "g/L")
    assert state == "VALID"
    assert norm == "14.5"

def test_unknown_unit_is_flagged_not_range_checked():
    state, _, meta = validate_numeric_and_range("glucose", "90", "furlongs")
    assert state == "UNRECOGNIZED_UNIT"
    assert meta["expected_unit"] == "mg/dL"

def test_thousands_separator_and_raw_count_scaling():
    assert normalize_numeric("250,000") == 250000.0
    state, norm, meta = validate_numeric_and_range("platelet_count", "250,000")
    assert state == "VALID"
    assert norm == "250"
    assert meta["assumed_unit"] == "cells/uL"

def test_low_platelets_still_out_of_range_after_scaling():
    state, _, _ = validate_numeric_and_range("platelet_count", "90,000")
    assert state == "OUTSIDE_REFERENCE_RANGE"


# --- dates -------------------------------------------------------------------

def test_us_and_day_first_dates():
    assert validate_date("04/12/1998") == ("VALID", "1998-04-12")
    # Day > 12 cannot be MM/DD, so it is read as DD/MM
    assert validate_date("25/12/1998") == ("VALID", "1998-12-25")

def test_future_date_is_implausible():
    future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    state, _ = validate_date(future)
    assert state == "IMPLAUSIBLE_VALUE"
    assert state in BLOCKING_STATES


def _extraction(**overrides):
    values = {
        "patient_name": "Aarav Mehta", "date_of_birth": "1998-04-12", "patient_id": "P-1",
        "specimen_type": "Blood", "collection_date": "2023-10-01", "received_date": "2023-10-02",
        "glucose": "90", "hemoglobin": "14.5", "hematocrit": "42", "white_blood_cell_count": "7.5",
        "platelet_count": "250",
    }
    values.update(overrides)
    e = Extraction(id=uuid.uuid4(), model_version="t", provider="t", prompt_version="t")
    e.extracted_fields = [ExtractedField(field_name=k, value=v, confidence=100.0) for k, v in values.items()]
    return e

def test_received_before_collection_is_inconsistent():
    e = _extraction(received_date="2023-09-30")
    ValidationEngine().validate_extraction(e)
    received = next(f for f in e.extracted_fields if f.field_name == "received_date")
    assert received.validation_state == "INCONSISTENT_DATES"
    assert e.decision == "REVIEW_REQUIRED"

def test_out_of_range_is_not_a_blocking_state():
    # Abnormal results force review but must remain approvable as-is
    assert "OUTSIDE_REFERENCE_RANGE" not in BLOCKING_STATES
    assert {"MISSING", "INVALID_FORMAT"} <= BLOCKING_STATES


# --- rule-based extractor ----------------------------------------------------

def _page(text):
    return {"pages": [{"page_number": 1, "words": [
        {"text": t, "bbox": [0.01 * i, 0.1, 0.01, 0.02], "confidence": 100.0} for i, t in enumerate(text.split())
    ]}]}

def test_rule_based_captures_units_and_hyphenated_names():
    result = RuleBasedExtractor().extract(_page("Patient Name: Mary-Jane O'Brien DOB: 1990-01-01 Glucose: 5.4 mmol/L Platelet Count: 250,000 /uL"))
    fields = {f.field_name: f for f in result.fields}
    assert fields["patient_name"].value == "Mary-Jane O'Brien"
    assert fields["glucose"].value == "5.4"
    assert fields["glucose"].unit == "mmol/L"
    assert fields["platelet_count"].value == "250,000"
    assert fields["platelet_count"].unit == "/uL"

def test_rule_based_does_not_duplicate_fields_across_pages():
    page = _page("Glucose: 90 mg/dL")["pages"][0]
    doc = {"pages": [page, {**page, "page_number": 2}]}
    result = RuleBasedExtractor().extract(doc)
    assert [f.page_num for f in result.fields if f.field_name == "glucose"] == [1]


# --- OCR geometry ------------------------------------------------------------

def _text_image(angle):
    img = np.ones((1200, 1000, 3), np.uint8) * 255
    for i in range(12):
        cv2.putText(img, "Hemoglobin 13.2 g/dL Patient Name Line", (60, 150 + i * 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    M = cv2.getRotationMatrix2D((500, 600), angle, 1.0)
    return cv2.warpAffine(img, M, (1000, 1200), borderValue=(255, 255, 255))

@pytest.mark.parametrize("applied", [-8, -3, 3, 8])
def test_skew_estimate_undoes_applied_rotation(applied):
    assert estimate_skew_angle(_text_image(applied)) == pytest.approx(-applied, abs=0.5)

def test_upright_page_is_not_rotated():
    _, M = deskew(_text_image(0))
    assert M is None

def test_box_maps_back_to_original_frame():
    img = _text_image(5)
    _, M = deskew(img)
    assert M is not None
    inv = cv2.invertAffineTransform(M)
    # The page centre is a fixed point of the rotation
    x, y, w, h = _box_to_original(499, 599, 2, 2, inv)
    assert x == pytest.approx(499, abs=1.5) and y == pytest.approx(599, abs=1.5)
