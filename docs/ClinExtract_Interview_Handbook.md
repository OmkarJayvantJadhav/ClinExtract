# ClinExtract Interview Handbook

This handbook provides technical interview questions and answers organized by architectural levels for the ClinExtract project.

## 1. Overview

**Q1: What is the primary problem ClinExtract solves, and what is its high-level architecture?**
* **SHORT ANSWER:** ClinExtract automates the extraction of clinical data from medical documents using OCR and NLP, reducing manual data entry.
* **DETAILED ANSWER:** ClinExtract is designed to process unstructured medical documents (like PDFs and images), extract relevant clinical entities (e.g., patient demographics, diagnoses, medications), and store them in a structured format. The architecture consists of a FastAPI backend, a PostgreSQL database for structured data, Redis/Celery for asynchronous task queueing, Tesseract/EasyOCR for optical character recognition, and Hugging Face Transformers for AI-driven NER (Named Entity Recognition).
* **PROJECT-SPECIFIC EXAMPLE:** When a user uploads a patient's discharge summary PDF, the FastAPI endpoint accepts it, saves it to AWS S3, and enqueues a Celery task. The worker pulls the file, runs OCR to get text, passes the text to an NLP model to extract the discharge date and medications, and saves the results to PostgreSQL.
* **COMMON MISTAKE:** Assuming the process is synchronous. Processing documents is heavily I/O and CPU bound, so trying to do this in the main request thread will lead to timeouts and poor scalability.

**Q2: How does ClinExtract handle scalability during high document ingestion?**
* **SHORT ANSWER:** It uses horizontal scaling of Celery workers and a message broker (Redis/RabbitMQ) to distribute the load.
* **DETAILED ANSWER:** To handle high ingestion rates, the API nodes are decoupled from the processing nodes. FastAPI simply accepts the file and returns a task ID. The actual heavy lifting (OCR and NLP) is done by Celery workers. By increasing the number of Celery worker instances across multiple nodes, the system can scale horizontally to process thousands of documents in parallel.
* **PROJECT-SPECIFIC EXAMPLE:** During a bulk upload of 1,000 lab reports, Redis holds 1,000 messages. We can spin up 10 Celery workers, each processing documents concurrently, without overwhelming the FastAPI web server.
* **COMMON MISTAKE:** Scaling the web servers instead of the background workers, which doesn't solve the bottleneck since the web servers are mostly idle waiting for the workers to finish.

**Q3: What are the key data privacy considerations for a system like ClinExtract?**
* **SHORT ANSWER:** HIPAA compliance, data encryption at rest and in transit, and role-based access control (RBAC).
* **DETAILED ANSWER:** Since ClinExtract processes PHI (Protected Health Information), it must adhere to strict security standards. Data in transit must be secured via TLS. Data at rest (both in the database and file storage) must be encrypted (e.g., AES-256). Furthermore, the application must enforce strict RBAC to ensure users only access documents they are authorized to view, and comprehensive audit logging must be implemented.
* **PROJECT-SPECIFIC EXAMPLE:** When storing the extracted patient names and SSNs in PostgreSQL, these fields might be encrypted at the column level or the entire database storage volume is encrypted.
* **COMMON MISTAKE:** Storing raw PHI in application logs (e.g., logging "Processing document for John Doe"), which violates HIPAA.

## 2. Backend (FastAPI)

**Q1: Why was FastAPI chosen over Django or Flask for ClinExtract?**
* **SHORT ANSWER:** High performance, native async support, and automatic OpenAPI documentation.
* **DETAILED ANSWER:** ClinExtract benefits from FastAPI's asynchronous capabilities (using `asyncio`), which is crucial for handling multiple concurrent I/O bound operations like database queries or cloud storage uploads. Additionally, FastAPI is built on Starlette and Pydantic, offering excellent performance and automatic data validation, plus self-generating Swagger UI documentation which is great for frontend integration.
* **PROJECT-SPECIFIC EXAMPLE:** The endpoint `POST /upload` uses `async def` and `UploadFile` to efficiently stream large PDF uploads to disk/S3 without blocking the main event loop.
* **COMMON MISTAKE:** Using blocking synchronous functions (like `time.sleep` or synchronous `requests.get`) inside an `async def` endpoint, which blocks the entire event loop.

**Q2: How does FastAPI handle data validation and serialization?**
* **SHORT ANSWER:** Through Pydantic models.
* **DETAILED ANSWER:** Pydantic is used to declare the shape of the data as classes with type hints. FastAPI uses these models to automatically validate incoming JSON payloads, convert data types (e.g., string to datetime), and serialize outgoing responses. If validation fails, FastAPI automatically returns a 422 Unprocessable Entity error with detailed information.
* **PROJECT-SPECIFIC EXAMPLE:** A `DocumentCreate` Pydantic model ensures that an uploaded document metadata includes a valid `patient_id` (integer) and `document_type` (enum), rejecting invalid requests before they reach the business logic.
* **COMMON MISTAKE:** Not using `response_model` in endpoints, which can lead to accidentally leaking sensitive internal database fields (like passwords or internal IDs) to the client.

## 3. Database (PostgreSQL)

**Q1: How do you model a many-to-many relationship in PostgreSQL for extracted entities?**
* **SHORT ANSWER:** Using an associative (join) table with foreign keys to both parent tables.
* **DETAILED ANSWER:** If a document can contain multiple medical entities (like medications) and a medication can appear in multiple documents, we create an associative table (e.g., `document_medications`) containing `document_id` and `medication_id`.
* **PROJECT-SPECIFIC EXAMPLE:** The `Document` table has an ID, and the `Entity` table has an ID. The `DocumentEntity` table links them, perhaps adding contextual data like the `confidence_score` of the extraction or the `bounding_box` coordinates in the document.
* **COMMON MISTAKE:** Storing lists of entity IDs as comma-separated strings in a single column, which violates 1NF and makes querying extremely slow and complex.

**Q2: How would you optimize query performance for searching documents by patient ID?**
* **SHORT ANSWER:** By creating an index on the `patient_id` column.
* **DETAILED ANSWER:** An index (usually a B-Tree) allows PostgreSQL to find the relevant rows without scanning the entire table (a sequential scan). This significantly speeds up read queries, although it slightly slows down writes and consumes extra disk space.
* **PROJECT-SPECIFIC EXAMPLE:** `CREATE INDEX idx_document_patient_id ON documents (patient_id);` This ensures that fetching all historical records for a specific patient is fast, even when the `documents` table grows to millions of rows.
* **COMMON MISTAKE:** Over-indexing every column, which degrades insert/update performance and bloats the database size unnecessarily.

## 4. OCR (Tesseract / EasyOCR)

**Q1: What are the trade-offs between using Tesseract and EasyOCR in ClinExtract?**
* **SHORT ANSWER:** Tesseract is faster and CPU-efficient but less accurate on complex layouts; EasyOCR is deep-learning based, more accurate, but slower and benefits heavily from a GPU.
* **DETAILED ANSWER:** Tesseract is a traditional OCR engine using LSTM, highly optimized for standard, clean document text. EasyOCR uses PyTorch and deep learning models (CRAFT for text detection), which makes it much better at reading messy, skewed, or handwritten text, but it requires significant compute power (preferably CUDA).
* **PROJECT-SPECIFIC EXAMPLE:** ClinExtract might use a two-tiered approach: run Tesseract first for standard printed clinical notes, and fallback to EasyOCR if the confidence score is below a threshold or if the document is flagged as handwritten.
* **COMMON MISTAKE:** Running EasyOCR on a CPU-only Celery worker for high-volume processing, leading to massive processing backlogs.

## 5. AI / ML (NLP)

**Q1: How do we extract specific medical entities (like medications or diagnoses) from the OCR text?**
* **SHORT ANSWER:** Using a Named Entity Recognition (NER) model, such as a fine-tuned BERT or BioBERT model.
* **DETAILED ANSWER:** Once OCR extracts raw text, the text is tokenized and fed into a transformer model fine-tuned on medical corpora (like BioBERT or ClinicalBERT). The model classifies each token into categories (e.g., B-MED, I-MED, B-DIAG). We then aggregate these tokens to extract the full entity.
* **PROJECT-SPECIFIC EXAMPLE:** The text "Patient was prescribed 50mg of Metoprolol" is processed. The model tags "50mg" as DOSAGE and "Metoprolol" as MEDICATION.
* **COMMON MISTAKE:** Not handling the context limit (e.g., 512 tokens for standard BERT). Medical documents can be long, so the text must be chunked carefully using a sliding window approach before feeding it to the model.

## 6. Celery (Task Queue)

**Q1: How do you handle transient failures during the OCR or NLP processing in Celery?**
* **SHORT ANSWER:** By implementing task retries with exponential backoff.
* **DETAILED ANSWER:** Celery allows you to configure automatic retries for specific exceptions (like a temporary database connection error or an external API timeout). Exponential backoff ensures that we don't overwhelm the failing service by progressively increasing the wait time between retries.
* **PROJECT-SPECIFIC EXAMPLE:** If the NLP model is hosted on a separate GPU server and that server returns a 503 error, the Celery task catches the `RequestException` and calls `self.retry(countdown=2 ** self.request.retries)`.
* **COMMON MISTAKE:** Retrying infinitely or retrying on fatal errors (like a permanently corrupted PDF), which clogs up the queue with poison pills.

## 7. Security

**Q1: How do you prevent SQL Injection in the ClinExtract backend?**
* **SHORT ANSWER:** By using an ORM (like SQLAlchemy) or parameterized queries.
* **DETAILED ANSWER:** SQL injection occurs when user input is directly concatenated into SQL queries. SQLAlchemy uses parameterized queries natively, ensuring that user input is treated strictly as data, not executable code.
* **PROJECT-SPECIFIC EXAMPLE:** When a user searches for a patient name, `session.query(Patient).filter(Patient.name == user_input)` safely parameterizes `user_input` behind the scenes.
* **COMMON MISTAKE:** Using raw string formatting for queries: `session.execute(f"SELECT * FROM patients WHERE name = '{user_input}'")`.

## 8. System Design

**Q1: If the system needs to process 100,000 documents a day, how would you architect the storage layer?**
* **SHORT ANSWER:** Store raw files in Object Storage (S3) and metadata/extracted data in a relational database (PostgreSQL).
* **DETAILED ANSWER:** Relational databases are not designed to store large binary blobs efficiently. Storing 100k PDFs a day in PostgreSQL would quickly bloat the DB, degrading performance and increasing backup costs. Object storage like AWS S3 is infinitely scalable and cheap.
* **PROJECT-SPECIFIC EXAMPLE:** ClinExtract saves the uploaded `report.pdf` to an S3 bucket, retrieves the S3 URL (or object key), and stores only the URL and file metadata in the `Document` table in PostgreSQL.
* **COMMON MISTAKE:** Storing the actual PDF bytes in a PostgreSQL `BYTEA` column.

## 9. Adversarial

**Q1: How would you handle a malicious user uploading a massive "zip bomb" disguised as a PDF?**
* **SHORT ANSWER:** Implement strict file size limits and validate file signatures (magic numbers).
* **DETAILED ANSWER:** A malicious upload can exhaust memory or disk space. The backend must enforce a strict `MAX_UPLOAD_SIZE` at the web server level (e.g., Nginx) and the application level (FastAPI). Additionally, we must inspect the file's first few bytes (magic numbers) to ensure it is genuinely a PDF or image, not just a renamed `.zip` or executable.
* **PROJECT-SPECIFIC EXAMPLE:** In FastAPI, we can read the first 1024 bytes to check for the `%PDF-` signature and raise a 400 error if it doesn't match, preventing further processing.
* **COMMON MISTAKE:** Relying solely on the `Content-Type` header from the client or the file extension, both of which can be easily spoofed.
