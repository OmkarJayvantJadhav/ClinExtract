from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum, ForeignKey, DateTime
import enum
import uuid
from datetime import datetime
from src.db.base import BaseModel

class ReviewStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class Review(BaseModel):
    __tablename__ = "reviews"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus, name="review_status_enum"), default=ReviewStatus.NOT_STARTED)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews")
    field_corrections = relationship("FieldCorrection", back_populates="review")
