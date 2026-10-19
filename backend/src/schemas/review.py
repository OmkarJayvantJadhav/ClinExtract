from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from src.db.models.review import ReviewStatus

class FieldCorrectionCreate(BaseModel):
    extracted_field_id: UUID
    new_value: Optional[str] = None
    # A corrected unit; None leaves the unit unchanged
    new_unit: Optional[str] = None
    reason: Optional[str] = None

class ReviewCompleteRequest(BaseModel):
    review_id: UUID
    decision: str  # HUMAN_APPROVED or HUMAN_REJECTED
    corrections: List[FieldCorrectionCreate]
    rejection_reason: Optional[str] = None
    # The reviewer has seen the warnings their corrections raised (returned by a first attempt)
    confirm_warnings: bool = False

class FieldCorrectionResponse(BaseModel):
    id: UUID
    extracted_field_id: UUID
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    previous_unit: Optional[str] = None
    new_unit: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ReviewResponse(BaseModel):
    id: UUID
    document_id: UUID
    reviewer_id: Optional[UUID] = None
    status: ReviewStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    field_corrections: List[FieldCorrectionResponse] = []

    model_config = ConfigDict(from_attributes=True)
