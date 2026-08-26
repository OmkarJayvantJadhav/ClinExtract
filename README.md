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

To enable the optional Gemini AI extractor:
```env
EXTRACTION_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
```

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
- **Backend API Docs:** `http://localhost:8000/docs`

## Database

Apply the latest database migrations by running Alembic inside the backend container:
```bash
docker compose exec backend alembic upgrade head
```

## Seed Users

To bootstrap the application with development users (Administrator, Reviewer, Operator roles), you can execute the official seed script:
```bash
docker compose exec backend python scripts/seed_users.py
```
*Note: This script provides pre-configured development credentials for local testing. These passwords must not be used in a production environment.*

## Testing

**Backend:**
Run the complete Pytest suite with async and regression testing:
```bash
docker compose exec backend pytest
```

**Frontend:**
Run linting and build checks:
```bash
cd frontend
npm run lint
npm run build
```

## Security

ClinExtract is built with production security principles:
- **HttpOnly JWT:** Secure session management.
- **CSRF Protection:** Anti-forgery tokens for state-changing requests.
- **RBAC:** Strict role-based access control for API endpoints.
- **Password Hashing:** Argon2 implementation.
- **File Validation:** Secure upload validation and path traversal protection.
- **Audit Logging:** Immutable provenance preservation for all clinical data changes.
- **No Secrets Committed:** Strict `.gitignore` rules prevent credentials from entering source control.

## AI Provider

- **RuleBased** is the default extraction provider, guaranteeing deterministic results.
- **Gemini** is optional and relies on a valid API key. (Note: standard API quotas and limits apply).
- **Mock Providers** are utilized internally for consistent automated testing.

## Project Status

ClinExtract v1.0 is feature-complete and verified locally. 
*(Disclaimer: This is a portfolio project. It does not carry HIPAA/GDPR/compliance certifications, is not deployed in a hospital production environment, and is not intended for live production clinical use.)*
