from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import Dict, Any
from datetime import datetime, timezone

from src.core.database import get_db
from src.db.models.document import Document, DocumentStatus
from src.db.models.processing_job import ProcessingJob, JobStatus
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.db.models.field_correction import FieldCorrection
from src.api.routes.auth import get_current_user
from src.schemas.auth import UserResponse

router = APIRouter()

@router.get("/metrics", response_model=Dict[str, Any])
async def get_analytics_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    # Enforce RBAC: Only Admin/Supervisor can see global operational metrics
    if current_user.role not in ["ADMIN", "SUPERVISOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view analytics"
        )
        
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Documents
    total_docs = await db.scalar(select(func.count()).select_from(Document))
    docs_today = await db.scalar(
        select(func.count()).select_from(Document)
        .where(Document.uploaded_at >= today)
    )
    
    # Processing Jobs
    jobs_succeeded = await db.scalar(
        select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status == JobStatus.SUCCEEDED)
    )
    jobs_failed = await db.scalar(
        select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status == JobStatus.FAILED)
    )
    jobs_retrying = await db.scalar(
        select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status == JobStatus.RETRYING)
    )
    
    # Validation outcomes (from Documents to reflect final status before review)
    auto_accepted = await db.scalar(
        select(func.count()).select_from(Document).where(Document.status == DocumentStatus.AUTO_ACCEPTED)
    )
    review_required = await db.scalar(
        select(func.count()).select_from(Document).where(Document.status == DocumentStatus.REVIEW_REQUIRED)
    )
    
    # Review outcomes
    human_approved = await db.scalar(
        select(func.count()).select_from(Document).where(Document.status == DocumentStatus.APPROVED)
    )
    human_rejected = await db.scalar(
        select(func.count()).select_from(Document).where(Document.status == DocumentStatus.REJECTED)
    )
    
    # Extraction Fallbacks
    # Count extractions where fallback_metadata is not null and has original_extractor
    fallback_count = await db.scalar(
        select(func.count()).select_from(Extraction)
        .where(Extraction.fallback_metadata.is_not(None))
    )
    
    # Human Correction Rate
    # Rate = (Documents containing at least one FieldCorrection) / (completed human reviews)
    completed_reviews = human_approved + human_rejected
    
    if completed_reviews > 0:
        docs_with_corrections = await db.scalar(
            select(func.count(func.distinct(Extraction.document_id)))
            .select_from(Extraction)
            .join(ExtractedField, ExtractedField.extraction_id == Extraction.id)
            .join(FieldCorrection, FieldCorrection.field_id == ExtractedField.id)
        )
        correction_rate = docs_with_corrections / completed_reviews
    else:
        docs_with_corrections = 0
        correction_rate = 0.0
        
    # Distributions
    status_distribution_raw = await db.execute(
        select(Document.status, func.count()).group_by(Document.status)
    )
    status_distribution = [{"name": str(r[0]), "value": r[1]} for r in status_distribution_raw.all()]
    
    type_distribution_raw = await db.execute(
        select(Document.doc_type, func.count()).group_by(Document.doc_type)
    )
    type_distribution = [{"name": str(r[0] or 'Unknown'), "value": r[1]} for r in type_distribution_raw.all()]
    
    # Confidence distribution (rough buckets)
    # Using case to bucket:
    confidence_distribution_raw = await db.execute(
        select(
            case(
                (Extraction.confidence_score >= 0.9, '90-100%'),
                (Extraction.confidence_score >= 0.7, '70-90%'),
                (Extraction.confidence_score >= 0.5, '50-70%'),
                else_='<50%'
            ).label('bucket'),
            func.count()
        ).select_from(Extraction).group_by('bucket')
    )
    confidence_distribution = [{"name": str(r[0]), "count": r[1]} for r in confidence_distribution_raw.all()]

    return {
        "documents": {
            "total": total_docs or 0,
            "processed_today": docs_today or 0
        },
        "processing": {
            "succeeded": jobs_succeeded or 0,
            "failed": jobs_failed or 0,
            "retrying": jobs_retrying or 0
        },
        "validation": {
            "auto_accepted": auto_accepted or 0,
            "review_required": review_required or 0
        },
        "review": {
            "human_approved": human_approved or 0,
            "human_rejected": human_rejected or 0,
            "correction_rate": float(correction_rate),
            "docs_with_corrections": docs_with_corrections
        },
        "extraction": {
            "fallback_count": fallback_count or 0
        },
        "distributions": {
            "status": status_distribution,
            "type": type_distribution,
            "confidence": confidence_distribution
        }
    }
