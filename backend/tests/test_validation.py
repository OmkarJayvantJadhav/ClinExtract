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
        ExtractedField(field_name="glucose", value="90", confidence=98.0, page_num=1),
        ExtractedField(field_name="hemoglobin", value="14.5", confidence=100.0, page_num=1),
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

def test_out_of_range(base_extraction):
    engine = ValidationEngine()
    glucose = next(f for f in base_extraction.extracted_fields if f.field_name == "glucose")
    glucose.value = "110" # > 100
    engine.validate_extraction(base_extraction)
    
    assert base_extraction.decision == "REVIEW_REQUIRED"
    assert glucose.validation_state == "OUTSIDE_REFERENCE_RANGE"
    assert glucose.confidence_category == "HIGH" # confidence is not reduced

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
