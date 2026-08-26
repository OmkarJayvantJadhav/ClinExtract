from pydantic_settings import BaseSettings
from typing import List
import json

class Settings(BaseSettings):
    APP_NAME: str = "ClinExtract API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5433/clinextract"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str | List[str] = '["http://localhost:5173"]'
    
    JWT_SECRET: str = "supersecret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
    
    # Extraction configuration
    EXTRACTION_PROVIDER: str = "rule_based"
    EXTRACTION_FALLBACK_ENABLED: bool = False
    
    LLM_PROVIDER: str | None = None
    LLM_MODEL: str | None = None
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str | None = None
    GEMINI_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str | None = None
    
    VLM_PROVIDER: str | None = None
    VLM_MODEL: str | None = None
    VLM_API_KEY: str | None = None
    VLM_BASE_URL: str | None = None

    class Config:
        env_file = ".env"

    @property
    def parsed_cors_origins(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            try:
                return json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                return [self.CORS_ORIGINS]
        return self.CORS_ORIGINS

settings = Settings()
