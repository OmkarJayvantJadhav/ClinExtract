"""
Accuracy regression guard on labeled synthetic reports (evaluation/). A change that makes
extraction worse, routes everything to review, or lets a wrong document through without
review fails here. Full report: python scripts/evaluate_extraction.py
"""
import pytest

from evaluation.scoring import evaluate
from evaluation.synthetic import make_cases


@pytest.fixture(scope="module")
def report():
    return evaluate(make_cases(24, seed=0))


def test_field_accuracy(report):
    assert report.overall_field_accuracy >= 0.97, report.markdown()


def test_auto_accepted_documents_are_fully_correct(report):
    # Auto-accepted documents are never seen by a reviewer, so none may contain an error
    assert report.auto_accept_precision == 1.0, report.markdown()


def test_most_documents_skip_review(report):
    assert len(report.auto_accepted) / len(report.results) >= 0.5, report.markdown()


def test_evaluation_runs_other_extractors():
    # The plumbing used to measure Gemini (--extractor llm/vlm), here with the mock provider
    from evaluation.scoring import run_case
    from src.extraction.llm import LLMExtractor
    from src.extraction.vlm import VLMExtractor
    from src.extraction.providers.mock_provider import MockLLMProvider, MockVLMProvider
    case = make_cases(1, seed=0)[0]
    for extractor in (LLMExtractor(MockLLMProvider()), VLMExtractor(MockVLMProvider())):
        result = run_case(case, extractor=extractor)
        assert result.found["patient_name"] == "Jane Doe"  # the mock's fixed answer, scored as wrong
        assert result.outcomes["patient_name"] == "wrong"
