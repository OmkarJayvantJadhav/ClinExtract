# Architecture Decision Records (ADRs) for ClinExtract

This document records the major architectural decisions made during the design and development of the ClinExtract platform.

## ADR-001: Backend Framework (FastAPI)
**Status:** Accepted
**Context:** The platform requires a performant, asynchronous backend API to handle multiple concurrent document extraction requests, status polling, and data retrieval. We need a framework that is easy to develop in, supports modern Python (type hints), and provides automatic documentation.
**Decision:** We will use FastAPI as the primary backend web framework.
**Alternatives:** 
- Django: Too heavy, synchronous by default, less suitable for an API-first microservices architecture.
- Flask: Lacks native async support and automatic OpenAPI documentation, requiring additional plugins.
**Rationale:** FastAPI provides excellent performance (built on Starlette and Pydantic), native async support which is crucial for handling long-running background tasks and AI API calls, and automatic OpenAPI generation which simplifies frontend integration.
**Trade-offs:** The ecosystem is newer compared to Django/Flask, meaning fewer out-of-the-box extensions for things like admin panels or complex ORM integrations (though SQLAlchemy works well).
**Consequences:** The backend will be highly concurrent. We must ensure all I/O operations (DB, network) use async libraries where possible to avoid blocking the event loop.

## ADR-002: Frontend Framework (React)
**Status:** Accepted
**Context:** We need to build a dynamic, responsive user interface for users to upload documents, review extracted clinical data, and perform human-in-the-loop corrections.
**Decision:** We will use React for the frontend application.
**Alternatives:**
- Vue.js: Good alternative, but React has a larger ecosystem and more available component libraries.
- Angular: Steeper learning curve and more opinionated, which might slow down rapid prototyping.
**Rationale:** React's component-based architecture is ideal for building complex UIs like document viewers alongside data forms. The massive ecosystem ensures we can find libraries for PDF rendering, state management, and complex form handling.
**Trade-offs:** Requires choosing and wiring up additional libraries for routing (e.g., React Router) and state management.
**Consequences:** We will establish a strong component hierarchy and utilize a modern build tool (like Vite or Next.js) to manage the React application.

## ADR-003: Primary Database (PostgreSQL)
**Status:** Accepted
**Context:** We need a robust relational database to store user data, document metadata, extracted clinical entities, extraction provenance, and audit logs. The data model requires complex relationships and transactions.
**Decision:** We will use PostgreSQL as the primary relational database.
**Alternatives:**
- MySQL/MariaDB: Good, but PostgreSQL offers better support for complex data types (JSONB) and advanced analytical queries.
- MongoDB (NoSQL): Not suitable for the highly relational nature of the extracted data and the need for strict ACID transactions.
**Rationale:** PostgreSQL is open-source, highly reliable, and provides advanced features like JSONB columns which are perfect for storing unstructured or semi-structured extraction results or provider-specific metadata while maintaining a relational core.
**Trade-offs:** Slightly more complex setup and tuning compared to simpler databases, but manageable.
**Consequences:** We will use SQLAlchemy (async) as the ORM to interact with PostgreSQL.

## ADR-004: Asynchronous Task Queue (Celery)
**Status:** Accepted
**Context:** Document processing, OCR, and AI extraction are slow, compute-heavy, and network-dependent tasks. They cannot be executed synchronously within an HTTP request cycle.
**Decision:** We will use Celery for background task processing.
**Alternatives:**
- RQ (Redis Queue): Simpler, but less feature-rich for complex workflows, retries, and task routing.
- FastAPI BackgroundTasks: Too simple; does not persist across server restarts and runs in the same process pool.
**Rationale:** Celery is the industry standard for Python asynchronous task queues. It supports robust retries, complex workflows (chains, chords), and integrates well with various message brokers.
**Trade-offs:** Adds complexity to the deployment (requires worker processes and a message broker).
**Consequences:** Document processing will be decoupled from the API. The API will return task IDs, and the frontend must poll or use WebSockets for status updates.

## ADR-005: Message Broker (RabbitMQ)
**Status:** Accepted
**Context:** Celery requires a message broker to route tasks from the web API to the background workers.
**Decision:** We will use RabbitMQ as the message broker.
**Alternatives:**
- Redis: Often used as a broker, but primarily an in-memory datastore. Can lose messages if not configured carefully.
- Amazon SQS: Cloud-locked; we want a solution that can easily run locally in Docker Compose.
**Rationale:** RabbitMQ is a dedicated, highly robust message broker supporting the AMQP protocol. It provides excellent guarantees for message delivery, routing, and persistence, which is critical for ensuring no document processing tasks are lost.
**Trade-offs:** Slightly heavier footprint than Redis.
**Consequences:** We will deploy a RabbitMQ container alongside the API and Celery workers.

## ADR-006: OCR Artifact Storage
**Status:** Accepted
**Context:** The OCR process generates intermediate artifacts (text files, bounding box data, images) that are needed for debugging, human review, and feeding into the AI extraction pipeline.
**Decision:** OCR artifacts will be stored in an object storage system (e.g., AWS S3, or MinIO for local development), with references (URIs) stored in the PostgreSQL database.
**Alternatives:**
- Store in the database (BLOBs): Bloats the database, degrades performance.
- Store on the local file system: Does not scale horizontally across multiple worker nodes.
**Rationale:** Object storage is designed for large binary and text files. MinIO provides an S3-compatible API, allowing easy local development and seamless transition to cloud storage in production.
**Trade-offs:** Requires an additional infrastructure component (MinIO).
**Consequences:** All components accessing documents or OCR results must retrieve them via the object storage API using the stored URIs.

## ADR-007: Provider Abstraction Layer
**Status:** Accepted
**Context:** The platform relies on external AI providers (e.g., Google Gemini, OpenAI, Anthropic) for data extraction. These APIs change, and we may want to switch providers or route requests dynamically based on cost or performance.
**Decision:** We will implement an abstract `AIProvider` interface. All specific provider implementations (e.g., `GeminiProvider`) must conform to this interface.
**Alternatives:**
- Direct API calls: Hardcodes the application to a specific vendor, making switching very difficult and requiring widespread code changes.
**Rationale:** The Strategy pattern allows us to decouple the core extraction logic from the specific AI vendor's API. This ensures vendor neutrality and simplifies testing (we can easily inject a `MockProvider`).
**Trade-offs:** Requires upfront design effort to create a generic interface that accommodates the nuances of different LLMs.
**Consequences:** Adding a new AI provider will only require writing a new class implementing the `AIProvider` interface.

## ADR-008: Rule-Based Fallback Mechanism
**Status:** Accepted
**Context:** LLMs can hallucinate, fail to return valid JSON, or experience downtime. We need a reliable way to extract critical, highly structured data (like dates, patient IDs) if the AI fails.
**Decision:** We will implement a rule-based fallback system (using RegEx, NLP libraries like spaCy, or simple heuristics) that runs if the AI provider fails or returns low-confidence results for specific fields.
**Alternatives:**
- Rely entirely on AI: High risk of data loss or incorrect data when dealing with brittle prompts or API outages.
**Rationale:** Rule-based systems are deterministic and reliable for well-defined patterns. Using them as a fallback increases the overall robustness and accuracy of the extraction pipeline.
**Trade-offs:** Increases development and maintenance burden, as rules must be continually updated to handle new edge cases.
**Consequences:** The extraction pipeline must have logic to evaluate AI results and selectively trigger rule-based extractors for missing or invalid fields.

## ADR-009: Primary AI Provider (Gemini)
**Status:** Accepted
**Context:** We need a powerful Large Language Model to perform zero-shot and few-shot extraction of complex clinical entities from unstructured text.
**Decision:** We will use Google's Gemini models (e.g., Gemini 1.5 Pro/Flash) as the primary AI provider.
**Alternatives:**
- OpenAI GPT-4o: Excellent performance, but Gemini currently offers massive context windows (up to 2M tokens) which is highly beneficial for processing long, multi-page medical records.
- Anthropic Claude 3.5 Sonnet: Also excellent, but Gemini's integration with Google Cloud ecosystem and context window size are strong advantages.
**Rationale:** Gemini's massive context window allows us to process entire patient charts in a single prompt without complex chunking strategies, improving the model's ability to cross-reference information.
**Trade-offs:** Tying the initial implementation heavily to Gemini's specific prompt formats, though mitigated by ADR-007 (Provider Abstraction).
**Consequences:** We will integrate the official Google GenAI SDK.

## ADR-010: Immutable AI Provenance
**Status:** Accepted
**Context:** In healthcare, it is critical to know exactly how a piece of data was generated. If an AI extracted it, we must know which model, version, prompt, and source text were used.
**Decision:** All extracted data points will have an immutable provenance record linked to them. This record will store the AI provider, model version, prompt hash, and a reference to the source document/bounding box.
**Alternatives:**
- Only store the final value: Unacceptable for compliance and auditing in clinical settings.
**Rationale:** Immutable provenance ensures trust in the system. If an error is found, it can be traced back to the specific AI call, allowing for targeted improvements to prompts or models.
**Trade-offs:** Significantly increases the storage requirements and database schema complexity.
**Consequences:** The data model will include a `Provenance` table, and every extracted `Entity` must have a foreign key to it.

## ADR-011: Append-Only Corrections
**Status:** Accepted
**Context:** Users will review and correct the AI-extracted data. We must maintain an audit trail of these changes.
**Decision:** Corrections will be implemented as an append-only log. When a user changes a value, a new record is created with the new value and the user's ID, rather than overwriting the original AI-extracted value. The system will always display the most recent version.
**Alternatives:**
- Overwrite existing data: Destroys the history and makes it impossible to compare AI performance against human corrections.
**Rationale:** An append-only design provides a complete, auditable history of the data's lifecycle. It allows us to calculate metrics on how often the AI is corrected, which is crucial for continuous improvement.
**Trade-offs:** More complex queries to retrieve the "current" state of the data.
**Consequences:** We will use a pattern similar to Event Sourcing or temporal tables for the extracted entities.

## ADR-012: Row-Level Locking
**Status:** Accepted
**Context:** Multiple human reviewers might attempt to open and edit the same document's extracted data simultaneously, leading to race conditions and lost work.
**Decision:** We will implement optimistic or pessimistic row-level locking when a user begins reviewing a document.
**Alternatives:**
- No locking (Last Write Wins): Unacceptable risk of data loss.
- Document-level locking: Prevents collaborative work on different sections of a large document.
**Rationale:** Row-level locking ensures data integrity during concurrent reviews. Pessimistic locking (e.g., marking a record as "checked out") provides better UX by preventing conflicts upfront.
**Trade-offs:** Adds complexity to the state management and requires mechanisms to handle abandoned locks (e.g., timeouts).
**Consequences:** The database schema and API must support locking mechanisms (e.g., a `locked_by` and `locked_at` column).

## ADR-013: Correlation IDs
**Status:** Accepted
**Context:** A single user request (e.g., uploading a document) triggers a complex cascade of events across the API, Celery workers, and external AI services. Tracing an issue through the logs is difficult.
**Decision:** We will implement Correlation IDs. A unique ID will be generated at the API entry point and passed along in all log messages, Celery task contexts, and database audit records.
**Alternatives:**
- Rely on timestamps and contextual clues: Highly inefficient and error-prone during debugging.
**Rationale:** Correlation IDs make distributed tracing trivial. By searching the centralized logging system for a single ID, developers can see the entire lifecycle of a request across all services.
**Trade-offs:** Requires discipline to ensure the ID is properly passed through all service boundaries.
**Consequences:** We will configure FastAPI middleware to generate the ID and Celery signal handlers to inject it into task contexts.

## ADR-014: Validation Architecture
**Status:** Accepted
**Context:** Extracted clinical data must adhere to strict schemas and business rules (e.g., dates must be valid, codes must match specific ontologies).
**Decision:** We will use Pydantic models for data validation at the API boundary and internally within the processing pipeline.
**Alternatives:**
- Manual validation logic: Error-prone, verbose, and difficult to maintain.
- JSON Schema: Good for API definition, but less integrated with Python code than Pydantic.
**Rationale:** Pydantic is native to FastAPI, highly performant, and allows us to define complex validation rules, custom data types, and complex nested structures easily.
**Trade-offs:** Pydantic V2 has a learning curve for complex custom validators.
**Consequences:** All incoming data and AI outputs will be parsed and validated through Pydantic models before touching the database.

## ADR-015: Human Review Workflow
**Status:** Accepted
**Context:** The system is "Human-in-the-loop" (HITL). We need a structured way for users to review, correct, and approve documents.
**Decision:** We will define specific document states (e.g., `Processing`, `Needs Review`, `Approved`, `Rejected`) and build a UI specifically designed for side-by-side comparison of the source document and extracted data.
**Alternatives:**
- Fully automated (No HITL): Unsafe for clinical data given current AI reliability.
**Rationale:** A structured state machine ensures documents are not exported or used until explicitly approved. The side-by-side UI minimizes cognitive load for the reviewer.
**Trade-offs:** Requires significant frontend development effort to build a robust document viewer (PDF.js) linked to form fields.
**Consequences:** The backend will implement an explicit state machine for documents, and the frontend will provide the review interface.

## ADR-016: Local Development (Docker Compose)
**Status:** Accepted
**Context:** The platform consists of multiple services (API, Frontend, Postgres, RabbitMQ, Celery, MinIO). Developers need a consistent and easy way to spin up the entire stack locally.
**Decision:** We will use Docker Compose to define and run the multi-container local development environment.
**Alternatives:**
- Running services bare-metal: Leads to "it works on my machine" issues and complex setup instructions.
- Kubernetes (Minikube): Too complex and resource-heavy for everyday local development.
**Rationale:** Docker Compose is the standard tool for defining multi-container Docker applications. It ensures every developer has identical dependencies and configurations.
**Trade-offs:** Requires developers to understand Docker and consumes more local resources than bare-metal.
**Consequences:** We will maintain a `docker-compose.yml` file that orchestrates all necessary services, including auto-reloading for the API and frontend.
