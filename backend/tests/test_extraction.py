import pytest
from src.extraction.rule_based import RuleBasedExtractor

def test_rule_based_extractor():
    extractor = RuleBasedExtractor()
    
    # Mock document data from Phase 7
    mock_data = {
        "pages": [
            {
                "page_number": 1,
                "words": [
                    {"text": "Patient", "bbox": [0.1, 0.1, 0.05, 0.02], "confidence": 100.0},
                    {"text": "Name:", "bbox": [0.16, 0.1, 0.05, 0.02], "confidence": 100.0},
                    {"text": "Aarav", "bbox": [0.22, 0.1, 0.05, 0.02], "confidence": 90.0},
                    {"text": "Mehta", "bbox": [0.28, 0.1, 0.05, 0.02], "confidence": 95.0},
                    {"text": "DOB:", "bbox": [0.1, 0.15, 0.04, 0.02], "confidence": 100.0},
                    {"text": "1998-04-12", "bbox": [0.15, 0.15, 0.08, 0.02], "confidence": 98.0},
                    {"text": "Glucose:", "bbox": [0.1, 0.2, 0.06, 0.02], "confidence": 100.0},
                    {"text": "108", "bbox": [0.17, 0.2, 0.03, 0.02], "confidence": 100.0},
                    {"text": "mg/dL", "bbox": [0.21, 0.2, 0.04, 0.02], "confidence": 100.0}
                ]
            }
        ]
    }
    
    result = extractor.extract(mock_data)
    assert result.model_version == "rule-based-v1.1"
    
    fields = result.fields
    assert len(fields) == 3
    
    name_field = next(f for f in fields if f.field_name == "patient_name")
    assert name_field.value == "Aarav Mehta"
    assert name_field.confidence == 92.5
    assert name_field.page_num == 1
    # Check bbox mapping
    # union of [0.22, 0.1, 0.05, 0.02] and [0.28, 0.1, 0.05, 0.02]
    # min x = 0.22, max x = 0.33, min y = 0.1, max y = 0.12
    # w = 0.11, h = 0.02
    assert name_field.bbox_normalized == pytest.approx([0.22, 0.1, 0.11, 0.02])
    
    dob_field = next(f for f in fields if f.field_name == "date_of_birth")
    assert dob_field.value == "1998-04-12"
    
    glucose_field = next(f for f in fields if f.field_name == "glucose")
    assert glucose_field.value == "108"

def test_factory_selection():
    from src.extraction.factory import ExtractionFactory
    from src.extraction.rule_based import RuleBasedExtractor
    from src.extraction.llm import LLMExtractor
    from src.extraction.vlm import VLMExtractor
    from src.core.config import settings

    settings.EXTRACTION_PROVIDER = "rule_based"
    ext = ExtractionFactory.get_extractor("rule_based")
    assert isinstance(ext, RuleBasedExtractor)

    settings.EXTRACTION_PROVIDER = "llm"
    ext = ExtractionFactory.get_extractor("llm")
    assert isinstance(ext, LLMExtractor)

    settings.EXTRACTION_PROVIDER = "vlm"
    ext = ExtractionFactory.get_extractor("vlm")
    assert isinstance(ext, VLMExtractor)
    
    with pytest.raises(ValueError):
        ExtractionFactory.get_extractor("invalid_provider")

def test_llm_extractor_with_mock():
    from src.extraction.factory import ExtractionFactory
    from src.core.config import settings
    settings.EXTRACTION_PROVIDER = "llm"
    settings.LLM_PROVIDER = "mock"
    
    ext = ExtractionFactory.get_extractor("llm")
    
    mock_data = {"pages": [{"page_number": 1, "words": [{"text": "test"}]}]}
    result = ext.extract(mock_data)
    
    assert result.extractor_type == "llm"
    assert result.provider == "mock"
    assert result.prompt_version == "v1.1"
    assert len(result.fields) == 3
    
    patient_name = next(f for f in result.fields if f.field_name == "patient_name")
    assert patient_name.value == "Jane Doe"
    
    # Check fallback/simulated failure
    mock_data_fail = {"pages": [{"page_number": 1, "words": [{"text": "simulated_failure"}]}]}
    from src.extraction.exceptions import NonRetryableExtractionError
    with pytest.raises(Exception): # Using Exception instead of exact because mock raises Exception
        ext.extract(mock_data_fail)

def test_bbox_validation():
    from src.extraction.schemas import ExtractedFieldData
    from pydantic import ValidationError
    
    # Valid
    f = ExtractedFieldData(field_name="test", bbox_normalized=[0.1, 0.2, 0.3, 0.4])
    assert f.bbox_normalized == [0.1, 0.2, 0.3, 0.4]
    
    # Valid missing
    f = ExtractedFieldData(field_name="test")
    assert f.bbox_normalized is None
    
    # Invalid length
    with pytest.raises(ValidationError):
        ExtractedFieldData(field_name="test", bbox_normalized=[0.1, 0.2])
        
    # Invalid range
    with pytest.raises(ValidationError):
        ExtractedFieldData(field_name="test", bbox_normalized=[-0.1, 0.2, 0.3, 0.4])
        
    with pytest.raises(ValidationError):
        ExtractedFieldData(field_name="test", bbox_normalized=[0.1, 1.2, 0.3, 0.4])
