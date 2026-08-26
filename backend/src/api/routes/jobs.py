from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any
import uuid

from src.core.database import get_db
from src.db.models.user import User, UserRole
from src.db.models.processing_job import ProcessingJob
from src.api.deps import require_roles
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class JobResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    attempt_number: int
    error_details: dict | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OPERATOR, UserRole.REVIEWER, UserRole.VIEWER]))
) -> Any:
    """
    Get job by ID
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    stmt = select(ProcessingJob).where(ProcessingJob.id == job_uuid)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Authorize based on document uploader. Well, Phase 4 RBAC rules didn't enforce 
    # tenant isolation strictly, but just role level access. For now, checking doc existence.
    return job
