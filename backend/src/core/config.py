from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import List
import json

INSECURE_DEFAULT_JWT_SECRET = "supersecret-change-in-production"

class Settings(BaseSettings):
    APP_NAME: str = "ClinExtract API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    # SQL statement logging is noisy and can leak PHI into logs, so it is opt-in.
    SQL_ECHO: bool = False
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5433/clinextract"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str | List[str] = '["http://localhost:5173"]'

    JWT_SECRET: str = INSECURE_DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"

    # A claimed review with no activity for this long can be taken over by another reviewer.
    REVIEW_CLAIM_TIMEOUT_MINUTES: int = 60
    # A job left RUNNING longer than this (e.g. the worker died) is considered abandoned
    # and may be picked up again when the broker redelivers it.
    JOB_STALE_AFTER_MINUTES: int = 15
    # Upper bound on pages processed per document (protects the worker from huge PDFs).
    MAX_DOCUMENT_PAGES: int = 50

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

    @model_validator(mode="after")
    def _require_real_secret_in_production(self):
        if self.APP_ENV == "production" and self.JWT_SECRET == INSECURE_DEFAULT_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set to a strong random value when APP_ENV=production")
        return self

    @property
    def parsed_cors_origins(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            try:
                return json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                return [self.CORS_ORIGINS]
        return self.CORS_ORIGINS

settings = Settings()
