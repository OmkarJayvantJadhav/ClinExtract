from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Float
from sqlalchemy.dialects.postgresql import JSONB
import uuid
from src.db.base import BaseModel

class Extraction(BaseModel):
    __tablename__ = "extractions"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    extractor_type: Mapped[str] = mapped_column(String, server_default="rule_based")
    model_version: Mapped[str] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String, nullable=True)
    fallback_metadata: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Phase 9 Validation Fields
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String, nullable=True)
    validation_summary: Mapped[dict] = mapped_column(JSONB, nullable=True)

    document = relationship("Document", back_populates="extractions")
    extracted_fields = relationship("ExtractedField", back_populates="extraction", cascade="all, delete-orphan")
