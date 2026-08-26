from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
import os

def create_presentation(output_path):
    prs = Presentation()
    
    # --- Custom Theme / Slide Size ---
    # Optional: Set 16:9 aspect ratio
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    def add_slide(title, bullet_points):
        slide_layout = prs.slide_layouts[1] # Title and Content
        slide = prs.slides.add_slide(slide_layout)
        title_shape = slide.shapes.title
        title_shape.text = title
        
        body_shape = slide.placeholders[1]
        tf = body_shape.text_frame
        
        for i, pt in enumerate(bullet_points):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = pt
            p.font.size = Pt(24)
            p.space_after = Pt(14)
            
    def add_title_slide(title, subtitle):
        slide_layout = prs.slide_layouts[0] # Title Slide
        slide = prs.slides.add_slide(slide_layout)
        title_shape = slide.shapes.title
        subtitle_shape = slide.placeholders[1]
        
        title_shape.text = title
        subtitle_shape.text = subtitle

    # Slide 1: Title
    add_title_slide(
        "ClinExtract",
        "AI-Assisted Clinical Document Extraction and Human-in-the-Loop Validation Platform\n\nTechnologies: FastAPI, React, PostgreSQL, Celery, Tesseract, Gemini\nVersion: v1.0.0"
    )

    # Slide 2: Problem Statement
    add_slide(
        "Problem Statement",
        [
            "Clinical documents are messy: Native PDFs, scanned images, mixed documents, and noisy OCR.",
            "Inconsistent layouts make regex or template-based extraction brittle.",
            "Simply extracting text is insufficient; we need structured data with high confidence.",
            "Requirements: Ingestion, OCR, extraction, validation, human correction, and auditability."
        ]
    )

    # Slide 3: Project Objectives
    add_slide(
        "Project Objectives",
        [
            "Secure document ingestion (path traversal protection, magic bytes)",
            "Reliable OCR/preprocessing (deskew, thresholding)",
            "Structured clinical extraction (LLM/VLM + Rules)",
            "AI-assisted extraction with deterministic fallback",
            "Confidence calculation and validation rules",
            "Human-in-the-loop review for flagged documents",
            "Immutable AI provenance & auditability",
            "Asynchronous processing (Celery + RabbitMQ)",
            "Operational observability"
        ]
    )

    # Slide 4: High-Level Architecture
    add_slide(
        "High-Level Architecture",
        [
            "Frontend: React + Vite + TanStack Query",
            "Gateway: FastAPI handles Auth, RBAC, CSRF",
            "Database: PostgreSQL via SQLAlchemy",
            "Broker: RabbitMQ queues tasks",
            "Worker: Celery executes async extraction",
            "Processing: PyMuPDF + OpenCV + Tesseract",
            "AI: Google Gemini LLM/VLM",
            "Storage: Local Volume for PDFs and OCR artifacts"
        ]
    )

    # Slide 5: Technology Stack
    add_slide(
        "Technology Stack",
        [
            "Frontend: React, Vite, Tailwind CSS, TanStack Query",
            "Backend: FastAPI, Pydantic, SQLAlchemy, Alembic",
            "Async: Celery, RabbitMQ",
            "Database: PostgreSQL 15",
            "Document Processing: PyMuPDF, Tesseract, OpenCV, Pillow",
            "AI: Google Gemini API (google-genai)",
            "Security: Argon2, JWT, HttpOnly Cookies, CSRF tokens",
            "Infrastructure: Docker, Docker Compose"
        ]
    )

    # Slide 6: Document Lifecycle
    add_slide(
        "Document Lifecycle",
        [
            "UPLOADED: File secured and stored",
            "PROCESSING: Celery worker takes ownership (Job=RUNNING)",
            "VALIDATION: Rules applied to extraction output",
            "REVIEW_REQUIRED: If validation fails or confidence is low",
            "AUTO_ACCEPTED: If all fields are valid and high confidence",
            "REVIEW_IN_PROGRESS: Claimed by a human reviewer",
            "HUMAN_APPROVED / REJECTED: Final manual decision",
            "Note: Document.status is distinct from ProcessingJob.status"
        ]
    )

    # Slide 7: Secure Document Intake
    add_slide(
        "Secure Document Intake",
        [
            "Multipart upload with strict size limits",
            "MIME and magic-byte validation (prevents disguised executables)",
            "Path traversal protection via UUID-based storage keys",
            "Storage abstraction pattern (currently Local Storage)",
            "Persistent Docker volume isolates files from application code",
            "Why magic bytes? File extensions can be trivially spoofed."
        ]
    )

    # Slide 8: OCR / Document Preprocessing
    add_slide(
        "OCR & Document Preprocessing",
        [
            "Phase 7 Pipeline separates text vs image logic.",
            "Native PDF: PyMuPDF extracts text, words, and bounding boxes directly.",
            "Scanned PDF/Image: OpenCV converts, deskews, and applies thresholding.",
            "Tesseract OCR: Extracts text, bounding boxes, and confidence scores.",
            "Coordinates are normalized to [x_min, y_min, width, height] relative to page dimensions."
        ]
    )

    # Slide 9: Structured OCR Artifact
    add_slide(
        "Structured OCR Artifact",
        [
            "Generated JSON artifact stores the entire visual layout.",
            "Fields: schema_version, document_id, job_id, pages, words, coordinates, confidence.",
            "Why JSON instead of PostgreSQL?",
            "- OCR yields thousands of words per document.",
            "- Relational DBs are inefficient for massive unstructured coordinate arrays.",
            "- JSON artifact acts as an immutable point-in-time source of truth."
        ]
    )

    # Slide 10: Extraction Architecture
    add_slide(
        "Extraction Architecture",
        [
            "BaseExtractor: Abstract interface.",
            "Implementations: RuleBasedExtractor, LLMExtractor, VLMExtractor, MockProvider.",
            "ExtractionFactory: Instantiates provider based on config.",
            "Why abstraction? Allows seamless swapping of AI models without changing business logic.",
            "Makes system completely provider-agnostic and highly testable."
        ]
    )

    # Slide 11: Rule-Based Extraction
    add_slide(
        "Rule-Based Extraction",
        [
            "Deterministic fallback extraction using RegEx.",
            "Extracts standard fields (e.g., Patient Name, DOB, Hemoglobin).",
            "Maps regex text spans back to OCR words to calculate precise bounding boxes.",
            "Averages confidence of the matched words.",
            "Preserves provenance (Provider=rule_based)."
        ]
    )

    # Slide 12: Gemini LLM/VLM
    add_slide(
        "Gemini LLM/VLM Integration",
        [
            "Uses official `google-genai` SDK with Structured Output (Pydantic schema).",
            "LLM Mode: Feeds raw OCR text into Gemini for nuanced extraction.",
            "VLM Mode: Feeds actual page images into Gemini for layout-aware extraction.",
            "Error Handling: Retries on 429/503; fails fast on 400 (Bad Request).",
            "Note: Gemini quota applies. Mock providers used for CI/CD."
        ]
    )

    # Slide 13: Fallback Architecture
    add_slide(
        "Deterministic Fallback",
        [
            "AI is inherently unpredictable (hallucinations, API outages).",
            "If Gemini extraction fails (Exception, Invalid Schema, Rate Limit):",
            "  -> Checks EXTRACTION_FALLBACK_ENABLED",
            "  -> If true, gracefully degrades to RuleBasedExtractor",
            "Logs original failure reason and fallback metadata for auditability.",
            "Ensures the system never stalls purely due to external API failures."
        ]
    )

    # Slide 14: Validation & Confidence
    add_slide(
        "Validation & Confidence (Phase 9)",
        [
            "Data Normalization: Casts text to YYYY-MM-DD or Float.",
            "Validation Rules: Checks required fields and reference ranges.",
            "Confidence Calculation: Aggregates OCR confidence + AI confidence.",
            "Source Mismatch: Flags discrepancies between text and expected format.",
            "If ANY field fails validation -> Document becomes REVIEW_REQUIRED.",
            "If ALL fields valid -> Document becomes AUTO_ACCEPTED."
        ]
    )

    # Slide 15: Human-In-The-Loop
    add_slide(
        "Human-In-The-Loop Review",
        [
            "Review Queue: Lists documents needing attention.",
            "Claim: Exclusive row-lock prevents concurrent editing.",
            "Correction: Reviewer fixes flagged fields via interactive UI.",
            "Re-validation: System strictly re-runs validation on corrected values.",
            "Approve/Reject: Finalizes the document lifecycle."
        ]
    )

    # Slide 16: AI Provenance
    add_slide(
        "Immutable AI Provenance",
        [
            "Original AI extraction is strictly IMMUTABLE.",
            "Human corrections do NOT overwrite the `extracted_fields` table.",
            "Instead, a new row is inserted into `field_corrections`.",
            "Why? Auditability, debugging AI drift, and regulatory compliance.",
            "We must always know exactly what the AI predicted vs what the human entered."
        ]
    )

    # Slide 17: Security
    add_slide(
        "Security Implementation",
        [
            "Argon2 password hashing",
            "HttpOnly, SameSite Cookies for JWT (prevents XSS theft)",
            "Double-Submit Cookie CSRF protection (prevents cross-site forgery)",
            "Strict RBAC (Admin, Reviewer, Operator)",
            "Path traversal protection for file uploads",
            "No sensitive PHI logging in stdout",
            "Immutable audit trails for every state change"
        ]
    )

    # Slide 18: Asynchronous Processing
    add_slide(
        "Asynchronous Processing (Celery)",
        [
            "Why Celery? OCR and LLM calls can take 10-60 seconds.",
            "FastAPI delegates work via RabbitMQ, responding with 201 Created immediately.",
            "Celery Workers consume tasks with `acks_late=True` (idempotency).",
            "Row-level locking (SELECT FOR UPDATE) prevents race conditions.",
            "Correlation IDs trace jobs across API -> RabbitMQ -> Celery."
        ]
    )

    # Slide 19: Observability
    add_slide(
        "Observability",
        [
            "Structured JSON-compatible logging.",
            "Correlation IDs link requests to async tasks.",
            "Comprehensive Audit Logs track 'Who did What and When'.",
            "Analytics API provides processing throughput and validation rates.",
            "Deep Health Endpoint: Checks DB, RabbitMQ, and Celery Worker pulse."
        ]
    )

    # Slide 20: Testing Strategy
    add_slide(
        "Testing Strategy",
        [
            "Backend: 43 passing Pytest test cases.",
            "Covers Auth, RBAC, CSRF, Uploads, Extraction, Validation.",
            "Includes manual regression fixtures (corrupt PDFs, varied OCR).",
            "Mock Provider used in tests to ensure determinism and avoid API costs.",
            "Frontend: Linter and Build checks verified.",
            "Docker: All 5 services start flawlessly."
        ]
    )

    # Slide 21: Adversarial Testing
    add_slide(
        "Adversarial Testing (Phase 10)",
        [
            "Standard 'happy path' testing is insufficient.",
            "Tested specific attack vectors:",
            "- Claiming already-claimed reviews (Concurrency)",
            "- Correcting fields owned by others (Ownership)",
            "- Approving invalid corrections (Re-validation bypass)",
            "- Corrupt PDF ingestion",
            "Ensures true enterprise-grade robustness."
        ]
    )

    # Slide 22: Docker Deployment
    add_slide(
        "Docker Deployment",
        [
            "5 Services: db, rabbitmq, backend, worker, frontend.",
            "Isolated `clin_network`.",
            "Health checks ensure DB and RabbitMQ are ready before Backend/Worker start.",
            "Persistent volumes for PostgreSQL data and uploaded documents.",
            "Environment variables manage configuration securely (no hardcoded keys)."
        ]
    )

    # Slide 23: Demonstration Flow
    add_slide(
        "Demonstration Flow",
        [
            "1. Login as Admin/Reviewer",
            "2. Upload synthetic clinical PDF",
            "3. Observe real-time Processing status",
            "4. Review flagged document in Workspace",
            "5. Correct a low-confidence field (e.g. Hemoglobin)",
            "6. Approve document",
            "7. View Audit Logs & System Health"
        ]
    )

    # Slide 24: Limitations
    add_slide(
        "Limitations",
        [
            "Local Storage: Currently uses mounted volumes instead of S3/MinIO.",
            "Schema: Limited to basic patient/lab schema, requires extension for complex EHR.",
            "Costs: Gemini VLM calls can become expensive at scale.",
            "Data: Evaluated on synthetic data, no formal HIPAA/GDPR certification yet.",
            "Load Testing: Not yet battle-tested under massive concurrent load."
        ]
    )

    # Slide 25: Future Scope
    add_slide(
        "Future Scope",
        [
            "Integrate S3 / MinIO for scalable object storage.",
            "Support additional AI Providers (e.g. Anthropic, OpenAI).",
            "Implement a formal AI model evaluation/calibration framework.",
            "Expand clinical schemas (ICD-10, SNOMED CT extraction).",
            "Migrate to Kubernetes for distributed auto-scaling deployment."
        ]
    )

    prs.save(output_path)
    print(f"Presentation saved to {output_path}")

if __name__ == "__main__":
    create_presentation(os.path.join(os.path.dirname(__file__), "ClinExtract_Project_Presentation.pptx"))
