import asyncio
import concurrent.futures
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import filetype
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.worker.celery_app import celery_app
from src.core.config import settings
from src.core.database import async_session_maker, create_worker_session_maker
from src.db.models.processing_job import ProcessingJob, JobStatus
from src.db.models.document import Document, DocumentStatus
from src.core.logging import correlation_id_var, document_id_var, job_id_var, get_logger
from src.extraction.exceptions import NonRetryableExtractionError
from src.processing.analyzer import DocumentProcessingError
from src.services.audit import log_audit_event, RESOURCE_DOCUMENT

logger = get_logger(__name__)

# Failures caused by the document or configuration itself. Retrying cannot fix these.
NON_RETRYABLE_ERRORS = (NonRetryableExtractionError, DocumentProcessingError, FileNotFoundError, ValueError)

_worker_session_maker: Optional[async_sessionmaker] = None

def _get_worker_session_maker() -> async_sessionmaker:
    global _worker_session_maker
    if _worker_session_maker is None:
        _worker_session_maker = create_worker_session_maker()
    return _worker_session_maker

def _run(coro):
    """
    Runs a coroutine to completion from synchronous Celery code. If an event loop is
    already running in this thread (eager mode inside the API during tests), the
    coroutine runs on a private loop in a helper thread instead.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()

def _is_stale(job: ProcessingJob) -> bool:
    if job.updated_at is None:
        return True
    updated = job.updated_at if job.updated_at.tzinfo else job.updated_at.replace(tzinfo=timezone.utc)
    return updated < datetime.now(timezone.utc) - timedelta(minutes=settings.JOB_STALE_AFTER_MINUTES)

async def _extract_with_fallback(session, doc_id_str: str, artifact: dict, file_bytes: bytes):
    from src.extraction.service import ExtractionService
    from src.extraction.factory import ExtractionFactory

    provider_name = settings.EXTRACTION_PROVIDER
    try:
        extractor = ExtractionFactory.get_extractor(provider_name)
        return await ExtractionService(extractor).process_extraction(
            session, doc_id_str, artifact, metadata={"image_bytes": file_bytes}
        )
    except Exception as ext_err:
        logger.error(f"Primary extractor '{provider_name}' failed: {ext_err}")
        if not (settings.EXTRACTION_FALLBACK_ENABLED and provider_name != "rule_based"):
            raise
        # Fall back for any primary failure, including configuration/auth/schema errors,
        # which are exactly the cases the primary provider cannot recover from.
        logger.info("Fallback enabled. Attempting RuleBasedExtractor.")
        await session.rollback()
        fallback_extractor = ExtractionFactory.get_extractor("rule_based")
        return await ExtractionService(fallback_extractor).process_extraction(
            session,
            doc_id_str,
            artifact,
            metadata={
                "image_bytes": file_bytes,
                "fallback_reason": str(ext_err),
                "original_extractor": provider_name,
                "fallback_extractor": "rule_based"
            }
        )

async def process_document_async(job_id: str, attempt: int = 1, session_maker: Optional[async_sessionmaker] = None):
    session_maker = session_maker or async_session_maker
    job_uuid = uuid.UUID(job_id)

    # 1. Transaction A: lock job and document, verify, set RUNNING/PROCESSING
    async with session_maker() as session:
        stmt = select(ProcessingJob).where(ProcessingJob.id == job_uuid).with_for_update()
        job = (await session.execute(stmt)).scalar_one_or_none()

        if not job:
            return "Job not found"

        runnable = job.status in (JobStatus.QUEUED, JobStatus.RETRYING) or (
            # acks_late redelivers a task whose worker died mid-run; the job is still RUNNING.
            job.status == JobStatus.RUNNING and _is_stale(job)
        )
        if not runnable:
            return "Job already processed or locked"

        doc_stmt = select(Document).where(Document.id == job.document_id).with_for_update()
        document = (await session.execute(doc_stmt)).scalar_one_or_none()
        if not document:
            return "Document not found"

        job.status = JobStatus.RUNNING
        job.attempt_number = attempt
        document.status = DocumentStatus.PROCESSING
        storage_key = document.storage_key
        doc_id_str = str(document.id)
        document_id_var.set(doc_id_str)

        await session.commit()

    # 2. Preprocessing & OCR (no DB transaction held open)
    from src.storage import get_storage_service
    from src.processing.analyzer import DocumentAnalyzer

    storage = get_storage_service()
    file_stream = await storage.backend.get_file(storage_key)
    try:
        file_bytes = file_stream.read()
    finally:
        file_stream.close()

    kind = filetype.guess(file_bytes)
    mime_type = kind.mime if kind else "application/pdf"

    artifact = DocumentAnalyzer.process(file_bytes, mime_type, doc_id_str, str(job_uuid))
    await storage.store_artifact(storage_key, json.dumps(artifact, indent=2))

    # 3. Transaction B: extraction + validation + final statuses, committed atomically.
    # A failure anywhere here rolls everything back, so a retry starts clean.
    from src.validation.engine import ValidationEngine

    async with session_maker() as session:
        extraction = await _extract_with_fallback(session, doc_id_str, artifact, file_bytes)
        ValidationEngine().validate_extraction(extraction, artifact)
        final_decision = extraction.decision

        job2 = await session.get(ProcessingJob, job_uuid)
        if job2:
            job2.status = JobStatus.SUCCEEDED
            job2.error_details = None

        doc = await session.get(Document, uuid.UUID(doc_id_str))
        new_status = DocumentStatus.AUTO_ACCEPTED if final_decision == "AUTO_ACCEPTED" else DocumentStatus.REVIEW_REQUIRED
        if doc:
            doc.status = new_status

        await log_audit_event(
            session, action="DOCUMENT_PROCESSED", resource_type=RESOURCE_DOCUMENT, resource_id=doc_id_str,
            correlation_id=correlation_id_var.get(None),
            after_state={
                "status": new_status.value,
                "decision": final_decision,
                "extractor_type": extraction.extractor_type,
                "overall_confidence": extraction.overall_confidence,
                "attempt": attempt,
            }
        )
        await session.commit()

    return f"Job {job_id} processed successfully. Decision: {final_decision}"

async def _mark_failed(session_maker: async_sessionmaker, job_id: str, exc: Exception, step: str):
    async with session_maker() as session:
        stmt = select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id)).with_for_update()
        job = (await session.execute(stmt)).scalar_one_or_none()
        if not job:
            return
        job.status = JobStatus.FAILED
        job.error_details = {"error": str(exc), "error_type": type(exc).__name__, "step": step}
        doc = await session.get(Document, job.document_id)
        if doc:
            doc.status = DocumentStatus.FAILED
            await log_audit_event(
                session, action="DOCUMENT_PROCESSING_FAILED", resource_type=RESOURCE_DOCUMENT,
                resource_id=str(doc.id), correlation_id=correlation_id_var.get(None),
                after_state={"status": DocumentStatus.FAILED.value, "error": str(exc), "step": step}
            )
        await session.commit()

async def _mark_retrying(session_maker: async_sessionmaker, job_id: str, exc: Exception):
    async with session_maker() as session:
        stmt = select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id)).with_for_update()
        job = (await session.execute(stmt)).scalar_one_or_none()
        if job:
            job.status = JobStatus.RETRYING
            job.error_details = {"error": str(exc), "error_type": type(exc).__name__, "step": "retrying"}
            await session.commit()

@celery_app.task(
    bind=True, name="process_document_job", max_retries=3, acks_late=True,
    soft_time_limit=540, time_limit=600,
)
def process_document_job(self, job_id: str, correlation_id: str = None):
    """
    Synchronous Celery task that wraps the async processor.
    """
    t1 = correlation_id_var.set(correlation_id if correlation_id else str(uuid.uuid4()))
    t2 = job_id_var.set(job_id)
    session_maker = _get_worker_session_maker()

    try:
        logger.info("Starting processing job", extra={"event": "job_started"})
        attempt = self.request.retries + 1
        try:
            return _run(process_document_async(job_id, attempt, session_maker))
        except NON_RETRYABLE_ERRORS as exc:
            logger.error(f"Job failed permanently: {exc}", extra={"event": "job_failed"})
            _run(_mark_failed(session_maker, job_id, exc, "non_retryable"))
            return f"Job {job_id} failed: {exc}"
        except Exception as exc:
            # Decide explicitly: Task.retry(exc=...) re-raises `exc` (not
            # MaxRetriesExceededError) once retries are exhausted.
            if self.request.retries >= self.max_retries:
                logger.error(f"Job failed after {attempt} attempts: {exc}", extra={"event": "job_failed"})
                _run(_mark_failed(session_maker, job_id, exc, "max_retries_exceeded"))
                raise
            _run(_mark_retrying(session_maker, job_id, exc))
            raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))
    finally:
        correlation_id_var.reset(t1)
        job_id_var.reset(t2)
