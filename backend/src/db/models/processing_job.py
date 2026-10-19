from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum, ForeignKey, JSON, String
import enum
import uuid
from src.db.base import BaseModel

class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

class ProcessingJob(BaseModel):
    __tablename__ = "processing_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status_enum"), index=True, default=JobStatus.QUEUED)
    attempt_number: Mapped[int] = mapped_column(default=1)
    # Times the stuck-job sweep restarted this job after its worker died mid-run
    recovery_count: Mapped[int] = mapped_column(default=0, server_default="0")
    error_details: Mapped[dict] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String, nullable=True, index=True)

    document = relationship("Document", back_populates="processing_jobs")
