from src.extraction.base import BaseExtractor
from src.extraction.rule_based import RuleBasedExtractor
from src.extraction.llm import LLMExtractor
from src.extraction.vlm import VLMExtractor
from src.extraction.providers.mock_provider import MockLLMProvider, MockVLMProvider
from src.extraction.providers.gemini_provider import GeminiProvider
from src.core.config import settings
from src.extraction.exceptions import NonRetryableExtractionError

def _require_external_ai_allowed(provider: str) -> None:
    # Document content is patient data; never send it to an external service by accident.
    if not settings.ALLOW_EXTERNAL_AI_PHI:
        raise NonRetryableExtractionError(
            f"{provider} would receive patient data but ALLOW_EXTERNAL_AI_PHI is false. "
            "Enable it only under an appropriate data-processing agreement."
        )

class ExtractionFactory:
    @staticmethod
    def get_extractor(provider_name: str) -> BaseExtractor:
        if provider_name == "rule_based":
            return RuleBasedExtractor()
            
        elif provider_name == "llm":
            if settings.LLM_PROVIDER == "gemini":
                _require_external_ai_allowed("Gemini")
                if not settings.GEMINI_API_KEY:
                    raise NonRetryableExtractionError("GEMINI_API_KEY is not configured for LLM_PROVIDER=gemini")
                provider_impl = GeminiProvider()
            else:
                provider_impl = MockLLMProvider()
                
            return LLMExtractor(provider=provider_impl)
            
        elif provider_name == "vlm":
            if settings.VLM_PROVIDER == "gemini":
                _require_external_ai_allowed("Gemini")
                if not settings.GEMINI_API_KEY:
                    raise NonRetryableExtractionError("GEMINI_API_KEY is not configured for VLM_PROVIDER=gemini")
                provider_impl = GeminiProvider()
            else:
                provider_impl = MockVLMProvider()
                
            return VLMExtractor(provider=provider_impl)
            
        else:
            raise ValueError(f"Invalid EXTRACTION_PROVIDER configured: {provider_name}")
