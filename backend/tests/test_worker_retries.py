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


# --- stuck-job sweep ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_requeue_stuck_jobs(db_session, user):
    from datetime import datetime, timedelta, timezone
    from src.db.models.document import Document, DocumentStatus
    from src.db.models.processing_job import ProcessingJob, JobStatus

    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=1)

    def make(status, updated_at):
        doc = Document(uploader_id=user.id, filename="stuck.pdf", storage_key=str(uuid.uuid4()), status=DocumentStatus.PROCESSING)
        db_session.add(doc)
        job = ProcessingJob(document=doc, status=status, correlation_id="cid")
        db_session.add(job)
        return job, updated_at

    planned = [make(JobStatus.QUEUED, old), make(JobStatus.RUNNING, old), make(JobStatus.QUEUED, now),
               make(JobStatus.SUCCEEDED, old), make(JobStatus.RETRYING, old)]
    await db_session.flush()
    for job, updated_at in planned:
        job.updated_at = updated_at
    await db_session.commit()
    lost_queued, dead_running, fresh, done, lost_retrying = (job for job, _ in planned)

    sent = []
    requeued = await tasks.requeue_stuck_jobs(db_session, lambda job_id, cid: sent.append((job_id, cid)), now=now)

    expected = {str(lost_queued.id), str(dead_running.id), str(lost_retrying.id)}
    assert expected <= set(requeued)  # other tests' leftovers may be swept too
    assert str(fresh.id) not in requeued and str(done.id) not in requeued
    assert (str(dead_running.id), "cid") in sent
    await db_session.refresh(dead_running)
    assert dead_running.status == JobStatus.QUEUED  # abandoned run reset so the task will pick it up

    # Touched: not sent again by the next sweep
    again = await tasks.requeue_stuck_jobs(db_session, lambda *a: None, now=now + timedelta(minutes=10))
    assert not expected & set(again)
