from typing import Dict, Any
from src.extraction.base import BaseExtractor
from src.extraction.schemas import ExtractionResult, CLINICAL_EXTRACTION_PROMPT_VERSION
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
            
        all_fields = []
        
        for page_img in page_images:
            page_num = page_img["page_num"]
            b64_image = page_img["base64"]
            
            prompt = self._build_prompt(document_data, page_num)
            
            try:
                page_result: ExtractionResult = self.provider.generate_structured(
                    prompt=prompt,
                    schema=ExtractionResult,
                    image_data=b64_image
                )
                
                # Enforce provenance and page_num deterministic assignment
                for field in page_result.fields:
                    field.page_num = page_num
                    all_fields.append(field)
                    
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
            fields=all_fields
        )
        
        return final_result

    def _build_prompt(self, document_data: Dict[str, Any], page_num: int) -> str:
        prompt = f"""
        Extract the following clinical fields from the provided document image for page {page_num}.
        Do not infer missing values. Do not fabricate patient information.
        Preserve source values exactly before normalization.
        Return null/missing when a field cannot be established.
        Never invent bounding boxes.
        """
        return prompt
