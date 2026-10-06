import uuid
import pytest
from celery.exceptions import Retry

import src.worker.tasks as tasks
from src.extraction.exceptions import NonRetryableExtractionError

task = tasks.process_document_job


@pytest.fixture
def recorder(monkeypatch):
    calls = {"attempts": [], "retrying": 0, "failed": [], "retry_calls": 0}

    async def fake_mark_failed(session_maker, job_id, exc, step):
        calls["failed"].append(step)

    async def fake_mark_retrying(session_maker, job_id, exc):
        calls["retrying"] += 1

    def fake_retry(*args, **kwargs):
        calls["retry_calls"] += 1
        return Retry("scheduled", exc=kwargs.get("exc"))

    monkeypatch.setattr(tasks, "_mark_failed", fake_mark_failed)
    monkeypatch.setattr(tasks, "_mark_retrying", fake_mark_retrying)
    monkeypatch.setattr(tasks, "_get_worker_session_maker", lambda: None)
    monkeypatch.setattr(task, "retry", fake_retry)
    return calls


def _run_attempt(retries: int, job_id: str):
    task.push_request(retries=retries, id=str(uuid.uuid4()))
    try:
        return task(job_id)
    finally:
        task.pop_request()


def test_transient_failure_marks_job_failed_after_max_retries(monkeypatch, recorder):
    async def always_fails(job_id, attempt=1, session_maker=None):
        recorder["attempts"].append(attempt)
        raise RuntimeError("broker hiccup")

    monkeypatch.setattr(tasks, "process_document_async", always_fails)
    job_id = str(uuid.uuid4())

    # Attempts 1..3 schedule a retry
    for retries in range(task.max_retries):
        with pytest.raises(Retry):
            _run_attempt(retries, job_id)
    assert recorder["failed"] == []

    # The final attempt must mark the job FAILED (not leave it RETRYING forever)
    with pytest.raises(RuntimeError):
        _run_attempt(task.max_retries, job_id)

    assert recorder["attempts"] == [1, 2, 3, 4]
    assert recorder["retrying"] == 3
    assert recorder["retry_calls"] == 3
    assert recorder["failed"] == ["max_retries_exceeded"]


def test_non_retryable_failure_fails_immediately(monkeypatch, recorder):
    async def bad_document(job_id, attempt=1, session_maker=None):
        recorder["attempts"].append(attempt)
        raise NonRetryableExtractionError("schema validation failed")

    monkeypatch.setattr(tasks, "process_document_async", bad_document)

    _run_attempt(0, str(uuid.uuid4()))

    assert recorder["attempts"] == [1]
    assert recorder["retry_calls"] == 0
    assert recorder["failed"] == ["non_retryable"]
