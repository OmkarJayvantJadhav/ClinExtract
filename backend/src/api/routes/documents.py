from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from src.core.database import get_db
from src.db.models.user import User, UserRole
from src.db.models.document import Document, DocumentStatus
from src.db.models.extraction import Extraction
from src.db.models.processing_job import ProcessingJob, JobStatus
from src.schemas.document import DocumentResponse, DocumentDetailResponse, PaginatedDocumentResponse
from src.api.deps import require_roles
from src.storage import get_storage_service, StorageService

router = APIRouter()

@router.get("", response_model=PaginatedDocumentResponse)
async def list_documents(
    status: DocumentStatus | None = None,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OPERATOR, UserRole.REVIEWER, UserRole.VIEWER]))
) -> Any:
    """
    Get paginated list of documents
    """
    from sqlalchemy import func
    
    query = select(Document)
    if status:
        query = query.where(Document.status == status)
        
    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()
    
    # Get items
    query = query.order_by(Document.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()
    
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
    
    # Store document using StorageService abstraction
    try:
        storage_key, mime_type, file_size = await storage.store_document(file)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage error: {str(e)}"
        )
    
    import os
    
    # Create Document record
    safe_filename = os.path.basename(file.filename)
    new_doc = Document(
        uploader_id=current_user.id,
        filename=safe_filename,
        storage_key=storage_key,
        status=DocumentStatus.UPLOADED
    )
    db.add(new_doc)
    await db.flush()  # To get new_doc.id

    # Create initial ProcessingJob record
    new_job = ProcessingJob(
        document_id=new_doc.id,
        status=JobStatus.QUEUED,
        correlation_id=correlation_id
    )
    db.add(new_job)

    await db.commit()
    await db.refresh(new_doc)
    await db.refresh(new_job)

    # Enqueue the Celery task
    from src.worker.tasks import process_document_job
    process_document_job.delay(str(new_job.id), correlation_id)

    return new_doc

@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OPERATOR, UserRole.REVIEWER, UserRole.VIEWER]))
) -> Any:
    """
    Get document by ID
    """
    import uuid
    from sqlalchemy.orm import selectinload
    from src.db.models.extracted_field import ExtractedField
    stmt = select(Document).options(
        selectinload(Document.extractions).selectinload(Extraction.extracted_fields).selectinload(ExtractedField.field_corrections)
    ).where(Document.id == uuid.UUID(document_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
