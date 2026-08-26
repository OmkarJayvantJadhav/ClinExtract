# Slide 1: Title
# ClinExtract: Clinical Document Extraction System
- Transforming unstructured clinical documents into structured, actionable data.
- Built with Python, FastAPI, React, and Gemini.

---

# Slide 2: Problem Statement
- Healthcare providers deal with mountains of unstructured medical records, lab reports, and prescriptions.
- Manual data entry is slow, error-prone, and expensive.
- Missing or misinterpreted clinical data can negatively impact patient care.

---

# Slide 3: Project Objectives
- Automate the extraction of structured data from clinical PDFs and images.
- Provide high accuracy through multi-modal extraction (OCR + LLM).
- Enable human-in-the-loop review for low-confidence extractions.
- Ensure security and traceability of patient health information (PHI).

---

# Slide 4: System Architecture
- **Frontend**: React SPA for document upload, review, and search.
- **Backend**: FastAPI for RESTful endpoints.
- **Database**: PostgreSQL (relational data) and Elasticsearch (search).
- **Storage**: MinIO/S3 for document storage.
- **Worker**: Celery + Redis for asynchronous processing.

---

# Slide 5: Tech Stack
- **Language**: Python 3.10+, TypeScript
- **Frameworks**: FastAPI, React, TailwindCSS
- **Data Store**: PostgreSQL, Elasticsearch, Redis, MinIO
- **AI/ML**: Tesseract OCR, Google Gemini API
- **Infrastructure**: Docker, Docker Compose

---

# Slide 6: Document Lifecycle
1. **Ingestion**: User uploads document (PDF/Image).
2. **Preprocessing**: File conversion and OCR.
3. **Extraction**: Rule-based and LLM-based entity extraction.
4. **Validation**: Schema checking and confidence scoring.
5. **Review**: Human validation (if required).
6. **Finalization**: Data indexed and ready for downstream use.

---

# Slide 7: Document Upload
- Secure REST API endpoint (`/documents/upload`).
- Validates file type, size, and content.
- Generates a unique tracking ID.
- Queues asynchronous processing tasks.

---

# Slide 8: Optical Character Recognition (OCR)
- Uses Tesseract to extract raw text from images and scanned PDFs.
- Handles layout analysis and artifact removal.
- Stores OCR output as intermediate representation.

---

# Slide 9: Document Artifact Generation
- Splits multi-page documents into individual pages.
- Converts pages to normalized images for the Gemini API.
- Stores references to pages for provenance tracking.

---

# Slide 10: Information Extraction Strategy
- Hybrid approach for maximum accuracy and resilience.
- **Tier 1**: Deterministic rule-based extraction (RegEx) for standard formats (dates, IDs).
- **Tier 2**: LLM-based extraction (Gemini) for complex, unstructured clinical narratives.

---

# Slide 11: Rule-based Extraction
- Fast, predictable, and fully explainable.
- Ideal for structured fields (DOB, MRN, Phone Numbers).
- Serves as a baseline and cross-reference for AI extraction.

---

# Slide 12: Gemini Integration
- Leverages Google's Gemini for multimodal understanding.
- Passes both raw OCR text and original document images.
- Uses prompt engineering to enforce structured JSON output matching FHIR/custom schemas.

---

# Slide 13: Fallback Mechanisms
- If Gemini API fails or times out, the system falls back to rule-based extraction.
- Ensures the system remains operational under API degradation.
- Flags documents for manual review if fallback is triggered.

---

# Slide 14: Data Validation
- Validates extracted data against strict Pydantic models.
- Checks semantic validity (e.g., discharge date > admission date).
- Calculates an overall confidence score based on extraction source and validation rules.

---

# Slide 15: Human Review Workflow
- Documents with confidence scores below a threshold are flagged for review.
- UI highlights extracted fields on the original document image.
- Reviewers can accept, modify, or reject extractions.

---

# Slide 16: Data Provenance
- Every extracted entity points back to its source (Page #, Bounding Box, Source System).
- Critical for medical and legal auditability.
- Ensures trust in the AI-extracted data.

---

# Slide 17: Security & PHI Handling
- All data in transit encrypted (TLS).
- Documents stored with encryption at rest.
- Role-Based Access Control (RBAC) restricts access to PHI.
- Audit logging of all access and modifications.

---

# Slide 18: Celery Task Queues
- Handles long-running OCR and LLM tasks outside the HTTP request-response cycle.
- Improves API responsiveness and scalability.
- Supports retries, dead-letter queues, and task monitoring.

---

# Slide 19: Observability
- **Metrics**: Prometheus (Task queue length, API latency).
- **Logging**: Structured JSON logging (ELK stack).
- **Tracing**: OpenTelemetry for distributed request tracing.

---

# Slide 20: Testing Strategy
- **Unit Tests**: Pytest for business logic and data models.
- **Integration Tests**: API endpoints and database interactions.
- **E2E Tests**: Cypress for frontend workflows.

---

# Slide 21: Adversarial Testing
- Testing system resilience against edge cases:
  - Upside-down or blurred scans.
  - Handwritten notes mixed with typed text.
  - Unexpected or malformed file formats.

---

# Slide 22: Docker & Deployment
- Containerized microservices using Docker Compose.
- Ensures consistency across dev, staging, and production environments.
- Easy to scale individual components (e.g., more Celery workers).

---

# Slide 23: Demo
- [Placeholder for live system demonstration]
- Show upload -> processing -> extraction -> review.

---

# Slide 24: Limitations
- OCR struggles with poor handwriting.
- Gemini API latency and rate limits.
- Requires domain experts to configure complex validation rules.

---

# Slide 25: Future Roadmap
- Support for DICOM medical imaging extraction.
- Fine-tuning a local LLM for sensitive data handling (air-gapped deployments).
- Integration with major EHR systems via HL7 FHIR interfaces.
