import asyncio
import io
import json
import uuid

import pytest
from cryptography.fernet import Fernet

from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.extraction.rule_based import RuleBasedExtractor
from src.validation.engine import ValidationEngine
from src.validation.rules import validate_source_agreement, age_in_years
from src.validation.reference_ranges import get_reference_range
from src.services.system_settings import validate_thresholds, DEFAULT_THRESHOLDS
from src.storage.local import LocalVolumeStorage
from src.core.rate_limit import SlidingWindowLimiter
from src.utils.security import password_policy_error


# --- sex / age aware reference ranges ------------------------------------------

def test_reference_range_by_sex_and_age():
    assert get_reference_range("hemoglobin", "F", 40)[:2] == (12.0, 15.5)
    assert get_reference_range("hemoglobin", "M", 40)[:2] == (13.5, 17.5)
    assert get_reference_range("hemoglobin", None, 40)[2] == "adult (sex unknown)"
    assert get_reference_range("hemoglobin", "F", 9) is None  # pediatric

def test_age_in_years():
    assert age_in_years("2000-06-15", "2020-06-14") == 19
    assert age_in_years("2000-06-15", "2020-06-15") == 20
    assert age_in_years("not a date") is None


def _extraction(**values):
    base = {
        "patient_name": "Aarav Mehta", "date_of_birth": "1980-04-12", "patient_id": "P-1",
        "specimen_type": "Blood", "collection_date": "2023-10-01", "received_date": "2023-10-02",
        "glucose": "90", "hemoglobin": "14.5", "hematocrit": "42", "white_blood_cell_count": "7.5",
        "platelet_count": "250",
    }
    base.update(values)
    e = Extraction(id=uuid.uuid4(), model_version="t", provider="t", prompt_version="t")
    e.extracted_fields = [ExtractedField(field_name=k, value=v, confidence=100.0, page_num=1) for k, v in base.items() if v is not None]
    return e

def _field(e, name):
    return next(f for f in e.extracted_fields if f.field_name == name)

def test_female_hemoglobin_uses_female_range():
    e = _extraction(hemoglobin="16.0", patient_sex="F")
    ValidationEngine().validate_extraction(e)
    hgb = _field(e, "hemoglobin")
    assert hgb.validation_state == "OUTSIDE_REFERENCE_RANGE"
    assert hgb.validation_metadata["range_basis"] == "adult female"
    assert _field(e, "patient_sex").normalized_value == "F"

def test_same_value_is_normal_for_male():
    e = _extraction(hemoglobin="16.0", patient_sex="Male")
    ValidationEngine().validate_extraction(e)
    assert _field(e, "hemoglobin").validation_state == "VALID"

def test_pediatric_patient_gets_no_adult_range():
    e = _extraction(date_of_birth="2015-01-01")
    ValidationEngine().validate_extraction(e)
    assert _field(e, "glucose").validation_state == "NO_REFERENCE_RANGE"
    assert e.decision == "REVIEW_REQUIRED"

def test_sex_is_optional():
    e = _extraction()
    ValidationEngine().validate_extraction(e)
    assert not any(f.field_name == "patient_sex" for f in e.extracted_fields)
    assert e.decision == "AUTO_ACCEPTED"


# --- source agreement ----------------------------------------------------------

def test_source_agreement_normalization():
    assert validate_source_agreement("250,000", "Platelet Count 250000 /uL")
    assert validate_source_agreement("O'Brien", "Patient: OBRIEN")
    assert not validate_source_agreement("Jane Doe", "Patient Name: John Smith")

def test_value_not_on_page_is_source_mismatch():
    e = _extraction()
    artifact = {"pages": [{"page_number": 1, "words": [{"text": t} for t in (
        "Patient Name: Aarav Mehta DOB: 1980-04-12 Patient ID: P-1 Specimen Type: Blood "
        "Collection Date: 2023-10-01 Received Date: 2023-10-02 Glucose: 95 mg/dL Hemoglobin: 14.5 "
        "Hematocrit: 42 White Blood Cell Count: 7.5 Platelet Count: 250").split()]}]}
    ValidationEngine().validate_extraction(e, artifact)
    assert _field(e, "glucose").validation_state == "SOURCE_MISMATCH"  # extracted 90, page says 95
    assert _field(e, "hemoglobin").validation_state == "VALID"


# --- layouts -------------------------------------------------------------------

def _page(text):
    return {"pages": [{"page_number": 1, "words": [
        {"text": t, "bbox": [0.01, 0.1, 0.01, 0.02], "confidence": 100.0} for t in text.split()
    ]}]}

def test_alternative_report_layout():
    text = ("Name: DOE, JANE MRN: 00012345 Sex: F D.O.B. 03/14/1975 Sample: Serum "
            "Collected: 2024/02/01 Date Received: 2024/02/02 Glucose, Fasting 101 mg/dL "
            "HGB 12.9 g/dL HCT 38.5 % WBC 6.2 10^3/uL PLT 210 K/uL")
    fields = {f.field_name: f for f in RuleBasedExtractor().extract(_page(text)).fields}
    assert fields["patient_name"].value == "DOE, JANE"
    assert fields["patient_id"].value == "00012345"
    assert fields["patient_sex"].value == "F"
    assert fields["date_of_birth"].value == "03/14/1975"
    assert fields["specimen_type"].value == "Serum"
    assert fields["collection_date"].value == "2024/02/01"
    assert fields["received_date"].value == "2024/02/02"
    assert (fields["glucose"].value, fields["glucose"].unit) == ("101", "mg/dL")
    assert fields["hemoglobin"].value == "12.9"
    assert fields["hematocrit"].value == "38.5"
    assert fields["white_blood_cell_count"].unit == "10^3/uL"
    assert fields["platelet_count"].unit == "K/uL"

def test_hb_does_not_match_hba1c():
    fields = {f.field_name: f for f in RuleBasedExtractor().extract(_page("HbA1c: 5.6 % Hemoglobin: 14.1 g/dL")).fields}
    assert fields["hemoglobin"].value == "14.1"


# --- encryption at rest --------------------------------------------------------

def test_storage_encrypts_and_reads_legacy_plaintext(tmp_path):
    key = Fernet.generate_key().decode()
    docs = tmp_path / "documents"
    store = LocalVolumeStorage(str(docs), encryption_key=key)

    asyncio.run(store.upload_file("doc1", io.BytesIO(b"%PDF-1.4 secret")))
    raw = (docs / "doc1").read_bytes()
    assert b"secret" not in raw and raw.startswith(b"gAAAAA")
    assert asyncio.run(store.get_file("doc1")).read() == b"%PDF-1.4 secret"

    asyncio.run(store.upload_artifact("doc1_ocr.json", json.dumps({"t": "PHI"})))
    assert b"PHI" not in (tmp_path / "artifacts" / "doc1_ocr.json").read_bytes()
    assert json.loads(asyncio.run(store.get_artifact("doc1_ocr.json"))) == {"t": "PHI"}

    (docs / "legacy").write_bytes(b"%PDF-1.4 old")  # written before encryption was enabled
    assert asyncio.run(store.get_file("legacy")).read() == b"%PDF-1.4 old"

def test_encrypted_file_without_key_fails_loudly(tmp_path):
    key = Fernet.generate_key().decode()
    asyncio.run(LocalVolumeStorage(str(tmp_path), encryption_key=key).upload_file("d", io.BytesIO(b"x")))
    with pytest.raises(ValueError):
        asyncio.run(LocalVolumeStorage(str(tmp_path)).get_file("d"))


# --- security helpers ----------------------------------------------------------

def test_password_policy():
    assert password_policy_error("short1!") is not None
    assert password_policy_error("alllowercaseletters") is not None
    assert password_policy_error("Reviewer-Pass-2026", username="reviewer") is not None
    assert password_policy_error("Correct-Horse-42") is None

def test_rate_limiter():
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert [limiter.allow("ip") for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("other-ip")


# --- settings / external AI guard ----------------------------------------------

def test_threshold_validation():
    assert validate_thresholds(DEFAULT_THRESHOLDS) is None
    assert validate_thresholds({**DEFAULT_THRESHOLDS, "low_confidence": 0.95}) is not None
    assert validate_thresholds({**DEFAULT_THRESHOLDS, "auto_accept": 0.3}) is not None

def test_custom_thresholds_change_categories():
    e = _extraction()
    for f in e.extracted_fields:
        f.confidence = 80.0
    ValidationEngine(auto_accept_threshold=0.75, review_recommended=0.75, low_confidence=0.5).validate_extraction(e)
    assert e.decision == "AUTO_ACCEPTED"

def test_gemini_refused_without_phi_consent(monkeypatch):
    from src.core.config import settings
    from src.extraction.factory import ExtractionFactory
    from src.extraction.exceptions import NonRetryableExtractionError
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_AI_PHI", False)
    with pytest.raises(NonRetryableExtractionError, match="ALLOW_EXTERNAL_AI_PHI"):
        ExtractionFactory.get_extractor("llm")
