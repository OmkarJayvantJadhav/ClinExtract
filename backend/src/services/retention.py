"""
Document deletion and retention.

Purging removes the stored file, its OCR artifact and every database row derived from the
document. Audit entries are kept (who did what, when) but their before/after payloads are
redacted, because they can contain patient data (field values, filenames, rejection reasons).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, delete, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit_log import AuditLog
from src.db.models.document import Document, DocumentStatus
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.db.models.field_correction import FieldCorrection
from src.db.models.processing_job import ProcessingJob
from src.db.models.review import Review
from src.services.audit import log_audit_event, RESOURCE_DOCUMENT, RESOURCE_EXTRACTED_FIELD
from src.storage.service import StorageService

FINAL_STATUSES = (
    DocumentStatus.AUTO_ACCEPTED,
    DocumentStatus.HUMAN_APPROVED,
    DocumentStatus.HUMAN_REJECTED,
    DocumentStatus.FAILED,
)
REDACTED = {"redacted": True}

async def purge_document(
    db: AsyncSession,
    document: Document,
    actor_id: Optional[uuid.UUID],
    reason: str,
) -> str:
    """
    Deletes a document's database rows and redacts its audit payloads. The caller commits and
    then removes the files with `storage.delete_document_files(<returned storage key>)`, so a
    failed transaction never leaves rows pointing at deleted files.
    """
    doc_id = document.id
    doc_id_str = str(doc_id)
    storage_key = document.storage_key

    extraction_ids = select(Extraction.id).where(Extraction.document_id == doc_id)
    field_ids_q = select(ExtractedField.id).where(ExtractedField.extraction_id.in_(extraction_ids))
    field_ids = [str(fid) for fid in (await db.execute(field_ids_q)).scalars().all()]

    # Redact audit payloads that may contain PHI, keeping the events themselves
    await db.execute(
        update(AuditLog)
        .where(or_(
            and_(AuditLog.resource_type == RESOURCE_DOCUMENT, AuditLog.resource_id == doc_id_str),
            and_(AuditLog.resource_type == RESOURCE_EXTRACTED_FIELD, AuditLog.resource_id.in_(field_ids or [""])),
        ))
        .values(before_state=None, after_state=REDACTED)
    )

    # Children first (explicit deletes avoid relying on lazy-loaded ORM cascades under asyncio)
    await db.execute(delete(FieldCorrection).where(FieldCorrection.extracted_field_id.in_(field_ids_q)))
    await db.execute(delete(ExtractedField).where(ExtractedField.extraction_id.in_(extraction_ids)))
    await db.execute(delete(Extraction).where(Extraction.document_id == doc_id))
    await db.execute(delete(Review).where(Review.document_id == doc_id))
    await db.execute(delete(ProcessingJob).where(ProcessingJob.document_id == doc_id))
    await db.execute(delete(Document).where(Document.id == doc_id))

    await log_audit_event(
        db, action="DOCUMENT_DELETED", resource_type=RESOURCE_DOCUMENT, resource_id=doc_id_str,
        user_id=actor_id, after_state={"reason": reason},
    )
    return storage_key

async def purge_expired_documents(db: AsyncSession, storage: StorageService, retention_days: int, now: Optional[datetime] = None) -> int:
    """Purges finalized documents older than `retention_days`. Returns how many were removed."""
    if retention_days <= 0:
        return 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    stmt = select(Document).where(Document.status.in_(FINAL_STATUSES), Document.created_at < cutoff).limit(500)
    documents = (await db.execute(stmt)).scalars().all()
    for document in documents:
        storage_key = await purge_document(db, document, actor_id=None, reason=f"retention policy ({retention_days} days)")
        await db.commit()
        # Files are removed only after the rows are gone; an orphaned file is encrypted and harmless
        await storage.delete_document_files(storage_key)
    return len(documents)
