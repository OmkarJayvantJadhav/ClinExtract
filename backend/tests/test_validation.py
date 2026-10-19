import pytest
import uuid
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.validation.engine import ValidationEngine

@pytest.fixture
def base_extraction():
    e = Extraction(id=uuid.uuid4(), model_version="rule-based", provider="test", prompt_version="1.0")
    # Add all mandatory fields valid
    e.extracted_fields = [
        ExtractedField(field_name="patient_name", value="Aarav Mehta", confidence=100.0, page_num=1),
        ExtractedField(field_name="date_of_birth", value="1998-04-12", confidence=95.0, page_num=1),
        ExtractedField(field_name="patient_id", value="P-10293", confidence=100.0, page_num=1),
        ExtractedField(field_name="specimen_type", value="Blood", confidence=100.0, page_num=1),
        ExtractedField(field_name="collection_date", value="2023-10-01", confidence=100.0, page_num=1),
        ExtractedField(field_name="received_date", value="2023-10-02", confidence=100.0, page_num=1),
        ExtractedField(field_name="glucose", value="90", unit="mg/dL", confidence=98.0, page_num=1),
        ExtractedField(field_name="hemoglobin", value="14.5", unit="g/dL", confidence=100.0, page_num=1),
        ExtractedField(field_name="hematocrit", value="42.0", confidence=100.0, page_num=1),
        ExtractedField(field_name="white_blood_cell_count", value="7.5", confidence=100.0, page_num=1),
        ExtractedField(field_name="platelet_count", value="250", confidence=100.0, page_num=1),
    ]
    return e

def test_valid_complete_document(base_extraction):
    engine = ValidationEngine()
    engine.validate_extraction(base_extraction)
    
    assert base_extraction.decision == "AUTO_ACCEPTED"
    assert base_extraction.overall_confidence >= 0.90
    assert base_extraction.validation_status == "VALID"
    assert all(f.validation_state == "VALID" for f in base_extraction.extracted_fields)

def test_source_mismatch(base_extraction):
    engine = ValidationEngine()
    mock_data = {"mock_mismatch": {"date_of_birth": True}}
    engine.validate_extraction(base_extraction, mock_data)
    
    assert base_extraction.decision == "REVIEW_REQUIRED"
    dob_field = next(f for f in base_extraction.extracted_fields if f.field_name == "date_of_birth")
    assert dob_field.validation_state == "SOURCE_MISMATCH"
    # confidence should be halved: 0.95 * 0.5 = 0.475 => 47.5% < 70% => LOW
    assert dob_field.confidence_category == "LOW"

def test_out_of_range_is_flagged_but_auto_accepted_by_default(base_extraction):
    engine = ValidationEngine()
    glucose = next(f for f in base_extraction.extracted_fields if f.field_name == "glucose")
    glucose.value = "110" # > 100
    engine.validate_extraction(base_extraction)

    # An abnormal result is a clinical finding, not an extraction problem
    assert base_extraction.decision == "AUTO_ACCEPTED"
    assert glucose.validation_state == "OUTSIDE_REFERENCE_RANGE"
    assert glucose.confidence_category == "HIGH" # confidence is not reduced
    assert "glucose: OUTSIDE_REFERENCE_RANGE" in base_extraction.validation_summary["messages"]

def test_out_of_range_held_for_review_when_policy_asks(base_extraction):
    engine = ValidationEngine.from_thresholds(
        {"auto_accept": 0.9, "review_recommended": 0.9, "low_confidence": 0.7},
        {"review_abnormal_results": True},
    )
    glucose = next(f for f in base_extraction.extracted_fields if f.field_name == "glucose")
    glucose.value = "110"
    engine.validate_extraction(base_extraction)
    assert base_extraction.decision == "REVIEW_REQUIRED"

def test_extreme_value_always_goes_to_review(base_extraction):
    hgb = next(f for f in base_extraction.extracted_fields if f.field_name == "hemoglobin")
    hgb.value = "1.45"  # "14.5" with a misread decimal point
    ValidationEngine().validate_extraction(base_extraction)

    assert hgb.validation_state == "EXTREME_VALUE"
    assert "decimal point" in hgb.validation_messages[0]
    assert base_extraction.decision == "REVIEW_REQUIRED"

def test_extreme_value_is_checked_after_unit_conversion():
    from src.validation.rules import validate_numeric_and_range
    # 145 g/L is 14.5 g/dL: normal, not extreme
    state, norm, _ = validate_numeric_and_range("hemoglobin", "145", "g/L")
    assert (state, norm) == ("VALID", "14.5")
    state, _, _ = validate_numeric_and_range("hemoglobin", "145", "g/dL")
    assert state == "EXTREME_VALUE"

def test_invalid_format(base_extraction):
    engine = ValidationEngine()
    dob = next(f for f in base_extraction.extracted_fields if f.field_name == "date_of_birth")
    dob.value = "1998-99-12"
    engine.validate_extraction(base_extraction)
    
    assert base_extraction.decision == "REVIEW_REQUIRED"
    assert dob.validation_state == "INVALID_FORMAT"
    assert dob.confidence_category == "LOW"

def test_missing_required_field(base_extraction):
    engine = ValidationEngine()
    base_extraction.extracted_fields = [f for f in base_extraction.extracted_fields if f.field_name != "patient_id"]
    engine.validate_extraction(base_extraction)
    
    assert base_extraction.decision == "REVIEW_REQUIRED"
    pid = next(f for f in base_extraction.extracted_fields if f.field_name == "patient_id")
    assert pid.validation_state == "MISSING"

def test_low_confidence(base_extraction):
    engine = ValidationEngine()
    glucose = next(f for f in base_extraction.extracted_fields if f.field_name == "glucose")
    glucose.confidence = 65.0
    engine.validate_extraction(base_extraction)
    
    assert base_extraction.decision == "REVIEW_REQUIRED"
    assert glucose.confidence_category == "LOW"
    assert glucose.validation_state == "VALID"

def test_multiple_issues(base_extraction):
    engine = ValidationEngine()
    # 1. Remove ID
    base_extraction.extracted_fields = [f for f in base_extraction.extracted_fields if f.field_name != "patient_id"]
    # 2. Glucose out of range
    glucose = next(f for f in base_extraction.extracted_fields if f.field_name == "glucose")
    glucose.value = "150"
    # 3. DOB Invalid
    dob = next(f for f in base_extraction.extracted_fields if f.field_name == "date_of_birth")
    dob.value = "1998-99-12"
    
    engine.validate_extraction(base_extraction)
    
    assert base_extraction.decision == "REVIEW_REQUIRED"
    assert next(f for f in base_extraction.extracted_fields if f.field_name == "patient_id").validation_state == "MISSING"
    assert glucose.validation_state == "OUTSIDE_REFERENCE_RANGE"
    assert dob.validation_state == "INVALID_FORMAT"
    
    # Check messages array
    assert "patient_id: MISSING" in base_extraction.validation_summary["messages"]
    assert "glucose: OUTSIDE_REFERENCE_RANGE" in base_extraction.validation_summary["messages"]
    assert "date_of_birth: INVALID_FORMAT" in base_extraction.validation_summary["messages"]


def test_a_low_count_with_a_dropped_decimal_point_goes_to_review():
    from src.validation.rules import validate_numeric_and_range
    state, _, meta = validate_numeric_and_range("white_blood_cell_count", "32", "x10^3/uL", printed_range="4.5 - 11.0")
    assert state == "EXTREME_VALUE" and meta["reason"] == "far_outside_range"
    # A plainly high count is still an ordinary abnormal result
    assert validate_numeric_and_range("white_blood_cell_count", "18", "x10^3/uL", printed_range="4.5 - 11.0")[0] == "OUTSIDE_REFERENCE_RANGE"


def test_an_overflowing_number_is_not_a_number():
    from src.validation.rules import validate_numeric_and_range
    assert validate_numeric_and_range("glucose", "9" * 400, "mg/dL")[0] == "INVALID_FORMAT"


@pytest.mark.parametrize("field, value, page, found", [
    ("glucose", "99", "Glucose 9.9 mmol/L 3.9 - 5.6", False),
    ("hemoglobin", "14.2", "Hemoglobin 142 g/L", False),
    ("glucose", "9.9", "Glucose 9.9 mmol/L", True),
    ("hemoglobin", "14.2", "Hemoglobin 14,2 g/dL", True),
    ("platelet_count", "250000", "Platelets 250,000 /uL", True),
    ("glucose", "92", "Glucose 92mg/dL", True),
    ("glucose", "92", "Glucose (92) H", True),
])
def test_a_result_must_match_the_printed_number_decimal_point_included(field, value, page, found):
    from src.validation.rules import validate_source_agreement
    assert validate_source_agreement(value, page, field) is found
