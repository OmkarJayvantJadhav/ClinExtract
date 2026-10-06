# ClinExtract

ClinExtract is an intelligent clinical document extraction system. It processes uploaded clinical documents, performs OCR, extracts structured medical data, and provides a human-in-the-loop review workflow for validation and correction.

## Overview

ClinExtract automates clinical document ingestion by combining Optical Character Recognition (OCR) and structured extraction. It supports a deterministic RuleBased extraction model as well as advanced integration with Gemini LLM/VLM for nuanced parsing. After extraction, the system automatically runs validation rules to assign confidence scores. Fields that fail validation or exhibit low confidence are flagged for human review. Comprehensive audit logging and analytics ensure full traceability of asynchronous processing workflows.

## Architecture

The system follows a modern, decoupled service-oriented architecture:
React (Frontend)
↓
FastAPI (Backend API)
↓
PostgreSQL (Relational Database)
↓
RabbitMQ (Message Broker)
↓
Celery (Asynchronous Task Processing)
↓
OCR / Extraction (PyMuPDF, Tesseract, OpenCV, Gemini)
↓
Validation (Rule engine)
↓
Human Review (React Dashboard)

**Key Technologies:** PyMuPDF, Tesseract, OpenCV, Gemini, SQLAlchemy, Alembic, TanStack Query.

## Features

- **Document Ingestion:** Support for native PDFs and scanned images.
- **Asynchronous Pipeline:** Robust Celery-driven OCR and data extraction.
- **Hybrid Extraction Engine:** Toggle between a deterministic Rule-Based provider and AI-assisted Gemini provider.
- **Validation Rules:** Configurable reference ranges and data type validation.
- **Human-in-the-Loop Review:** Interactive workspace to visualize document bounds, correct extracted fields, and approve or reject documents.
- **Security & Provenance:** RBAC, CSRF protection, and immutable audit logs.

## Project Structure

```
ClinExtract/
├── backend/
│   ├── alembic/            # Database migrations
│   ├── scripts/            # Bootstrapping scripts
│   ├── src/                # FastAPI application
│   │   ├── api/            # Route handlers
│   │   ├── core/           # Configuration and DB setup
│   │   ├── db/             # SQLAlchemy models
│   │   ├── extraction/     # Provider factory and AI/rules
│   │   ├── processing/     # OCR and parsing logic
│   │   └── worker/         # Celery application and tasks
│   └── tests/              # Pytest suite and regression fixtures
├── frontend/
│   ├── src/
│   │   ├── components/     # Reusable UI elements (shadcn)
│   │   ├── features/       # Complex domain components (Review Workspace)
│   │   ├── pages/          # Application views
│   │   └── services/       # API client definitions
├── docker-compose.yml      # Container orchestration
└── README.md
```

## Requirements

- Docker Desktop
- Docker Compose
- *Optional:* Google Gemini API key

## Configuration

Extraction behavior is configured via environment variables.

To use the default deterministic rule-based extractor:
```env
EXTRACTION_PROVIDER=rule_based
```

To enable the optional Gemini AI extractor (text-based LLM over the OCR output, or the
vision model over page images):
```env
EXTRACTION_PROVIDER=llm        # or: vlm
LLM_PROVIDER=gemini            # or, for vlm: VLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
EXTRACTION_FALLBACK_ENABLED=true   # fall back to the rule-based extractor if Gemini fails
```

> **Patient data:** the Gemini extractors send document content to Google. Only enable them
> under an appropriate data-processing agreement (e.g. a HIPAA BAA) for your deployment.

Put these in a `.env` file next to `docker-compose.yml`. For any deployment beyond your own
machine also set `JWT_SECRET` (the API refuses to start with `APP_ENV=production` and the
default secret), `POSTGRES_PASSWORD`, `RABBITMQ_USER` and `RABBITMQ_PASSWORD`.

## Running the Project

1. Build the Docker images:
   ```bash
   docker compose build
   ```
2. Start the application stack:
   ```bash
   docker compose up -d
   ```

- **Frontend Application:** `http://localhost:5173`
- **Backend API Docs:** `http://localhost:8001/api/v1/docs`

If a port is already taken by another project, override the host ports in `.env` (or the shell):
```env
FRONTEND_HOST_PORT=5174    # default 5173
BACKEND_HOST_PORT=8001
DB_HOST_PORT=5434          # default 5433
RABBITMQ_HOST_PORT=5672
RABBITMQ_UI_HOST_PORT=15672
```
CORS and the frontend's API URL follow these values automatically.

## Local Development (without Docker)

Create one virtual environment from the pinned requirements:
```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows; use .venv/bin/python on macOS/Linux
```

## Database

The backend container applies pending Alembic migrations automatically on start-up. To run
them by hand:
```bash
docker compose exec backend alembic upgrade head
```

## Seed Users

To bootstrap the application with development users (Administrator, Reviewer, Operator, Viewer roles), run the seed script:
```bash
docker compose exec backend python scripts/seed_users.py
```
Existing users are left untouched; pass `--reset` to reset their passwords.
*Note: This script provides pre-configured development credentials for local testing. These passwords must not be used in a production environment.*

## Testing

**Backend:**
Run the complete Pytest suite with async and regression testing:
```bash
docker compose exec backend pytest
```
To keep test data out of the development database, create a separate database and point the
suite at it with `TEST_DATABASE_URL` (tables and test users are created automatically):
```bash
docker compose exec db createdb -U postgres clinextract_test
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/clinextract_test backend pytest
```
The Gemini provider is covered by tests using a fake SDK client, so no API key is needed.

**Frontend:**
```bash
cd frontend
npm run lint
npm test
npm run build
```

**CI:** `.github/workflows/ci.yml` runs on every push and pull request: backend tests against
PostgreSQL, a migration upgrade/downgrade check, frontend lint/tests/build, and Docker image builds.

## Production Deployment

**Free hosting with a public link:** see [DEPLOYMENT.md](DEPLOYMENT.md) (Oracle Cloud Always Free + `scripts/deploy.sh`, one command).

`docker-compose.prod.yml` runs the full stack with only the web server exposed:

| Service | Role |
|---|---|
| `web` | Caddy: serves the built frontend, proxies `/api`, automatic HTTPS, security headers |
| `backend` | FastAPI (2 workers); runs migrations on start; health-checked via `/api/v1/health/ready` |
| `worker` | Celery document processing; health-checked with `celery inspect ping` |
| `beat` | Scheduler for the daily retention purge |
| `db`, `rabbitmq` | Internal only, with persistent volumes |
| `backup` | Daily database dump and document archive |

```bash
cp .env.production.example .env.production   # fill in every value
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.production exec backend python scripts/seed_users.py
```
Point a DNS record for `SITE_ADDRESS` at the host and open ports 80/443; Caddy obtains and
renews the TLS certificate. The API refuses to start in production without a strong
`JWT_SECRET` and a `DOCUMENT_ENCRYPTION_KEY`. Seeding refuses the default dev passwords there,
so set the `*_SEED_PASSWORD` variables (or create users in the UI once an admin exists).

### Backups

The `backup` service writes `db-<timestamp>.dump` and `files-<timestamp>.tar.gz` to the
`backups` volume every `BACKUP_INTERVAL_SECONDS` and deletes copies older than
`BACKUP_RETENTION_DAYS`. Run one immediately, and restore, with:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backup --once
scripts/restore.sh 20261006T030000Z
```
The database dump contains patient data: copy backups off the host to encrypted,
access-controlled storage. Stored files stay encrypted inside the archive, so keep
`DOCUMENT_ENCRYPTION_KEY` safe; backups are unreadable without it.

### Monitoring

- `GET /api/v1/health` (liveness), `/api/v1/health/ready` (readiness, checks the database),
  `/api/v1/health/detailed` (signed-in users: database, broker, worker, storage).
- `GET /api/v1/health/metrics`: Prometheus metrics (request rates/latency, documents and jobs
  by status, oldest pending review, dependency up/down). Requires
  `Authorization: Bearer $METRICS_TOKEN`; the public web server blocks it, so scrape
  `backend:8000` from inside the Docker network.
- Suggested alerts: `clinextract_dependency_up == 0`, a rising
  `clinextract_processing_jobs{status="FAILED"}`, and
  `clinextract_oldest_pending_review_age_seconds` above your review SLA.

## Security

- **Sessions:** HttpOnly, SameSite=Strict JWT cookies (Secure in production) with double-submit CSRF tokens.
  Changing a password, changing a role, deactivating an account or "sign out everywhere" revokes
  existing sessions immediately.
- **Brute-force protection:** accounts lock for `LOGIN_LOCKOUT_MINUTES` after
  `LOGIN_MAX_FAILED_ATTEMPTS` failures, and login attempts are rate-limited per client IP. Failed
  logins and lockouts are audited.
- **Passwords:** Argon2 hashing, with a policy of at least 12 characters mixing three character classes.
  Users change their own password in Settings; admins create users, change roles,
  deactivate, unlock and reset passwords in User Management.
- **RBAC:** role checks on every endpoint, mirrored in the UI's navigation.
- **Uploads:** magic-byte type checks, a streaming 10 MB limit, and page and pixel limits.
- **Transport:** HTTPS via Caddy with HSTS, CSP, frame and content-type protections.
- **Secrets:** `.env*` files are git-ignored (except the examples).

## Data Protection

- **Encryption at rest:** documents and OCR artifacts are encrypted with Fernet (AES + HMAC) using
  `DOCUMENT_ENCRYPTION_KEY`. Files stored before encryption was enabled remain readable.
- **Access logging:** document views and downloads are recorded in the audit log, de-duplicated over
  `VIEW_AUDIT_THROTTLE_MINUTES`.
- **Deletion:** admins can permanently delete a document, with a required reason. Files, extractions
  and reviews are removed, and the audit trail is kept with its patient-data payloads redacted.
- **Retention:** set `DOCUMENT_RETENTION_DAYS` to purge finalized documents automatically each night.
- **External AI:** Gemini receives document content, so it is refused unless
  `ALLOW_EXTERNAL_AI_PHI=true`. Enable this only under an appropriate data-processing agreement.

These controls support, but do not by themselves constitute, HIPAA/GDPR compliance. That
also requires organizational measures such as agreements, policies and risk assessment.

## Clinical Validation

- Reference ranges are adult ranges, sex-specific where they differ (hemoglobin, hematocrit), using
  the extracted patient sex. For patients under 18, no adult range is applied and the value is
  routed to human review.
- Units are captured and converted (for example glucose in mmol/L, hemoglobin in g/L, cell counts in /µL).
- Every extracted value is checked against the document's own text. Values that do not appear on
  the page (a risk with AI extractors) are flagged `SOURCE_MISMATCH`.
- The rule-based extractor understands common label variants (MRN, Hgb/Hb, Hct, WBC, PLT,
  "Collected", "Sample", several date formats). Unusual layouts are best handled by the Gemini
  extractors with review.
- Only missing, malformed or impossible values block approval. Abnormal results must be explicitly
  confirmed by the reviewer.

## AI Provider

- **RuleBased** is the default extraction provider, guaranteeing deterministic results.
- **Gemini** (LLM over OCR text, or VLM over page images) is optional. It needs `GEMINI_API_KEY` and
  `ALLOW_EXTERNAL_AI_PHI=true`; with `EXTRACTION_FALLBACK_ENABLED=true` it falls back to the
  rule-based extractor on failure.
- **Mock Providers** are used internally for consistent automated testing.

## Project Status

ClinExtract includes the technical controls expected of a production clinical-document system
(encryption, access logging, retention, hardened authentication, HTTPS deployment, backups,
monitoring, CI).
*(Disclaimer: it has not been certified, clinically validated or audited for HIPAA/GDPR
compliance. Validate it against your own requirements and documents before clinical use.)*
