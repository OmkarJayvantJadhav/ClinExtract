"""
The demo sample reports (scripts/make_sample_reports.py) must keep demonstrating what their
descriptions say, and the OCR path must read table rows in order.
"""
import os
import sys
import uuid

import filetype
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from make_sample_reports import SAMPLES  # noqa: E402

from src.db.models.extracted_field import ExtractedField
from src.db.models.extraction import Extraction
from src.extraction.rule_based import RuleBasedExtractor
from src.processing.analyzer import DocumentAnalyzer
from src.validation.engine import ValidationEngine


def _run(filename):
    data = SAMPLES[filename][0]()
    artifact = DocumentAnalyzer.process(data, filetype.guess(data).mime, "doc", "job")
    result = RuleBasedExtractor().extract(artifact)
    extraction = Extraction(id=uuid.uuid4(), model_version="t", provider="t", prompt_version="t")
    extraction.extracted_fields = [
        ExtractedField(field_name=f.field_name, value=f.value, unit=f.unit, confidence=f.confidence, page_num=f.page_num)
        for f in result.fields
    ]
    ValidationEngine().validate_extraction(extraction, artifact)
    return extraction, {f.field_name: f for f in extraction.extracted_fields}


@pytest.mark.parametrize("filename", [name for name, (_, expected, _) in SAMPLES.items() if expected])
def test_sample_reaches_expected_decision(filename):
    extraction, _ = _run(filename)
    assert extraction.decision == SAMPLES[filename][1]


def test_abnormal_sample_is_flagged():
    _, fields = _run("02_abnormal_results.pdf")
    assert fields["glucose"].validation_state == "OUTSIDE_REFERENCE_RANGE"
    assert fields["hemoglobin"].validation_metadata["range_basis"] == "adult female"


def test_correction_sample_has_blocking_issues():
    _, fields = _run("04_needs_correction.pdf")
    assert fields["patient_id"].validation_state == "MISSING"
    assert fields["date_of_birth"].validation_state == "INVALID_FORMAT"


def test_misread_decimal_sample_is_extreme():
    _, fields = _run("05_decimal_misread.pdf")
    assert fields["hemoglobin"].validation_state == "EXTREME_VALUE"


@pytest.mark.parametrize("filename", ["03_scanned_report.jpg", "06_mixed_page.pdf"])
def test_ocr_samples_read_every_result(filename):
    _, fields = _run(filename)
    expected = {"glucose": "92", "white_blood_cell_count": "7.2", "platelet_count": "265"}
    assert {name: fields[name].value for name in expected} == expected
    assert all(fields[name].validation_state != "MISSING" for name in fields)


def test_ocr_words_follow_table_rows():
    from src.processing.scanned_image import _reading_order
    # Two table rows emitted column by column, as Tesseract does for widely spaced columns
    positioned = [
        (100, 20, 10, {"text": "Glucose"}), (140, 20, 10, {"text": "Hemoglobin"}),
        (101, 20, 300, {"text": "92"}), (139, 20, 300, {"text": "14.8"}),
    ]
    assert [w["text"] for _, _, _, w in _reading_order(positioned)] == ["Glucose", "92", "Hemoglobin", "14.8"]
