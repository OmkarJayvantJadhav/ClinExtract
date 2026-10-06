from typing import Type
from pydantic import BaseModel
from src.extraction.providers.base_provider import BaseAIProvider

class MockLLMProvider(BaseAIProvider):
    def generate_structured(self, prompt: str, schema: Type[BaseModel], image_data: bytes = None, image_mime_type: str = "image/jpeg") -> BaseModel:
        # A deterministic mock provider for testing
        
        if "simulated_failure" in prompt:
            raise Exception("Mock provider simulated failure")
            
        if "simulated_malformed" in prompt:
            # We bypass the schema validation return just to test bad Pydantic validation if we want,
            # but since we return BaseModel, we should raise ValueError to simulate schema error.
            raise ValueError("Malformed JSON or schema validation failed")
            
        # Return a known extraction result matching the clinical schema
        mock_data = {
            "extractor_type": "llm",
            "provider": "mock",
            "fields": [
                {
                    "field_name": "patient_name",
                    "value": "Jane Doe",
                    "confidence": 95.0,
                    "page_num": 1,
                    "bbox_normalized": [0.1, 0.1, 0.2, 0.05]
                },
                {
                    "field_name": "glucose",
                    "value": "90 mg/dL",
                    "confidence": 98.0,
                    "page_num": 1,
                    "bbox_normalized": [0.1, 0.2, 0.1, 0.05]
                },
                {
                    "field_name": "date_of_birth",
                    "value": "1980-01-01",
                    "confidence": 90.0,
                    "page_num": 1,
                    "bbox_normalized": None
                }
            ]
        }
        
        # Pydantic validation
        return schema(**mock_data)

class MockVLMProvider(MockLLMProvider):
    pass
