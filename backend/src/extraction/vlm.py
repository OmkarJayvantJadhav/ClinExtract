from typing import Dict, Any
from src.extraction.base import BaseExtractor
from src.extraction.schemas import ExtractionResult, CLINICAL_EXTRACTION_PROMPT_VERSION, build_field_instructions
from src.extraction.providers.base_provider import BaseAIProvider
from src.core.config import settings
from src.extraction.image_preparation import prepare_page_images
from src.extraction.exceptions import NonRetryableExtractionError
from pydantic import ValidationError

class VLMExtractor(BaseExtractor):
    def __init__(self, provider: BaseAIProvider):
        self.provider = provider
        
    def extract(self, document_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> ExtractionResult:
        image_bytes = metadata.get("image_bytes") if metadata else None
        if not image_bytes:
            raise NonRetryableExtractionError("VLM requires image_bytes in metadata")
            
        page_images = prepare_page_images(image_bytes)
        if not page_images:
            raise NonRetryableExtractionError("VLM failed to extract page images from document bytes")
            
        # One entry per field: every page is asked for every field, so a multi-page document
        # would otherwise yield one (mostly empty) copy of each field per page.
        best_fields = {}

        for page_img in page_images:
            page_num = page_img["page_num"]
            img_bytes = page_img["bytes"]
            img_mime = page_img["mime_type"]
            
            prompt = self._build_prompt(document_data, page_num)
            
            try:
                page_result: ExtractionResult = self.provider.generate_structured(
                    prompt=prompt,
                    schema=ExtractionResult,
                    image_data=img_bytes,
                    image_mime_type=img_mime
                )
                
                # Enforce provenance and page_num deterministic assignment
                for field in page_result.fields:
                    field.page_num = page_num
                    current = best_fields.get(field.field_name)
                    if current is None or self._is_better(field, current):
                        best_fields[field.field_name] = field


            except ValidationError as e:
                raise NonRetryableExtractionError(f"Provider returned invalid structured extraction output.") from e
            except ValueError as e:
                raise NonRetryableExtractionError(f"Provider returned malformed JSON or schema validation failed.") from e
        
        # Merge results
        final_result = ExtractionResult(
            extractor_type="vlm",
            provider=settings.VLM_PROVIDER or "unknown",
            model_version=settings.VLM_MODEL or "unknown",
            prompt_version=CLINICAL_EXTRACTION_PROMPT_VERSION,
            fields=list(best_fields.values())
        )

        return final_result

    @staticmethod
    def _is_better(candidate, current) -> bool:
        """A value beats no value; between two values the higher confidence wins (earlier page on ties)."""
        has_candidate = bool(candidate.value and candidate.value.strip())
        has_current = bool(current.value and current.value.strip())
        if has_candidate != has_current:
            return has_candidate
        return (candidate.confidence or 0.0) > (current.confidence or 0.0)

    def _build_prompt(self, document_data: Dict[str, Any], page_num: int) -> str:
        prompt = (
            f"Extract the following clinical fields from the provided document image (page {page_num}).\n"
            "Do not infer missing values. Do not fabricate patient information.\n"
            "Preserve source values exactly before normalization.\n"
            "Return null when a field cannot be established on this page.\n"
            "Never invent bounding boxes.\n\n"
            f"{build_field_instructions()}"
        )
        return prompt
