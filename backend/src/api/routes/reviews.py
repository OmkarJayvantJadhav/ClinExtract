import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from src.core.config import settings
from src.core.database import get_db
from src.api.deps import require_roles
from src.db.models.user import User, UserRole
from src.db.models.document import Document, DocumentStatus
from src.db.models.review import Review, ReviewStatus
from src.db.models.field_correction import FieldCorrection
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField
from src.schemas.review import ReviewResponse, ReviewCompleteRequest
from src.services.audit import log_audit_event, RESOURCE_DOCUMENT, RESOURCE_EXTRACTED_FIELD
from src.validation.engine import ValidationEngine, BLOCKING_STATES, VALIDATED_FIELDS
from src.services.system_settings import get_thresholds

router = APIRouter(prefix="/reviews", tags=["reviews"])

REVIEW_ROLES = [UserRole.ADMIN, UserRole.REVIEWER]

def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _claim_expired(review: Review) -> bool:
    last_activity = _as_aware(review.updated_at or review.created_at)
    return last_activity < datetime.now(timezone.utc) - timedelta(minutes=settings.REVIEW_CLAIM_TIMEOUT_MINUTES)

async def _load_review(db: AsyncSession, review_id: uuid.UUID) -> Review:
    stmt = (
        select(Review)
        .options(selectinload(Review.field_corrections))
        .where(Review.id == review_id)
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one()

async def _lock_document(db: AsyncSession, document_id: uuid.UUID) -> Document:
    # Always lock the document row first so every review endpoint acquires locks in the same order.
    stmt = select(Document).where(Document.id == document_id).with_for_update()
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

async def _active_review(db: AsyncSession, document_id: uuid.UUID) -> Review | None:
    stmt = select(Review).where(Review.document_id == document_id, Review.status == ReviewStatus.IN_PROGRESS).with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()

@router.post("/{document_id}/claim", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def claim_review(
    document_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(REVIEW_ROLES))
):
    document = await _lock_document(db, document_id)
    active_review = await _active_review(db, document_id)

    if active_review:
        if active_review.reviewer_id == current_user.id:
            # Re-entrant: the same reviewer reopening the workspace (e.g. after a reload)
            response.status_code = status.HTTP_200_OK
            return await _load_review(db, active_review.id)
        if not _claim_expired(active_review):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DOCUMENT_ALREADY_CLAIMED")
        # Abandoned claim: release it so the document can be reviewed again
        active_review.status = ReviewStatus.CANCELLED
        document.status = DocumentStatus.REVIEW_REQUIRED
        await log_audit_event(
            db, action="DOCUMENT_REVIEW_EXPIRED", resource_type=RESOURCE_DOCUMENT, resource_id=str(document_id),
            user_id=current_user.id,
            before_state={"review_id": str(active_review.id), "reviewer_id": str(active_review.reviewer_id)},
            after_state={"status": DocumentStatus.REVIEW_REQUIRED.value}
        )

    if document.status != DocumentStatus.REVIEW_REQUIRED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"DOCUMENT_NOT_REVIEWABLE: document status is {document.status.value}"
        )

    new_review = Review(
        id=uuid.uuid4(),
        document_id=document_id,
        reviewer_id=current_user.id,
        status=ReviewStatus.IN_PROGRESS
    )
    db.add(new_review)
    document.status = DocumentStatus.REVIEW_IN_PROGRESS

    await log_audit_event(
        db, action="DOCUMENT_REVIEW_CLAIMED", resource_type=RESOURCE_DOCUMENT, resource_id=str(document_id),
        user_id=current_user.id, after_state={"status": DocumentStatus.REVIEW_IN_PROGRESS.value}
    )

    await db.commit()
    return await _load_review(db, new_review.id)

@router.post("/{document_id}/complete", response_model=ReviewResponse)
async def complete_review(
    document_id: uuid.UUID,
    request: ReviewCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(REVIEW_ROLES))
):
    document = await _lock_document(db, document_id)

    review_stmt = select(Review).options(selectinload(Review.field_corrections)).where(Review.id == request.review_id).with_for_update()
    review = (await db.execute(review_stmt)).scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.document_id != document_id:
        raise HTTPException(status_code=400, detail="Review does not belong to this document")
    if review.reviewer_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to complete this review")
    if review.status != ReviewStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Review is not in progress (it may have expired or been released)")
    if document.status != DocumentStatus.REVIEW_IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Document is not in review")

    if request.decision == "HUMAN_REJECTED":
        if not request.rejection_reason or not request.rejection_reason.strip():
            raise HTTPException(status_code=422, detail="Rejection reason is required")

        review.status = ReviewStatus.COMPLETED
        review.completed_at = datetime.now(timezone.utc)
        document.status = DocumentStatus.HUMAN_REJECTED

        await log_audit_event(
            db, action="DOCUMENT_HUMAN_REJECTED", resource_type=RESOURCE_DOCUMENT, resource_id=str(document_id),
            user_id=current_user.id, after_state={"status": DocumentStatus.HUMAN_REJECTED.value, "reason": request.rejection_reason}
        )
        await db.commit()
        return await _load_review(db, review.id)

    if request.decision != "HUMAN_APPROVED":
        raise HTTPException(status_code=400, detail="Invalid decision")

    # Current extraction (Document.extractions is ordered newest first)
    extraction_stmt = (
        select(Extraction)
        .options(selectinload(Extraction.extracted_fields).selectinload(ExtractedField.field_corrections))
        .where(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    extraction = (await db.execute(extraction_stmt)).scalar_one_or_none()
    if not extraction:
        raise HTTPException(status_code=400, detail="No extraction found for document")

    fields_by_id = {f.id: f for f in extraction.extracted_fields}
    # Keyed by field id (not name) so duplicate field names cannot overwrite each other
    current_values = {f.id: f.current_value for f in extraction.extracted_fields}

    pending_corrections = []
    for corr in request.corrections:
        field = fields_by_id.get(corr.extracted_field_id)
        if field is None:
            raise HTTPException(status_code=400, detail=f"Extracted field {corr.extracted_field_id} does not belong to this document")
        if corr.new_value == current_values[field.id]:
            continue  # Confirmation of the existing value, nothing to record
        if not corr.reason or not corr.reason.strip():
            raise HTTPException(status_code=422, detail=f"Reason required for changing field {field.field_name}")
        pending_corrections.append((field, corr))
        current_values[field.id] = corr.new_value

    # Re-validate the final values. Only unusable values block approval; abnormal-but-valid
    # results (e.g. OUTSIDE_REFERENCE_RANGE) are confirmed by the reviewer's approval.
    engine = ValidationEngine.from_thresholds(await get_thresholds(db))
    values_by_name = {}
    for field in extraction.extracted_fields:
        values_by_name.setdefault(field.field_name, current_values[field.id])
    context = engine.build_context(values_by_name)
    results = {}
    for field in extraction.extracted_fields:
        if field.field_name not in VALIDATED_FIELDS:
            continue
        results[field.id] = engine.validate_field(field.field_name, current_values[field.id], field.unit, context)

    inconsistencies = engine.check_cross_field(
        (fields_by_id[fid].field_name, res[0], res[3]) for fid, res in results.items()
    )

    blocking_issues = []
    warnings = []
    for fid, (state, messages, meta, norm_val) in results.items():
        name = fields_by_id[fid].field_name
        if state in BLOCKING_STATES:
            blocking_issues.append({"field_id": str(fid), "field_name": name, "state": state, "messages": messages})
        elif state != "VALID":
            warnings.append({"field_name": name, "state": state})
        if state == "VALID" and name in inconsistencies:
            warnings.append({"field_name": name, "state": "INCONSISTENT_DATES"})

    if blocking_issues:
        raise HTTPException(status_code=422, detail={
            "code": "UNRESOLVED_VALIDATION_ISSUES",
            "message": "Some fields are missing or invalid and must be corrected before approval.",
            "fields": blocking_issues
        })

    # Persist corrections
    for field, corr in pending_corrections:
        previous = field.current_value
        fc = FieldCorrection(
            id=uuid.uuid4(),
            extracted_field_id=field.id,
            review_id=review.id,
            previous_value=previous,
            new_value=corr.new_value,
            reason=corr.reason
        )
        db.add(fc)
        field.field_corrections.append(fc)
        field.is_corrected = True
        await log_audit_event(
            db, action="FIELD_CORRECTED", resource_type=RESOURCE_EXTRACTED_FIELD, resource_id=str(field.id),
            user_id=current_user.id,
            before_state={"value": previous, "document_id": str(document_id), "field_name": field.field_name},
            after_state={"value": corr.new_value, "reason": corr.reason}
        )

    # Store the post-review validation outcome on each field. `value` keeps the original
    # extracted text for provenance; `current_value` / `normalized_value` reflect the review.
    for fid, (state, messages, meta, norm_val) in results.items():
        field = fields_by_id[fid]
        field.normalized_value = norm_val
        field.validation_state = state
        field.validation_messages = messages
        field.validation_metadata = meta
        field.is_valid = state == "VALID"

    review.status = ReviewStatus.COMPLETED
    review.completed_at = datetime.now(timezone.utc)
    document.status = DocumentStatus.HUMAN_APPROVED

    await log_audit_event(
        db, action="DOCUMENT_HUMAN_APPROVED", resource_type=RESOURCE_DOCUMENT, resource_id=str(document_id),
        user_id=current_user.id,
        after_state={
            "status": DocumentStatus.HUMAN_APPROVED.value,
            "corrections": len(pending_corrections),
            "confirmed_warnings": warnings,
        }
    )

    await db.commit()
    return await _load_review(db, review.id)

@router.post("/{document_id}/release", response_model=ReviewResponse)
async def release_review(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(REVIEW_ROLES))
):
    document = await _lock_document(db, document_id)
    review = await _active_review(db, document_id)

    if not review:
        raise HTTPException(status_code=404, detail="No active review found for this document")
    if review.reviewer_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only the assigned reviewer or an admin can release this review")

    review.status = ReviewStatus.CANCELLED
    document.status = DocumentStatus.REVIEW_REQUIRED

    await log_audit_event(
        db, action="DOCUMENT_REVIEW_RELEASED", resource_type=RESOURCE_DOCUMENT, resource_id=str(document_id),
        user_id=current_user.id, after_state={"status": DocumentStatus.REVIEW_REQUIRED.value}
    )

    await db.commit()
    return await _load_review(db, review.id)

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
    review = (await db.execute(stmt)).scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="No active review found")

    return review
