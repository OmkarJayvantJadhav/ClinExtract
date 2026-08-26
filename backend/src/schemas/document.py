from pydantic import BaseModel, field_validator
import uuid
from datetime import datetime
from typing import List, Optional
from src.db.models.document import DocumentStatus

class ExtractedFieldResponse(BaseModel):
    id: uuid.UUID
    field_name: str
    value: Optional[str]
    original_value: Optional[str] = None
    current_value: Optional[str] = None
    is_corrected: bool = False
    normalized_value: Optional[str]
    validation_state: Optional[str]
    validation_messages: Optional[List[str]]
    confidence: Optional[float]
    confidence_category: Optional[str]
    page_num: Optional[int]
    bbox_normalized: Optional[List[float]]
    
    @field_validator('confidence', mode='before')
    def scale_confidence(cls, v):
        if v is not None and v <= 1.0:
            return round(v * 100, 1)
        return v

    class Config:
        from_attributes = True



class ExtractionResponse(BaseModel):
    id: uuid.UUID
    extractor_type: Optional[str] = None
    model_version: Optional[str] = None
    provider: str
    prompt_version: Optional[str] = None
    overall_confidence: Optional[float]
    validation_status: Optional[str]
    decision: Optional[str]
    validation_summary: Optional[dict]
    extracted_fields: List[ExtractedFieldResponse] = []
    
    @field_validator('overall_confidence', mode='before')
    def scale_overall_confidence(cls, v):
        if v is not None and v <= 1.0:
            return round(v * 100, 1)
        return v
    
    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    doc_type: str | None = None
    status: DocumentStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class DocumentDetailResponse(DocumentResponse):
    extractions: List[ExtractionResponse] = []

class PaginatedDocumentResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    size: int
    pages: int

