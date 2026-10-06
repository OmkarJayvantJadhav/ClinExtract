import os
import uuid
from urllib.parse import quote
from typing import Any

import filetype
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.logging import get_logger
from src.db.models.user import User, UserRole
from src.db.models.document import Document, DocumentStatus
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.db.models.processing_job import ProcessingJob, JobStatus
from src.schemas.document import DocumentResponse, DocumentDetailResponse, DocumentListItem, PaginatedDocumentResponse
from src.api.deps import require_roles
from src.storage import get_storage_service, StorageService
from src.services.audit import log_audit_event, RESOURCE_DOCUMENT

router = APIRouter()
logger = get_logger(__name__)

ALL_ROLES = [UserRole.ADMIN, UserRole.OPERATOR, UserRole.REVIEWER, UserRole.VIEWER]
PAGE_RENDER_DPI = 150

def _list_item(doc: Document) -> DocumentListItem:
    item = DocumentListItem.model_validate(doc)
    extraction = doc.extractions[0] if doc.extractions else None
    if extraction:
        if extraction.overall_confidence is not None:
            item.overall_confidence = round(extraction.overall_confidence * 100, 1)
        values = {f.field_name: f.current_value for f in extraction.extracted_fields}
        item.patient_name = values.get("patient_name")
        item.patient_id = values.get("patient_id")
    return item

@router.get("", response_model=PaginatedDocumentResponse)
async def list_documents(
    status: DocumentStatus | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES))
) -> Any:
    """
    Get paginated list of documents
    """
    query = select(Document)
    if status:
        query = query.where(Document.status == status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()

    query = (
        query.order_by(Document.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .options(selectinload(Document.extractions).selectinload(Extraction.extracted_fields).selectinload(ExtractedField.field_corrections))
    )
    docs = (await db.execute(query)).scalars().all()
    items = [_list_item(d) for d in docs]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }

@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OPERATOR])),
    storage: StorageService = Depends(get_storage_service)
) -> Any:
    """
    Upload a new clinical document.
    Must be PDF, PNG, JPEG, and under 10MB.
    Stores the binary in volume and creates the database records.
    """
    correlation_id = getattr(request.state, "correlation_id", None)

    try:
        storage_key, mime_type, file_size = await storage.store_document(file)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Storage error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store the uploaded file"
        )

    safe_filename = os.path.basename(file.filename or "upload")
    try:
        new_doc = Document(
            uploader_id=current_user.id,
            filename=safe_filename,
            storage_key=storage_key,
            status=DocumentStatus.UPLOADED
        )
        db.add(new_doc)
        await db.flush()  # To get new_doc.id

        new_job = ProcessingJob(
            document_id=new_doc.id,
            status=JobStatus.QUEUED,
            correlation_id=correlation_id
        )
        db.add(new_job)

        await log_audit_event(
            db, action="DOCUMENT_UPLOADED", resource_type=RESOURCE_DOCUMENT, resource_id=str(new_doc.id),
            user_id=current_user.id, correlation_id=correlation_id,
            after_state={"status": DocumentStatus.UPLOADED.value, "filename": safe_filename,
                         "mime_type": mime_type, "size_bytes": file_size}
        )
        await db.commit()
    except Exception:
        # Don't leave an orphaned file behind if the database write failed
        await db.rollback()
        await storage.backend.delete_file(storage_key)
        raise

    await db.refresh(new_doc)
    await db.refresh(new_job)

    # Enqueue the Celery task
    from src.worker.tasks import process_document_job
    try:
        process_document_job.delay(str(new_job.id), correlation_id)
    except Exception as e:
        logger.error(f"Failed to enqueue processing job {new_job.id}: {e}")
        new_job.status = JobStatus.FAILED
        new_job.error_details = {"error": "Could not enqueue processing job", "step": "enqueue"}
        new_doc.status = DocumentStatus.FAILED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document stored but processing could not be queued. Please retry later."
        )

    return new_doc

async def _get_document_or_404(db: AsyncSession, document_id: uuid.UUID) -> Document:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES))
) -> Any:
    """
    Get document by ID
    """
    stmt = select(Document).options(
        selectinload(Document.extractions).selectinload(Extraction.extracted_fields).selectinload(ExtractedField.field_corrections)
    ).where(Document.id == document_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

async def _read_document_bytes(storage: StorageService, doc: Document) -> bytes:
    try:
        stream = await storage.backend.get_file(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found in storage")
    try:
        return stream.read()
    finally:
        stream.close()

@router.get("/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
    storage: StorageService = Depends(get_storage_service)
):
    """Download the original uploaded file."""
    doc = await _get_document_or_404(db, document_id)
    data = await _read_document_bytes(storage, doc)
    kind = filetype.guess(data)
    return Response(
        content=data,
        media_type=kind.mime if kind else "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

@router.get("/{document_id}/pages/{page_number}/image")
async def get_document_page_image(
    document_id: uuid.UUID,
    page_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
    storage: StorageService = Depends(get_storage_service)
):
    """
    Render one page of the original document as PNG (1-based page number), in the same
    coordinate frame as the extracted bounding boxes, for the review viewer.
    """
    doc = await _get_document_or_404(db, document_id)
    data = await _read_document_bytes(storage, doc)
    kind = filetype.guess(data)
    mime = kind.mime if kind else None
    headers = {"Cache-Control": "private, no-store"}

    if mime in ("image/png", "image/jpeg"):
        if page_number != 1:
            raise HTTPException(status_code=404, detail="Page not found")
        return Response(content=data, media_type=mime, headers=headers)

    if mime == "application/pdf":
        import fitz
        try:
            pdf = fitz.open(stream=data, filetype="pdf")
        except Exception:
            raise HTTPException(status_code=422, detail="Document cannot be rendered")
        try:
            if page_number < 1 or page_number > pdf.page_count:
                raise HTTPException(status_code=404, detail="Page not found")
            zoom = PAGE_RENDER_DPI / 72.0
            pix = pdf[page_number - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            png = pix.tobytes("png")
        finally:
            pdf.close()
        return Response(content=png, media_type="image/png", headers=headers)

    raise HTTPException(status_code=415, detail="Unsupported document type")

@router.get("/{document_id}/pages")
async def get_document_page_count(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
    storage: StorageService = Depends(get_storage_service)
):
    """Number of renderable pages for the review viewer."""
    doc = await _get_document_or_404(db, document_id)
    data = await _read_document_bytes(storage, doc)
    kind = filetype.guess(data)
    if kind and kind.mime == "application/pdf":
        import fitz
        try:
            with fitz.open(stream=data, filetype="pdf") as pdf:
                return {"page_count": pdf.page_count}
        except Exception:
            raise HTTPException(status_code=422, detail="Document cannot be rendered")
    return {"page_count": 1}
