from abc import ABC, abstractmethod
from typing import Any, Type
from pydantic import BaseModel

class BaseAIProvider(ABC):
    @abstractmethod
    def generate_structured(self, prompt: str, schema: Type[BaseModel], image_data: Any = None) -> BaseModel:
        """
        Generates structured data from the provider.
        If image_data is provided, the provider should process it as a VLM.
        Returns an instance of the provided pydantic schema.
        """
        pass
