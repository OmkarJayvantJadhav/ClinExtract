import asyncio
import uuid
import sys
from src.worker.celery_app import celery_app
from src.core.database import async_session_maker
from src.db.models.processing_job import ProcessingJob, JobStatus
from src.db.models.document import Document, DocumentStatus
from sqlalchemy import select
from src.core.logging import correlation_id_var, document_id_var, job_id_var, get_logger

logger = get_logger(__name__)

async def process_document_async(job_id: str):
    job_uuid = uuid.UUID(job_id)
    
    async with async_session_maker() as session:
        # 1. Transaction A: Lock job and document, verify, set RUNNING/PROCESSING
        stmt = select(ProcessingJob).where(ProcessingJob.id == job_uuid).with_for_update()
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            return "Job not found"
            
        if job.status not in [JobStatus.QUEUED, JobStatus.RETRYING]:
            return "Job already processed or locked"
            
        job.status = JobStatus.RUNNING
        job.attempt_number += 1
        
        # 2. Extract Document from DB
        doc_stmt = select(Document).where(Document.id == job.document_id).with_for_update()
        doc_result = await session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()
        
        if not document:
            return "Document not found"
            
        document.status = DocumentStatus.PROCESSING
        storage_key = document.storage_key
        doc_id_str = str(document.id)
        
        document_id_var.set(doc_id_str)
        
        await session.commit()
        
    # 2. Actual Preprocessing & OCR
    try:
        from src.storage import get_storage_service
        import json
        
        storage = get_storage_service()
        file_stream = await storage.backend.get_file(storage_key)
        file_bytes = file_stream.read()
        file_stream.close()
        
        # Determine mime type from extension or use python-magic here, but doc.doc_type isn't strictly mime.
        # Let's use filetype to be safe, or just pass it if we know. We can guess it.
        import filetype
        kind = filetype.guess(file_bytes)
        mime_type = kind.mime if kind else "application/pdf"
        
        from src.processing.analyzer import DocumentAnalyzer
        artifact = DocumentAnalyzer.process(file_bytes, mime_type, doc_id_str, str(job_uuid))
        
        artifact_json = json.dumps(artifact, indent=2)
        await storage.store_artifact(storage_key, artifact_json)
        
    except Exception as e:
        raise e
        
    # Phase 8 & 9: Extraction and Validation
    try:
        from src.extraction.service import ExtractionService
        from src.extraction.factory import ExtractionFactory
        from src.validation.engine import ValidationEngine
        from src.core.config import settings
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Load extractor from factory
        provider_name = settings.EXTRACTION_PROVIDER
        extractor = ExtractionFactory.get_extractor(provider_name)
        service = ExtractionService(extractor)
        validation_engine = ValidationEngine()
        
        async with async_session_maker() as session_ext:
            try:
                extraction = await service.process_extraction(session_ext, doc_id_str, artifact, metadata={"image_bytes": file_bytes})
            except Exception as ext_err:
                from src.extraction.exceptions import NonRetryableExtractionError
                logger.error(f"Primary extractor failed: {ext_err}")
                if settings.EXTRACTION_FALLBACK_ENABLED and provider_name != "rule_based" and not isinstance(ext_err, NonRetryableExtractionError):
                    logger.info("Fallback enabled. Attempting RuleBasedExtractor.")
                    fallback_extractor = ExtractionFactory.get_extractor("rule_based")
                    service = ExtractionService(fallback_extractor)
                    extraction = await service.process_extraction(
                        session_ext, 
                        doc_id_str, 
                        artifact, 
                        metadata={
                            "image_bytes": file_bytes,
                            "fallback_reason": str(ext_err),
                            "original_extractor": provider_name,
                            "fallback_extractor": "rule_based"
                        }
                    )
                else:
                    raise ext_err
            
            # Phase 9: Validation
            validation_engine.validate_extraction(extraction, artifact)
            session_ext.add(extraction)
            await session_ext.commit()
            
            final_decision = extraction.decision
            
    except Exception as e:
        raise e
    
    # 3. Transaction B: Mark success and update Document status
    async with async_session_maker() as session2:
        job2 = await session2.get(ProcessingJob, job_uuid)
        if job2:
            job2.status = JobStatus.SUCCEEDED
            
        doc = await session2.get(Document, uuid.UUID(doc_id_str))
        if doc:
            if final_decision == "AUTO_ACCEPTED":
                doc.status = DocumentStatus.AUTO_ACCEPTED
            else:
                doc.status = DocumentStatus.REVIEW_REQUIRED
                
        await session2.commit()
        
    return f"Job {job_id} processed successfully. Decision: {final_decision}"

@celery_app.task(bind=True, name="process_document_job", max_retries=3, acks_late=True)
def process_document_job(self, job_id: str, correlation_id: str = None):
    """
    Synchronous Celery task that wraps the async processor.
    """
    t1 = correlation_id_var.set(correlation_id if correlation_id else str(uuid.uuid4()))
    t2 = job_id_var.set(job_id)
    
    try:
        logger.info("Starting processing job", extra={"event": "job_started"})
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        try:
            try:
                loop = asyncio.get_running_loop()
                res = loop.create_task(process_document_async(job_id))
                return res
            except RuntimeError:
                res = asyncio.run(process_document_async(job_id))
                return res
        except Exception as exc:
            from src.extraction.exceptions import NonRetryableExtractionError
            # If it's a non-retryable error, fail immediately without Celery retries
            if isinstance(exc, NonRetryableExtractionError):
                async def fail_job_non_retryable():
                    async with async_session_maker() as session:
                        stmt = select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id)).with_for_update()
                        result = await session.execute(stmt)
                        job = result.scalar_one_or_none()
                        if job:
                            job.status = JobStatus.FAILED
                            job.error_details = {"error": str(exc), "step": "extraction_non_retryable"}
                            
                            doc = await session.get(Document, job.document_id)
                            if doc:
                                doc.status = DocumentStatus.FAILED
                                
                            await session.commit()
                
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(fail_job_non_retryable())
                except RuntimeError:
                    asyncio.run(fail_job_non_retryable())
                return
                
            async def mark_retrying():
                async with async_session_maker() as session:
                    stmt = select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id)).with_for_update()
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = JobStatus.RETRYING
                        await session.commit()

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(mark_retrying())
            except RuntimeError:
                asyncio.run(mark_retrying())

            try:
                self.retry(exc=exc, countdown=5)
            except self.MaxRetriesExceededError:
                # Update DB to FAILED if max retries exceeded
                async def fail_job():
                    async with async_session_maker() as session:
                        stmt = select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id)).with_for_update()
                        result = await session.execute(stmt)
                        job = result.scalar_one_or_none()
                        if job:
                            job.status = JobStatus.FAILED
                            job.error_details = {"error": str(exc)}
                            
                            doc = await session.get(Document, job.document_id)
                            if doc:
                                doc.status = DocumentStatus.FAILED
                                
                            await session.commit()
                if sys.platform == "win32":
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(fail_job())
                except RuntimeError:
                    asyncio.run(fail_job())
                raise
    finally:
        correlation_id_var.reset(t1)
        job_id_var.reset(t2)
