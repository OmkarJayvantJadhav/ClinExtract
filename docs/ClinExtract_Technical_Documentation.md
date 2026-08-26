# ClinExtract Technical Documentation

## 1. Executive Summary
**WHAT**: ClinExtract is a comprehensive, AI-driven clinical document extraction and management system designed to process, extract, validate, and store unstructured medical data from various document types (PDFs, images, faxes).
**WHY**: Healthcare organizations struggle with unstructured data. Manual entry is slow, error-prone, and expensive.
**HOW**: By combining traditional Rule-Based NLP, advanced Large Language Models (Gemini), and Vision-Language Models (VLMs) orchestrated through an asynchronous backend (Django/Celery/RabbitMQ) and a modern frontend (React).
**PROBLEM SOLVED**: Automates clinical data extraction, reducing manual workload by up to 80% while maintaining high accuracy through confidence scoring and human-in-the-loop review.
**FAILURES**: Occasional hallucination from LLMs, handled via strict validation schemas and fallback mechanisms.
**ALTERNATIVES**: Pure rule-based systems (low adaptability), manual data entry (high cost), or third-party black-box SaaS (data privacy concerns).

## 2. System Architecture
**WHAT**: A distributed, service-oriented architecture (SOA) based on Django REST Framework, Celery workers, RabbitMQ message broker, PostgreSQL, and a React frontend.
**WHY**: Ensures scalability, fault tolerance, and clear separation of concerns.
**HOW**: Frontend communicates with backend via REST APIs. Backend offloads heavy processing (OCR, LLM calls) to Celery workers via RabbitMQ.
**PROBLEM SOLVED**: Prevents long-running document processing tasks from blocking web request threads.
**FAILURES**: Broker downtime can halt processing. Mitigated by RabbitMQ clustering and durable queues.
**ALTERNATIVES**: Monolithic synchronous architecture (poor UX, timeouts), Microservices (too complex for the current scale).

## 3. Backend
**WHAT**: Django and Django REST Framework (DRF) serving as the core API and orchestration layer.
**WHY**: Rapid development, robust ORM, excellent security defaults, and a strong ecosystem.
**HOW**: Implements stateless REST APIs, handles business logic, database transactions, and task enqueuing.
**PROBLEM SOLVED**: Provides a stable, secure, and scalable foundation for the application logic.
**FAILURES**: High memory usage under heavy load. Mitigated by optimized ORM queries and caching.
**ALTERNATIVES**: Node.js/Express, Go, FastAPI. Django chosen for mature ORM and admin interface.

## 4. Frontend
**WHAT**: A React-based Single Page Application (SPA) utilizing modern state management and UI libraries.
**WHY**: Provides a highly interactive, responsive user experience required for document review and data correction.
**HOW**: Consumes backend APIs, handles document viewing (PDF.js), and provides forms for manual correction.
**PROBLEM SOLVED**: Delivers a seamless human-in-the-loop interface.
**FAILURES**: State desynchronization. Mitigated by optimistic UI updates and robust error handling.
**ALTERNATIVES**: Vue.js, Angular, Django Templates (not interactive enough).

## 5. Database & Storage
**WHAT**: PostgreSQL for relational data and S3-compatible storage (AWS S3 or MinIO) for object storage (documents).
**WHY**: ACID compliance for medical records; scalable, cheap storage for large PDF/image files.
**HOW**: Django ORM maps to PostgreSQL. `boto3` interacts with S3 for file uploads and presigned URLs.
**PROBLEM SOLVED**: Secure, scalable persistence of both structured clinical data and unstructured files.
**FAILURES**: Connection pooling exhaustion. Mitigated by PgBouncer.
**ALTERNATIVES**: MongoDB (lacks strong relations), Local file system (not scalable).

## 6. Authentication, RBAC, & CSRF
**WHAT**: JWT-based authentication, Role-Based Access Control (Admin, Reviewer, Uploader), and strict CSRF protection.
**WHY**: HIPAA compliance mandates strict access controls and security against unauthorized actions.
**HOW**: DRF SimpleJWT for tokens. Custom Django permissions for RBAC. Django's built-in CSRF middleware.
**PROBLEM SOLVED**: Ensures only authorized personnel can view or modify sensitive PHI (Protected Health Information).
**FAILURES**: Token theft. Mitigated by short-lived access tokens and HttpOnly refresh tokens.
**ALTERNATIVES**: Session-based auth (less scalable for mobile/external integrations).

## 7. Intake & Pre-processing
**WHAT**: The pipeline entry point accepting PDFs and images, performing format conversion, deskewing, and noise reduction.
**WHY**: High-quality input is crucial for OCR and LLM extraction accuracy.
**HOW**: Python libraries (e.g., OpenCV, ImageMagick) preprocess files before OCR.
**PROBLEM SOLVED**: Normalizes diverse, messy real-world clinical documents.
**FAILURES**: Corrupted files. Mitigated by strict file validation and virus scanning at upload.
**ALTERNATIVES**: Processing raw files directly (leads to poor extraction).

## 8. OCR Pipeline & OCR Artifact
**WHAT**: Optical Character Recognition engine (e.g., Tesseract, AWS Textract) generating a standardized JSON "Artifact" containing text and bounding boxes.
**WHY**: Text must be machine-readable for rule-based and standard LLM processing.
**HOW**: Celery task runs OCR, parses the output, and saves an internal standard artifact to S3.
**PROBLEM SOLVED**: Decouples the OCR engine from downstream extraction logic.
**FAILURES**: Poor scan quality leading to gibberish. Mitigated by VLM fallback.
**ALTERNATIVES**: Extracting directly without storing the artifact (makes debugging and re-processing impossible).

## 9. Extraction Architecture
The core intelligence of ClinExtract, designed as a pluggable pipeline.

### 9.1 Rule-Based Extraction
**WHAT**: Regex and SpaCy-based NER for highly structured fields (e.g., SSN, Dates, standard lab values).
**WHY**: Fast, cheap, and 100% deterministic.
**HOW**: Applied to the OCR artifact before heavy LLMs.
**PROBLEM SOLVED**: Efficient extraction of standard patterns without API costs.
**FAILURES**: Fails on variations.
**ALTERNATIVES**: Using LLMs for everything (too expensive).

### 9.2 Gemini / LLM Extraction
**WHAT**: Prompt-engineered calls to Google Gemini for complex, unstructured narrative extraction (e.g., Diagnosis, Treatment Plans).
**WHY**: Unmatched ability to understand clinical context and nuances.
**HOW**: Sends OCR text + strict JSON schema instructions to Gemini API.
**PROBLEM SOLVED**: Extracts data from physician notes that rules cannot handle.
**FAILURES**: Hallucinations. Mitigated by prompt constraints, temperature=0, and schema validation.
**ALTERNATIVES**: Fine-tuned custom models (high maintenance cost).

### 9.3 Vision-Language Model (VLM) Extraction
**WHAT**: Passing the raw document image directly to a VLM (e.g., Gemini 1.5 Pro Vision).
**WHY**: Captures spatial layout, tables, and handwriting better than OCR -> Text -> LLM.
**HOW**: Image encoded as base64 and sent to the VLM API with extraction prompts.
**PROBLEM SOLVED**: Solves complex table extraction and poor OCR quality issues.
**FAILURES**: High latency and cost.
**ALTERNATIVES**: Complex OCR table-parsing algorithms (brittle).

### 9.4 Provider Factory & Fallback
**WHAT**: A design pattern abstracting the extraction engine, allowing seamless switching and fallback (e.g., Rule -> Gemini -> VLM).
**WHY**: Balances cost, speed, and accuracy.
**HOW**: Python Factory pattern instantiates the appropriate extractor based on document type and previous step failures.
**PROBLEM SOLVED**: Prevents a single point of failure if an API goes down.

## 10. Validation & Confidence Scoring
**WHAT**: Every extracted field is validated against strict Pydantic schemas and assigned a confidence score (0-100%).
**WHY**: Users need to know which fields to trust and which to review.
**HOW**: LLM logprobs (if available) or heuristic checks (e.g., missing standard format = low confidence).
**PROBLEM SOLVED**: Focuses human reviewer attention only on uncertain data.

## 11. Human Review, Corrections, & Audit
**WHAT**: The frontend interface where clinicians review low-confidence data, correct it, and an immutable audit trail records changes.
**WHY**: 100% AI accuracy is impossible; legal/medical standards require human accountability.
**HOW**: Django tracks `created_by`, `updated_by`, and utilizes libraries like `django-simple-history`.
**PROBLEM SOLVED**: Maintains clinical safety and regulatory compliance.

## 12. Asynchronous Processing (Celery & RabbitMQ)
**WHAT**: Background task queue.
**WHY**: Document processing takes seconds to minutes; synchronous HTTP would timeout.
**HOW**: Django sends messages to RabbitMQ, Celery workers consume and process.
**PROBLEM SOLVED**: Scalable, non-blocking UI.

## 13. System Reliability: Transactions, Idempotency, Retries
**WHAT**: Database ACID transactions, idempotent task design, and exponential backoff retries.
**WHY**: Network failures and API limits happen.
**HOW**: Django `atomic` blocks; Celery `autoretry_for`. Tasks check state before executing to prevent double-processing.
**PROBLEM SOLVED**: Prevents duplicate data and corrupted states during failures.

## 14. Observability: Correlation IDs, Logging, Analytics, Health
**WHAT**: End-to-end tracking of requests.
**WHY**: Distributed systems are hard to debug.
**HOW**: Middleware injects Correlation UUIDs. Structured JSON logging (structlog). Healthcheck endpoints.
**PROBLEM SOLVED**: Rapid RCA (Root Cause Analysis) for failed documents.

## 15. API Design & Examples
**WHAT**: RESTful JSON APIs.
**Examples**:
- `POST /api/v1/documents/` (Upload)
- `GET /api/v1/documents/{id}/` (Status)
- `PATCH /api/v1/extractions/{id}/` (Human Correction)

## 16. Data Schema & Relationships
**WHAT**: Relational design. `Patient` 1:N `Document` 1:N `ExtractionTask` 1:N `ExtractedField`.

## 17. Deployment: Docker & Configuration
**WHAT**: Containerized via Docker Compose for local/dev, Kubernetes for Prod. 12-factor app config via environment variables.

## 18. Testing, Failures & Performance
**WHAT**: Pytest for backend, Jest for frontend. Mocked LLM APIs. Load testing via Locust.

## 19. Limitations & Future Roadmap
**Limitations**: High API costs at scale, VLM latency.
**Future**: Fine-tuned on-premise models (Llama 3) to reduce API dependency, multi-modal cross-document reasoning.

## 20. Troubleshooting
Check Celery logs for OCR/LLM failures. Ensure S3 bucket permissions are correct. Verify RabbitMQ is accepting connections.

---
*End of Documentation*
