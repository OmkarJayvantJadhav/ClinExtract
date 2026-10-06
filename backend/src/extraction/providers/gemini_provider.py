from pydantic import BaseModel
from typing import Type, Any
from src.extraction.providers.base_provider import BaseAIProvider
from src.extraction.exceptions import RetryableExtractionError, NonRetryableExtractionError
from src.core.config import settings

class GeminiProvider(BaseAIProvider):
    def __init__(self):
        # Allow it to run without a key if rule_based is active
        # The key isn't needed unless generating.
        self.api_key = settings.GEMINI_API_KEY
        self.client = None
        if self.api_key:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)

    def generate_structured(self, prompt: str, schema: Type[BaseModel], image_data: Any = None, image_mime_type: str = "image/jpeg") -> BaseModel:
        if not self.client:
            raise NonRetryableExtractionError("GEMINI_API_KEY is not configured.")

        # Determine model
        model = settings.GEMINI_MODEL
        if not model:
            model = settings.VLM_MODEL if image_data else settings.LLM_MODEL
            if not model:
                model = "gemini-3.6-flash"
        
        contents = []
        if image_data:
            from google.genai import types
            if isinstance(image_data, str):
                # Accept base64 for backwards compatibility, but the SDK needs raw bytes.
                import base64
                image_data = base64.b64decode(image_data)
            contents.append(
                types.Part.from_bytes(
                    data=image_data,
                    mime_type=image_mime_type,
                )
            )
        contents.append(prompt)

        try:
            from google.genai.errors import APIError
            from pydantic import create_model
            
            # Create a safe schema to avoid additional_properties error from Gemini API
            safe_fields = {}
            for name, field in schema.model_fields.items():
                if name == "fallback_metadata":
                    continue
                safe_fields[name] = (field.annotation, field.default)
                
            SafeSchema = create_model(schema.__name__, **safe_fields)
            
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": SafeSchema,
                }
            )
            
            # The google-genai SDK for gemini structured output returns json string in response.text
            # Use pydantic to parse it to the schema instance
            if not response.text:
                 raise NonRetryableExtractionError("Provider returned empty response.")
                 
            return schema.model_validate_json(response.text)

        except APIError as e:
            # Map Google GenAI errors
            # APIError contains status code and message. We classify 400, 401, 403 as NonRetryable, and others as Retryable.
            if e.code in (400, 401, 403):
                raise NonRetryableExtractionError(f"Gemini authentication or bad request failed ({e.code}): {e.message}. Check configuration.") from e
            raise RetryableExtractionError(f"Transient error from Gemini API: {e.message}") from e
        except Exception as e:
            # We catch pydantic validation errors in the extractor
            raise
