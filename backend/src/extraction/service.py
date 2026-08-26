import uuid
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.extraction.base import BaseExtractor
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField

class ExtractionService:
    def __init__(self, extractor: BaseExtractor):
        self.extractor = extractor

    async def process_extraction(self, db: AsyncSession, document_id: str, document_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> Extraction:
        # Phase 8: Extraction (Provider Agnostic)
        result = self.extractor.extract(document_data, metadata=metadata)
        
        fallback_meta = None
        if metadata and "fallback_reason" in metadata:
            fallback_meta = {
                "original_extractor": metadata.get("original_extractor"),
                "fallback_extractor": metadata.get("fallback_extractor", getattr(result, "extractor_type", "rule_based")),
                "failure_reason": metadata.get("fallback_reason")
            }
            result.fallback_metadata = fallback_meta

        extraction = Extraction(
            id=uuid.uuid4(),
            document_id=uuid.UUID(document_id),
            extractor_type=getattr(result, "extractor_type", "rule_based"),
            model_version=result.model_version,
            provider=result.provider,
            prompt_version=result.prompt_version,
            fallback_metadata=fallback_meta,
        )
        
        db.add(extraction)
        
        for field in result.fields:
            extracted_field = ExtractedField(
                id=uuid.uuid4(),
                extraction_id=extraction.id,
                field_name=field.field_name,
                value=field.value,
                confidence=field.confidence,
                is_valid=True,
                page_num=field.page_num,
                bbox_normalized=field.bbox_normalized,
                is_corrected=False
            )
            db.add(extracted_field)
            
        await db.commit()
        
        # Re-fetch with extracted_fields loaded to avoid MissingGreenlet in validation
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        stmt = select(Extraction).options(selectinload(Extraction.extracted_fields)).where(Extraction.id == extraction.id)
        result = await db.execute(stmt)
        extraction = result.scalar_one()
        
        return extraction
