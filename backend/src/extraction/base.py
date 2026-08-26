from abc import ABC, abstractmethod
from typing import Dict, Any
from src.extraction.schemas import ExtractionResult

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, document_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> ExtractionResult:
        """
        Extracts structured fields from standardized document data (Phase 7 artifact).
        """
        pass
