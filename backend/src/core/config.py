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
    # A QUEUED or RETRYING job with no progress for this long is sent to the worker again
    # (its message was lost, e.g. a broker restart). Checked every 10 minutes.
    STUCK_JOB_MINUTES: int = 15
    # Upper bound on pages processed per document (protects the worker from huge PDFs).
    MAX_DOCUMENT_PAGES: int = 50
    # Pages OCR'd at the same time within one document; 0 = number of CPUs (at most 4)
    OCR_WORKERS: int = 0

    # --- Compliance ---
    # Fernet key used to encrypt stored documents and OCR artifacts at rest.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Required when APP_ENV=production. Without it (development only) files are stored unencrypted.
    DOCUMENT_ENCRYPTION_KEY: str | None = None
    # Finalized documents (approved/rejected/auto-accepted/failed) older than this are purged
    # by the scheduled retention task. 0 disables automatic purging.
    DOCUMENT_RETENTION_DAYS: int = 0
    # External AI providers (Gemini) receive document content. They are refused unless this is
    # explicitly enabled, which should only happen under an appropriate data-processing agreement.
    ALLOW_EXTERNAL_AI_PHI: bool = False
    # Repeated views of the same document by the same user within this window are logged once.
    VIEW_AUDIT_THROTTLE_MINUTES: int = 5

    # --- Authentication hardening ---
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    # Per-client-IP login attempts allowed per minute (shared by all API processes)
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 20
    PASSWORD_MIN_LENGTH: int = 12
    # Mark cookies Secure. Defaults to True in production; set explicitly when serving over HTTPS elsewhere.
    COOKIE_SECURE: bool | None = None
    # Only enable behind the bundled reverse proxy, which sets X-Real-IP; otherwise clients could spoof it.
    TRUST_PROXY_HEADERS: bool = False

    # --- Observability ---
    # Bearer token for GET /api/v1/health/metrics. Without it the endpoint is open in
    # development and disabled in production.
    METRICS_TOKEN: str | None = None

    # --- Public demo ---
    # Comma-separated non-admin usernames to share publicly on a demo deployment, e.g.
    # "operator,reviewer". With DEMO_PASSWORD set they are offered on the sign-in page, cannot
    # change their password or sign out other sessions, and are not locked by failed logins
    # (per-IP login rate limiting still applies). Use synthetic documents only.
    DEMO_ACCOUNTS: str = ""
    DEMO_PASSWORD: str | None = None

    # How to read numeric dates such as 03/04/2025 that are valid either way: "MDY" (US,
    # March 4) or "DMY" (most other countries, 3 April). ISO dates (2025-04-03) are unaffected.
    DATE_ORDER: str = "MDY"

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
        if self.APP_ENV == "production":
            if self.JWT_SECRET == INSECURE_DEFAULT_JWT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be a strong random value (>= 32 chars) when APP_ENV=production")
            if not self.DOCUMENT_ENCRYPTION_KEY:
                raise ValueError("DOCUMENT_ENCRYPTION_KEY must be set when APP_ENV=production")
        return self

    @property
    def demo_usernames(self) -> set[str]:
        if not self.DEMO_PASSWORD:
            return set()
        return {name.strip() for name in self.DEMO_ACCOUNTS.split(",") if name.strip()}

    @property
    def cookie_secure(self) -> bool:
        return self.COOKIE_SECURE if self.COOKIE_SECURE is not None else self.APP_ENV == "production"

    @property
    def parsed_cors_origins(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            try:
                return json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                return [self.CORS_ORIGINS]
        return self.CORS_ORIGINS

settings = Settings()
