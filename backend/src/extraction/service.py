import uuid
from typing import Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from src.extraction.base import BaseExtractor
from src.db.models.extraction import Extraction
from src.db.models.extracted_field import ExtractedField

class ExtractionService:
    def __init__(self, extractor: BaseExtractor):
        self.extractor = extractor

    async def process_extraction(self, db: AsyncSession, document_id: str, document_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> Extraction:
        """
        Runs the extractor and stages the Extraction + fields in `db` WITHOUT committing.
        The caller commits once, together with validation results and job/document status,
        so a failure part-way through never leaves a half-recorded extraction behind.
        """
        # Phase 8: Extraction (Provider Agnostic)
        result = self.extractor.extract(document_data, metadata=metadata)
        doc_uuid = uuid.UUID(document_id)

        fallback_meta = None
        if metadata and "fallback_reason" in metadata:
            fallback_meta = {
                "original_extractor": metadata.get("original_extractor"),
                "fallback_extractor": metadata.get("fallback_extractor", getattr(result, "extractor_type", "rule_based")),
                "failure_reason": metadata.get("fallback_reason")
            }
            result.fallback_metadata = fallback_meta

        # A retried job must replace, not duplicate, any extraction left by an earlier attempt.
        old_ids = (await db.execute(select(Extraction.id).where(Extraction.document_id == doc_uuid))).scalars().all()
        if old_ids:
            await db.execute(delete(ExtractedField).where(ExtractedField.extraction_id.in_(old_ids)))
            await db.execute(delete(Extraction).where(Extraction.id.in_(old_ids)))

        extraction = Extraction(
            id=uuid.uuid4(),
            document_id=doc_uuid,
            extractor_type=getattr(result, "extractor_type", "rule_based"),
            model_version=result.model_version,
            provider=result.provider,
            prompt_version=result.prompt_version,
            fallback_metadata=fallback_meta,
        )
        db.add(extraction)

        for field in result.fields:
            db.add(ExtractedField(
                id=uuid.uuid4(),
                extraction_id=extraction.id,
                field_name=field.field_name,
                value=field.value,
                unit=field.unit,
                confidence=field.confidence,
                is_valid=True,
                page_num=field.page_num,
                bbox_normalized=field.bbox_normalized,
                is_corrected=False
            ))

        await db.flush()

        # Re-fetch with extracted_fields loaded to avoid MissingGreenlet in validation
        stmt = (
            select(Extraction)
            .options(selectinload(Extraction.extracted_fields))
            .where(Extraction.id == extraction.id)
            .execution_options(populate_existing=True)
        )
        return (await db.execute(stmt)).scalar_one()
