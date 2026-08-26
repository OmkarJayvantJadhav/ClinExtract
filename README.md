# ClinExtract

ClinExtract is an intelligent clinical document extraction system. It processes uploaded clinical documents, performs OCR, extracts structured medical data, and provides a review workflow for clinicians.

## Architecture

- **Frontend**: React, Vite, Tailwind CSS, shadcn/ui.
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, Celery, RabbitMQ.
- **Extraction**: Extensible architecture supporting a deterministic Rule-Based Provider (default) and AI Providers (Gemini integration via Google GenAI SDK).

## Setup & Execution

### Prerequisites
- Docker and Docker Compose
- Optional: Google Gemini API Key (if you wish to enable the AI provider)

### Environment Variables
Review the environment variables in docker-compose.yml.
By default, the system runs with the ule_based extraction provider. If you want to use the Gemini AI provider, set your GEMINI_API_KEY in the environment.

### Running with Docker
To start the entire application stack:

docker compose build --no-cache
docker compose up -d

### Database Initialization
Apply the latest Alembic migrations:
docker compose exec backend alembic upgrade head

### Seeding Development Users
If you need seeded test accounts (e.g. for Admin, Reviewer, Operator roles), you can run the bootstrap script:

docker compose exec backend python scripts/seed_users.py

*Note: This creates default users as defined in backend/scripts/seed_users.py.*

## Testing
Run the comprehensive Pytest suite in the backend container:
docker compose exec backend pytest
