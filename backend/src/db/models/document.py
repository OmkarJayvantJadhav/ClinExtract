from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Enum, ForeignKey
import enum
import uuid
from src.db.base import BaseModel

class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    FAILED = "FAILED"

class Document(BaseModel):
    __tablename__ = "documents"

    uploader_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(String, unique=True)
    doc_type: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus, name="document_status_enum"), default=DocumentStatus.UPLOADED)

    uploader = relationship("User", back_populates="documents")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")
    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="document", cascade="all, delete-orphan")
