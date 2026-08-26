from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
import uuid
from src.db.base import BaseModel

class FieldCorrection(BaseModel):
    __tablename__ = "field_corrections"

    extracted_field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extracted_fields.id"))
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reviews.id"))
    previous_value: Mapped[str] = mapped_column(String, nullable=True)
    new_value: Mapped[str] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String, nullable=True)

    extracted_field = relationship("ExtractedField", back_populates="field_corrections")
    review = relationship("Review", back_populates="field_corrections")
