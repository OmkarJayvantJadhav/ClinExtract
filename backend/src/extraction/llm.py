from typing import Dict, Any
from src.extraction.base import BaseExtractor
from src.extraction.schemas import ExtractionResult, CLINICAL_EXTRACTION_PROMPT_VERSION
from src.extraction.providers.base_provider import BaseAIProvider
from src.core.config import settings

class LLMExtractor(BaseExtractor):
    def __init__(self, provider: BaseAIProvider):
        self.provider = provider
        
    def extract(self, document_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> ExtractionResult:
        # Build deterministic prompt from OCR artifact
        prompt = self._build_prompt(document_data)
        
        # Call provider and validate with pydantic schema
        try:
            from pydantic import ValidationError
            result_schema = self.provider.generate_structured(
                prompt=prompt,
                schema=ExtractionResult
            )
        except ValidationError as e:
            from src.extraction.exceptions import NonRetryableExtractionError
            raise NonRetryableExtractionError(f"Provider returned invalid structured extraction output.") from e
        except ValueError as e:
            from src.extraction.exceptions import NonRetryableExtractionError
            raise NonRetryableExtractionError(f"Provider returned malformed JSON or schema validation failed.") from e
        
        # Add metadata provenance to the result before returning
        result_schema.extractor_type = "llm"
        result_schema.provider = settings.LLM_PROVIDER or "unknown"
        result_schema.model_version = settings.LLM_MODEL or "unknown"
        result_schema.prompt_version = CLINICAL_EXTRACTION_PROMPT_VERSION
        
        return result_schema

    def _build_prompt(self, document_data: Dict[str, Any]) -> str:
        # Simplistic prompt building from Phase 7 artifact
        text_content = ""
        for page in document_data.get("pages", []):
            words = [w.get("text", "") for w in page.get("words", [])]
            text_content += " ".join(words) + "\n"
            
        prompt = f"""
        Extract the following clinical fields from the provided document text.
        Do not infer missing values. Do not fabricate patient information.
        Preserve source values exactly before normalization.
        Return null/missing when a field cannot be established.
        Never invent bounding boxes.
        
        Document Text:
        {text_content}
        """
        return prompt
