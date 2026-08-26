# ClinExtract Development Chronicle

This document chronicles the phase-by-phase development of the ClinExtract project, from Phase 0 to v1.0.0.

## Phase 0: Project Initiation and Setup
**Goal**: Establish the project structure, repository, and core dependencies.

| File | Action | Description |
| :--- | :--- | :--- |
| `README.md` | Created | Project overview and initial documentation. |
| `.gitignore` | Created | Standard Python and Node.js ignore patterns. |
| `docker-compose.yml` | Created | Initial definition for PostgreSQL, Redis, and MinIO. |
| `backend/pyproject.toml` | Created | Poetry configuration with FastAPI, SQLAlchemy, and Celery dependencies. |
| `frontend/package.json` | Created | React project initialization with Vite. |

**Architectural Decisions**: 
- Selected FastAPI for its async support and automatic OpenAPI generation.
- Chose PostgreSQL for relational data and Redis for Celery task queuing.
- Adopted a monorepo structure separating `frontend` and `backend`.

---

## Phase 1: Core API and Database Modeling
**Goal**: Implement the basic REST API, database schemas, and document upload functionality.

| File | Action | Description |
| :--- | :--- | :--- |
| `backend/app/models.py` | Created | Defined SQLAlchemy models for `Document` and `ExtractedData`. |
| `backend/app/schemas.py` | Created | Pydantic models for request/response validation. |
| `backend/app/database.py` | Created | Database connection setup and session management. |
| `backend/app/main.py` | Modified | Initialized FastAPI application and included routers. |
| `backend/app/routers/documents.py` | Created | Implementation of document upload and retrieval endpoints. |
| `backend/app/services/storage.py` | Created | Integration with MinIO for saving uploaded files. |

**Architectural Decisions**:
- Used Pydantic for strict data validation at the API boundary.
- Decoupled file storage logic into a dedicated service module to support future S3 migration.

---

## Phase 2: Asynchronous Processing and OCR
**Goal**: Integrate Celery for background tasks and implement Tesseract OCR.

| File | Action | Description |
| :--- | :--- | :--- |
| `backend/app/worker.py` | Created | Celery application configuration and task definitions. |
| `backend/app/services/ocr.py` | Created | Tesseract OCR wrapper for text extraction. |
| `backend/app/routers/documents.py` | Modified | Updated upload endpoint to trigger background Celery tasks. |
| `docker-compose.yml` | Modified | Added Celery worker and Tesseract dependencies to backend container. |

**Architectural Decisions**:
- Offloaded OCR to Celery workers to prevent API timeouts during large document processing.

---

## Phase 3: Gemini Integration and Extraction Engine
**Goal**: Implement the core extraction logic using LLMs and rule-based fallbacks.

| File | Action | Description |
| :--- | :--- | :--- |
| `backend/app/services/extraction.py` | Created | Orchestrator for rule-based and LLM extraction. |
| `backend/app/services/gemini.py` | Created | API client and prompt templates for Google Gemini. |
| `backend/app/services/rules.py` | Created | Regular expression patterns for standard field extraction. |
| `backend/app/worker.py` | Modified | Added tasks for AI extraction following OCR completion. |
| `backend/app/models.py` | Modified | Added fields for confidence scores and provenance data. |

**Architectural Decisions**:
- Implemented a two-tier extraction system: regex for speed/reliability, Gemini for unstructured text.
- Standardized the extraction output format regardless of the underlying extraction method.

---

## Phase 4: Frontend Development and Review UI
**Goal**: Build the user interface for document management and data review.

| File | Action | Description |
| :--- | :--- | :--- |
| `frontend/src/App.tsx` | Modified | Setup React Router and main layout. |
| `frontend/src/components/UploadModal.tsx` | Created | Component for drag-and-drop document upload. |
| `frontend/src/pages/DocumentList.tsx` | Created | Dashboard showing document processing status. |
| `frontend/src/pages/ReviewView.tsx` | Created | Interface displaying document image alongside extracted data for human review. |
| `frontend/src/services/api.ts` | Created | Axios client for backend communication. |

**Architectural Decisions**:
- Used TailwindCSS for rapid UI development.
- Implemented a side-by-side view for the Review UI to maximize efficiency for human validators.

---

## Phase 5: v1.0.0 Release and Polish
**Goal**: Finalize testing, add observability, and prepare for production deployment.

| File | Action | Description |
| :--- | :--- | :--- |
| `backend/tests/` | Created | Comprehensive pytest suite for API and services. |
| `backend/app/middleware.py` | Created | Added Prometheus metrics and structured logging. |
| `docker-compose.prod.yml` | Created | Production-ready Docker configuration. |
| `README.md` | Modified | Updated setup instructions and API documentation. |
| `docs/ClinExtract_Project_Presentation.md` | Created | Project presentation slides. |
| `docs/ClinExtract_Development_Chronicle.md` | Created | Development history chronicle. |

**Architectural Decisions**:
- Focused on high test coverage for the extraction logic.
- Adopted Prometheus for monitoring Celery queue health and API performance.
