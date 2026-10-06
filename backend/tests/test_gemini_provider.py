"""
Gemini provider tests with a fake SDK client (no network, no API key).
They pin down the request we build: raw image bytes, the right MIME type, the field list in
the prompt, structured-output config, and error classification.
"""
import io
import json

import pytest
from PIL import Image
from google.genai.errors import APIError

from src.core.config import settings
from src.extraction.providers.gemini_provider import GeminiProvider
from src.extraction.exceptions import NonRetryableExtractionError, RetryableExtractionError
from src.extraction.llm import LLMExtractor
from src.extraction.vlm import VLMExtractor
from src.extraction.schemas import CLINICAL_FIELD_SPECS, ExtractionResult


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FakeResponse(self.outcome)


class FakeClient:
    def __init__(self, outcome):
        self.models = FakeModels(outcome)


GOOD_OUTPUT = json.dumps({
    "extractor_type": "llm",
    "provider": "gemini",
    "fields": [
        {"field_name": "patient_name", "value": "Jane Doe", "confidence": 97, "page_num": 1, "bbox_normalized": None},
        {"field_name": "glucose", "value": "92", "unit": "mg/dL", "confidence": 95, "page_num": 1, "bbox_normalized": None},
    ],
})


def make_provider(monkeypatch, outcome):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)  # don't build a real client
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test-model")
    provider = GeminiProvider()
    provider.client = FakeClient(outcome)
    return provider


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_llm_request_and_parsing(monkeypatch):
    provider = make_provider(monkeypatch, GOOD_OUTPUT)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    result = LLMExtractor(provider).extract({"pages": [{"page_number": 1, "words": [{"text": "Glucose:"}, {"text": "92"}]}]})

    call = provider.client.models.calls[0]
    prompt = call["contents"][-1]
    assert call["model"] == "gemini-test-model"
    assert call["config"]["response_mime_type"] == "application/json"
    assert "fallback_metadata" not in call["config"]["response_schema"].model_fields
    assert all(f'"{name}"' in prompt for name in CLINICAL_FIELD_SPECS)
    assert "Glucose: 92" in prompt
    assert result.extractor_type == "llm" and result.provider == "gemini"
    assert {f.field_name: f.unit for f in result.fields}["glucose"] == "mg/dL"


def test_vlm_sends_raw_png_bytes_with_png_mime(monkeypatch):
    provider = make_provider(monkeypatch, GOOD_OUTPUT)
    image = png_bytes()
    result = VLMExtractor(provider).extract({"pages": []}, metadata={"image_bytes": image})

    part = provider.client.models.calls[0]["contents"][0]
    assert part.inline_data.mime_type == "image/png"
    assert part.inline_data.data == image  # raw bytes, not base64 text
    assert all(f.page_num == 1 for f in result.fields)


def test_vlm_renders_pdf_pages_as_jpeg(monkeypatch):
    import fitz
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "Glucose: 92 mg/dL")
    doc.new_page().insert_text((50, 50), "Page two")
    provider = make_provider(monkeypatch, GOOD_OUTPUT)
    VLMExtractor(provider).extract({"pages": []}, metadata={"image_bytes": doc.write()})

    calls = provider.client.models.calls
    assert len(calls) == 2
    assert all(c["contents"][0].inline_data.mime_type == "image/jpeg" for c in calls)
    assert calls[0]["contents"][0].inline_data.data[:3] == b"\xff\xd8\xff"  # JPEG magic


def test_malformed_output_is_non_retryable(monkeypatch):
    provider = make_provider(monkeypatch, '{"fields": "not a list"}')
    with pytest.raises(NonRetryableExtractionError):
        LLMExtractor(provider).extract({"pages": []})


@pytest.mark.parametrize("code,expected", [(401, NonRetryableExtractionError), (403, NonRetryableExtractionError),
                                           (429, RetryableExtractionError), (503, RetryableExtractionError)])
def test_api_errors_are_classified(monkeypatch, code, expected):
    provider = make_provider(monkeypatch, APIError(code, {"error": {"message": "boom", "status": "X"}}))
    with pytest.raises(expected):
        provider.generate_structured("prompt", schema=ExtractionResult)


def test_missing_key_is_non_retryable(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    with pytest.raises(NonRetryableExtractionError):
        GeminiProvider().generate_structured("prompt", schema=object)
