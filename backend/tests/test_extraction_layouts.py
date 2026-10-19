"""
Report layouts that used to auto-accept a wrong value: each must now read the right value or
send the document to review.
"""
import uuid

import pytest

from src.db.models.extracted_field import ExtractedField
from src.db.models.extraction import Extraction
from src.extraction.rule_based import RuleBasedExtractor
from src.validation.confidence import calculate_field_confidence
from src.validation.engine import ValidationEngine

HEADER = """Patient Name: Aarav Mehta
Patient ID: P-10293
DOB: 1980-04-12 Sex: Male
Specimen Type: Blood
Collection Date: 2026-01-10 Received Date: 2026-01-11
"""
RESULTS = """Glucose 90 mg/dL 70 - 100
Hemoglobin 14.5 g/dL 13.5 - 17.5
Hematocrit 44.0 % 41 - 50
WBC 7.5 K/uL 4.5 - 11.0
Platelets 250 K/uL 150 - 450
"""


def _page(text: str) -> dict:
    """A native-text page: one row of words per line of `text`."""
    words = []
    for row, line in enumerate(text.strip().split("\n")):
        for col, word in enumerate(line.split()):
            words.append({"text": word, "confidence": 99.0, "bbox": [min(0.05 * col, 0.9), 0.03 * row, 0.04, 0.02]})
    return {"page_number": 1, "words": words, "ocr_used": False}


def _run(text: str):
    doc = {"pages": [_page(text)]}
    result = RuleBasedExtractor().extract(doc)
    extraction = Extraction(id=uuid.uuid4(), model_version="t", provider="t", prompt_version="t")
    extraction.extracted_fields = [
        ExtractedField(field_name=f.field_name, value=f.value, unit=f.unit, confidence=f.confidence, page_num=f.page_num,
                       reference_range=f.reference_range, abnormal_flag=f.abnormal_flag)
        for f in result.fields
    ]
    ValidationEngine().validate_extraction(extraction, doc)
    return extraction, {f.field_name: f for f in extraction.extracted_fields}


def test_clean_report_is_auto_accepted():
    extraction, fields = _run(HEADER + RESULTS)
    assert extraction.decision == "AUTO_ACCEPTED"
    assert fields["patient_id"].value == "P-10293" and fields["glucose"].normalized_value == "90"


@pytest.mark.parametrize("line, expected", [
    ("Patient ID Number: P-10293", "P-10293"),
    ("MRN No. 778812", "778812"),
    ("Patient ID:", None),  # blank: never the next line's "DOB"
])
def test_patient_id_is_never_a_label_word(line, expected):
    extraction, fields = _run(HEADER.replace("Patient ID: P-10293", line) + RESULTS)
    assert fields["patient_id"].value == expected
    if expected is None:
        assert extraction.decision == "REVIEW_REQUIRED"


def test_another_persons_name_is_not_the_patient():
    _, fields = _run("Physician Name: Dr Rao\n" + HEADER + RESULTS)
    assert fields["patient_name"].value == "Aarav Mehta"


def test_patient_name_stops_at_the_end_of_its_line():
    header = HEADER.replace("Patient Name: Aarav Mehta\n", "") + "Patient Name: Aarav Mehta\nComplete Blood Count\n"
    _, fields = _run(header + RESULTS)
    assert fields["patient_name"].value == "Aarav Mehta"


def test_range_lower_limit_is_not_the_result():
    extraction, fields = _run(HEADER + RESULTS.replace("Hemoglobin 14.5 g/dL 13.5 - 17.5", "Hemoglobin 13.5 - 17.5 g/dL"))
    assert fields["hemoglobin"].value is None
    assert extraction.decision == "REVIEW_REQUIRED"


def test_unit_printed_after_the_range_is_used():
    _, fields = _run(HEADER + RESULTS.replace("Glucose 90 mg/dL 70 - 100", "Glucose 12.0 3.9 - 5.6 mmol/L"))
    assert fields["glucose"].unit == "mmol/L"
    assert float(fields["glucose"].normalized_value) == pytest.approx(216.2, abs=0.1)


@pytest.mark.parametrize("result", ["Glucose 90 70 - 100", "Glucose 5.5 mmol/1"])
def test_missing_or_unknown_glucose_unit_goes_to_review(result):
    extraction, fields = _run(HEADER + RESULTS.replace("Glucose 90 mg/dL 70 - 100", result))
    assert fields["glucose"].validation_state == "UNRECOGNIZED_UNIT"
    assert extraction.decision == "REVIEW_REQUIRED"


def test_decimal_comma_is_read_as_a_decimal():
    _, fields = _run(HEADER + RESULTS.replace("14.5 g/dL", "14,8 g/dL").replace("Glucose 90 mg/dL 70 - 100", "Glucose 5,0 mmol/L 3,9 - 5,6"))
    assert fields["hemoglobin"].normalized_value == "14.8"
    assert float(fields["glucose"].normalized_value) == pytest.approx(90.08, abs=0.01)
    assert fields["glucose"].validation_state == "VALID"


@pytest.mark.parametrize("line", ["Mean Cell Hemoglobin 24.0 pg 27 - 33", "Estimated Average Glucose 140 mg/dL"])
def test_other_analytes_are_not_taken_as_hemoglobin_or_glucose(line):
    _, fields = _run(HEADER + line + "\n" + RESULTS)
    assert fields["hemoglobin"].value == "14.5" and fields["glucose"].value == "90"


def test_a_word_on_the_next_line_is_not_a_flag():
    _, fields = _run(HEADER + RESULTS + "High Sensitivity CRP 1.0 mg/L\n")
    assert fields["glucose"].abnormal_flag is None and fields["glucose"].validation_state == "VALID"


def test_flag_contradicting_the_built_in_range_is_a_mismatch():
    extraction, fields = _run(HEADER + RESULTS.replace("Glucose 90 mg/dL 70 - 100", "Glucose 150 L mg/dL"))
    assert fields["glucose"].validation_state == "FLAG_MISMATCH"
    assert extraction.decision == "REVIEW_REQUIRED"


def test_day_first_document_reads_all_its_dates_day_first():
    header = HEADER.replace("DOB: 1980-04-12", "DOB: 25/03/1980").replace(
        "Collection Date: 2026-01-10 Received Date: 2026-01-11", "Collection Date: 05/04/2026 Received Date: 06/04/2026")
    _, fields = _run(header + RESULTS)
    assert fields["collection_date"].normalized_value == "2026-04-05"
    assert fields["received_date"].normalized_value == "2026-04-06"


@pytest.mark.parametrize("value", [None, "", "Unknown"])
def test_sex_not_given_does_not_block(value):
    state, messages, _, normalized = ValidationEngine().validate_field("patient_sex", value)
    assert state == "VALID" and normalized is None


def test_confidence_is_always_on_a_0_to_100_scale():
    assert calculate_field_confidence(1.0, "VALID") == 0.01
    assert calculate_field_confidence(95.0, "VALID") == 0.95
