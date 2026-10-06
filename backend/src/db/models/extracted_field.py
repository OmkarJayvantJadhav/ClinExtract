from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Float, Boolean, Integer
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
import uuid
from src.db.base import BaseModel

class ExtractedField(BaseModel):
    __tablename__ = "extracted_fields"

    extraction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extractions.id"))
    field_name: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String, nullable=True)
    unit: Mapped[str] = mapped_column(String, nullable=True)
    
    # Phase 9 fields
    normalized_value: Mapped[str] = mapped_column(String, nullable=True)
    validation_state: Mapped[str] = mapped_column(String, nullable=True)
    validation_messages: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    confidence_category: Mapped[str] = mapped_column(String, nullable=True)
    validation_metadata: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    page_num: Mapped[int] = mapped_column(Integer, nullable=True)
    bbox_normalized: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=True)
    is_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    extraction = relationship("Extraction", back_populates="extracted_fields")
    field_corrections = relationship("FieldCorrection", back_populates="extracted_field", order_by="FieldCorrection.created_at", cascade="all, delete-orphan")

    @property
    def current_value(self) -> str:
        if self.is_corrected and self.field_corrections:
            return self.field_corrections[-1].new_value
        return self.value
        
    @property
    def original_value(self) -> str:
        return self.value
