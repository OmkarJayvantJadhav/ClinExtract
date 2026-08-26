import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from src.core.database import get_db
from src.api.deps import require_roles
from src.db.models.user import User, UserRole
from src.db.models.document import Document
from src.db.models.review import Review, ReviewStatus
from src.db.models.field_correction import FieldCorrection
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.schemas.review import ReviewResponse, ReviewCompleteRequest
from src.services.audit import log_audit_event
from src.validation.engine import ValidationEngine

router = APIRouter(prefix="/reviews", tags=["reviews"])

@router.post("/{document_id}/claim", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def claim_review(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER]))
):
    # Lock the document
    stmt = select(Document).where(Document.id == document_id).with_for_update()
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if document.status != "REVIEW_REQUIRED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DOCUMENT_ALREADY_CLAIMED")
        
    # Check for existing active review
    active_review_stmt = select(Review).where(Review.document_id == document_id, Review.status == ReviewStatus.IN_PROGRESS)
    result = await db.execute(active_review_stmt)
    active_review = result.scalar_one_or_none()
    
    if active_review:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DOCUMENT_ALREADY_CLAIMED")
        
    # Create Review
    new_review = Review(
        id=uuid.uuid4(),
        document_id=document_id,
        reviewer_id=current_user.id,
        status=ReviewStatus.IN_PROGRESS
    )
    db.add(new_review)
    
    # Update Document status
    document.status = "REVIEW_IN_PROGRESS"
    
    # Log audit event
    await log_audit_event(
        db, action="DOCUMENT_REVIEW_CLAIMED", resource_type="Document", resource_id=str(document_id),
        user_id=current_user.id, after_state={"status": "REVIEW_IN_PROGRESS"}
    )
    
    await db.commit()
    
    # Eager load the field_corrections so Pydantic doesn't throw MissingGreenlet
    stmt = select(Review).options(selectinload(Review.field_corrections)).where(Review.id == new_review.id)
    result = await db.execute(stmt)
    new_review = result.scalar_one()
    
    return new_review

@router.post("/{document_id}/complete", response_model=ReviewResponse)
async def complete_review(
    document_id: uuid.UUID,
    request: ReviewCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER]))
):
    stmt = select(Review).options(selectinload(Review.field_corrections)).where(Review.id == request.review_id).with_for_update()
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.document_id != document_id:
        raise HTTPException(status_code=400, detail="Review does not belong to this document")
    if review.reviewer_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to complete this review")
    if review.status != ReviewStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Review is not in progress")
        
    doc_stmt = select(Document).options(
        selectinload(Document.extractions).selectinload(Extraction.extracted_fields).selectinload(ExtractedField.field_corrections)
    ).where(Document.id == document_id).with_for_update()
    result = await db.execute(doc_stmt)
    document = result.scalar_one()
    
    if document.status != "REVIEW_IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Document is not in progress")
        
    if request.decision == "HUMAN_REJECTED":
        if not request.rejection_reason:
            raise HTTPException(status_code=422, detail="Rejection reason is required")
            
        review.status = ReviewStatus.COMPLETED
        review.completed_at = datetime.now(timezone.utc)
        document.status = "HUMAN_REJECTED"
        
        await log_audit_event(
            db, action="DOCUMENT_HUMAN_REJECTED", resource_type="Document", resource_id=str(document_id),
            user_id=current_user.id, after_state={"status": "HUMAN_REJECTED", "reason": request.rejection_reason}
        )
        await db.commit()
        await db.refresh(review)
        return review
        
    elif request.decision == "HUMAN_APPROVED":
        extraction = document.extractions[0] if document.extractions else None
        if not extraction:
            raise HTTPException(status_code=400, detail="No extraction found for document")
            
        extracted_fields_map = {f.id: f for f in extraction.extracted_fields}
        
        engine = ValidationEngine()
        
        # We need to simulate the current values
        current_values = {f.field_name: f.value for f in extraction.extracted_fields}
        
        # Apply corrections
        field_corrections = []
        for corr in request.corrections:
            if corr.extracted_field_id not in extracted_fields_map:
                raise HTTPException(status_code=400, detail=f"Extracted field {corr.extracted_field_id} does not belong to this document")
                
            field = extracted_fields_map[corr.extracted_field_id]
            if corr.new_value != field.value:
                if not corr.reason:
                    raise HTTPException(status_code=422, detail=f"Reason required for changing field {field.field_name}")
                
                # We update our local dictionary of current_values to validate
                current_values[field.field_name] = corr.new_value
                
                fc = FieldCorrection(
                    id=uuid.uuid4(),
                    extracted_field_id=corr.extracted_field_id,
                    review_id=review.id,
                    previous_value=field.value,
                    new_value=corr.new_value,
                    reason=corr.reason
                )
                field.is_corrected = True
                field.field_corrections.append(fc)
                field_corrections.append(fc)
                db.add(fc)

                
                await log_audit_event(
                    db, action="FIELD_CORRECTED", resource_type="ExtractedField", resource_id=str(field.id),
                    user_id=current_user.id, before_state={"value": field.value}, after_state={"value": corr.new_value}
                )

        # Re-validate current values
        unresolved_issues = []
        for field in extraction.extracted_fields:
            current_val = current_values.get(field.field_name)
            # We skip source mismatch checking here for simplicity, or we could pass document_data=None
            state, messages, meta, norm_val = engine.validate_field(field.field_name, current_val)
            if state != "VALID":
                unresolved_issues.append({"field_name": field.field_name, "state": state, "messages": messages})
                
        if unresolved_issues:
            raise HTTPException(status_code=422, detail={
                "code": "UNRESOLVED_VALIDATION_ISSUES",
                "message": "There are unresolved validation issues.",
                "fields": unresolved_issues
            })
            
        review.status = ReviewStatus.COMPLETED
        review.completed_at = datetime.now(timezone.utc)
        document.status = "HUMAN_APPROVED"
        
        await log_audit_event(
            db, action="DOCUMENT_HUMAN_APPROVED", resource_type="Document", resource_id=str(document_id),
            user_id=current_user.id, after_state={"status": "HUMAN_APPROVED"}
        )
        
        await db.commit()
        
        # Eager load the new corrections
        stmt = select(Review).options(selectinload(Review.field_corrections)).where(Review.id == review.id)
        result = await db.execute(stmt)
        review = result.scalar_one()
        return review
        
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")

@router.post("/{document_id}/release", response_model=ReviewResponse)
async def release_review(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN]))
):
    stmt = select(Review).options(selectinload(Review.field_corrections)).where(Review.document_id == document_id, Review.status == ReviewStatus.IN_PROGRESS).with_for_update()
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="No active review found for this document")
        
    doc_stmt = select(Document).where(Document.id == document_id).with_for_update()
    result = await db.execute(doc_stmt)
    document = result.scalar_one()
    
    review.status = ReviewStatus.CANCELLED
    document.status = "REVIEW_REQUIRED"
    
    await log_audit_event(
        db, action="DOCUMENT_REVIEW_RELEASED", resource_type="Document", resource_id=str(document_id),
        user_id=current_user.id, after_state={"status": "REVIEW_REQUIRED"}
    )
    
    await db.commit()
    await db.refresh(review)
    return review

@router.get("/{document_id}", response_model=ReviewResponse)
async def get_review(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER, UserRole.OPERATOR]))
):
    stmt = select(Review).options(selectinload(Review.field_corrections)).where(
        Review.document_id == document_id, 
        Review.status == ReviewStatus.IN_PROGRESS
    )
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="No active review found")
        
    return review
