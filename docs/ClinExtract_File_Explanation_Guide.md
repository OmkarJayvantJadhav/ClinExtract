# ClinExtract File Explanation Guide

This guide provides a comprehensive "Explain Any File" breakdown for the key files and modules in the ClinExtract project. Each section covers Purpose, Imports, Classes, Functions, Data Flow, Database Interaction, Security, Failure Scenarios, Interview Questions, and multi-level explanations.

---

## 1. Core Backend Configuration & Setup

### `config.py`
- **Purpose**: Manages application configuration and environment variables.
- **Imports**: `pydantic_settings.BaseSettings`, `functools.lru_cache`.
- **Classes**: `Settings` (inherits from `BaseSettings`).
- **Functions**: `get_settings()` (caches the settings instance).
- **Data flow**: Reads `.env` / env vars -> Pydantic validates types -> returns structured config object.
- **DB interaction**: Holds DB connection strings; no active queries.
- **Security**: Prevents hardcoding of secrets; validates required security variables are present.
- **Failure**: App refuses to start if required configs (like `DATABASE_URL`) are missing.
- **Interview Questions**: How do you manage secrets in FastAPI? Why use `lru_cache` on `get_settings`?
- **30-sec explanation**: The central place to load and validate all environment variables.
- **2-min explanation**: Uses Pydantic to strictly type-check environment variables on startup. The `get_settings` function is cached so the app only reads the disk/environment once, making it fast to inject settings anywhere.
- **Deep explanation**: Enforces the 12-factor app configuration methodology. By separating config from code, the same Docker image can be deployed to staging and production just by changing the environment. Pydantic ensures that if a port should be an integer, the app fails fast if a string is provided.

### `database.py`
- **Purpose**: Configures SQLAlchemy, creates the connection pool, and manages sessions.
- **Imports**: `sqlalchemy`, `sqlalchemy.orm.sessionmaker`.
- **Classes**: `Base` (Declarative mapping base).
- **Functions**: `get_db()` (Dependency for providing DB sessions).
- **Data flow**: Engine created with connection pool -> `SessionLocal` spawns sessions -> `get_db` yields session per request.
- **DB interaction**: Initializes the ORM layer; handles connection pooling limits.
- **Security**: Connection pooling mitigates DoS via connection exhaustion.
- **Failure**: DB unreachable on startup, connection timeouts.
- **Interview Questions**: Explain connection pooling. How do you tie a DB session to a FastAPI request lifecycle?
- **30-sec explanation**: Sets up the connection to Postgres so the app can read/write data.
- **2-min explanation**: Configures SQLAlchemy's engine and session factory. `get_db` is a generator that gives each API request a unique, isolated database transaction and ensures it closes when the request ends.
- **Deep explanation**: The engine manages a pool of TCP connections to Postgres. `get_db` yields a session, tying the transaction to the request context. If an exception occurs in the route, the session is cleanly rolled back and the connection is returned to the pool, preventing memory leaks and orphaned connections.

### `logging.py`
- **Purpose**: Configures structured logging across the application.
- **Imports**: `logging`, `logging.config`, `json`.
- **Classes**: Custom formatters (e.g., `JSONFormatter`).
- **Functions**: `setup_logging()`.
- **Data flow**: Log statement -> Formatter -> Handlers (Console, File) -> Output.
- **DB interaction**: None.
- **Security**: Must ensure PII and sensitive data (passwords, tokens) are filtered out of logs.
- **Failure**: Disk full (if logging to file), though usually logs output to stdout in containerized environments.
- **Interview Questions**: Why is structured JSON logging important? How do you prevent logging sensitive data?
- **30-sec explanation**: Sets up how the app outputs debug and error messages.
- **2-min explanation**: Configures Python's built-in logging module to output in standard formats (like JSON) so that external tools (like ELK or Datadog) can easily parse and search the application's logs.
- **Deep explanation**: In distributed systems, simple text logs are hard to search. This file configures structured logging, attaching metadata (request IDs, timestamps, log levels) as JSON keys. It centralizes the logging configuration so uvicorn, fastapi, and custom modules all output uniform logs.

---

## 2. API Routing & Middleware

### `middleware.py`
- **Purpose**: Intercepts requests/responses for global logic (CORS, timing, request IDs).
- **Imports**: `starlette.middleware.base`, `fastapi.Request`.
- **Classes**: `LoggingMiddleware`, `TimingMiddleware`.
- **Functions**: Middleware dispatch functions.
- **Data flow**: Request -> Middleware -> Router -> Middleware -> Response.
- **DB interaction**: Minimal (perhaps checking tenant state, but generally avoided for performance).
- **Security**: Enforces CORS (Cross-Origin Resource Sharing) policies and security headers (HSTS).
- **Failure**: Unhandled exceptions in middleware crash the request before it hits the route.
- **Interview Questions**: What is the difference between middleware and a dependency in FastAPI?
- **30-sec explanation**: Code that runs on every single request and response, like a bouncer at a club.
- **2-min explanation**: Middleware sits at the ASGI level. It can look at incoming requests (to add tracking IDs) and outgoing responses (to inject CORS headers or log the execution time).
- **Deep explanation**: Because middleware runs on every request, it must be highly optimized. Unlike dependencies which are explicitly injected where needed, middleware is implicit and global. It's ideal for infrastructural concerns (timing, CORS, generic error trapping) but bad for business logic.

### `router.py` / `API Routes`
- **Purpose**: Defines the HTTP endpoints and maps them to handler functions.
- **Imports**: `fastapi.APIRouter`, schemas, dependencies, specific services.
- **Classes**: None (usually function-based).
- **Functions**: Route handlers (e.g., `@router.post("/upload") def upload_file(...)`).
- **Data flow**: Request URL/Body -> FastAPI Validation -> Router Handler -> Service Layer -> DB.
- **DB interaction**: Passes DB sessions from dependencies to service/CRUD functions.
- **Security**: Applies auth dependencies (e.g., `Depends(get_current_user)`); validates payload schemas to prevent injection.
- **Failure**: Validation errors (422), Unauthorized (401), Internal Errors (500).
- **Interview Questions**: How does FastAPI validate incoming JSON? How do you structure large API projects?
- **30-sec explanation**: The "URLs" of the app. It maps a web URL to a specific Python function.
- **2-min explanation**: APIRouters group related endpoints (like `/users` or `/documents`). They define the HTTP method (GET, POST), the URL path, the expected input schema, and the output schema. FastAPI uses this to generate the Swagger UI automatically.
- **Deep explanation**: Route handlers act as the presentation layer. They should contain minimal business logic. Their job is solely to parse incoming HTTP data, pass it to the service/processing layer, handle domain exceptions, and format the HTTP response.

### `deps.py`
- **Purpose**: Holds FastAPI dependencies (reusable logic tied to request lifecycle).
- **Imports**: `fastapi.Depends`, security modules, database session getters.
- **Classes**: Dependency callables.
- **Functions**: `get_current_user()`, `verify_api_key()`.
- **Data flow**: Request -> Dependency executed -> Result injected into route handler.
- **DB interaction**: Queries DB to fetch user objects for authentication.
- **Security**: The core of endpoint security; ensures users are authenticated and authorized.
- **Failure**: Raises `HTTPException` if auth fails, blocking the request from hitting the router.
- **Interview Questions**: What is dependency injection? Why is it useful in testing?
- **30-sec explanation**: Reusable helper functions that run before a route, mostly used for checking if a user is logged in.
- **2-min explanation**: FastAPI's dependency injection system allows you to write functions that extract data from a request (like a JWT token) and validate it. Routes simply declare they need this data, and FastAPI handles executing the dependency and passing the result.
- **Deep explanation**: Dependencies create a directed acyclic graph (DAG) of execution. They are highly modular and can be overridden during unit testing (e.g., `app.dependency_overrides[get_current_user] = mock_user`). This allows testing routes without needing a real database or real authentication tokens.

---

## 3. Data Layer

### `models/` (SQLAlchemy Models)
- **Purpose**: Defines the database schema and object-relational mapping (ORM).
- **Imports**: `sqlalchemy` columns, relationships, types.
- **Classes**: `User`, `Document`, `ExtractedData` (inheriting from `Base`).
- **Functions**: None (declarative).
- **Data flow**: Python object manipulations are translated into SQL queries by SQLAlchemy.
- **DB interaction**: Direct representation of DB tables.
- **Security**: Prevents SQL injection by using ORM parameter binding.
- **Failure**: Integrity errors (unique constraints, foreign key violations) on save.
- **Interview Questions**: What is the N+1 query problem in ORMs? What's the difference between a model and a schema?
- **30-sec explanation**: Python classes that represent tables in the database.
- **2-min explanation**: These files map database concepts (like foreign keys and columns) to Python objects. If you have a `documents` table, you have a `Document` model. SQLAlchemy uses these to automatically generate SQL queries.
- **Deep explanation**: Models handle the state of data as it exists in persistent storage. They define complex relationships (one-to-many, many-to-many) and cascading behaviors. They should not be used to validate incoming HTTP data (that's what schemas are for).

### `schemas/` (Pydantic Models)
- **Purpose**: Defines data validation and serialization shapes.
- **Imports**: `pydantic.BaseModel`, `pydantic.Field`.
- **Classes**: `DocumentCreate`, `DocumentResponse`, `UserLogin`.
- **Functions**: Custom Pydantic validators (`@field_validator`).
- **Data flow**: Incoming JSON -> Pydantic validates -> Python dict/object -> ORM.
- **DB interaction**: None directly, but frequently used to validate data before DB insertion.
- **Security**: Strips out unexpected fields; sanitizes input; prevents mass-assignment vulnerabilities.
- **Failure**: Raises `ValidationError` resulting in HTTP 422 Unprocessable Entity.
- **Interview Questions**: Contrast SQLAlchemy models with Pydantic schemas. How do you handle password validation?
- **30-sec explanation**: Defines the exact shape and rules of data coming in and going out of the API.
- **2-min explanation**: Pydantic schemas ensure that an incoming request has all the required fields (e.g., email is a valid email string, age is an integer). They are also used to format responses, hiding sensitive data like passwords from the output.
- **Deep explanation**: Schemas act as an anti-corruption layer. Incoming HTTP requests are dirty and untrusted. Pydantic parses them, strictly types them, and yields a clean Python object. Using separate Create, Update, and Response schemas prevents accidental data leaks and enforces strict API contracts.

### `alembic/env.py`
- **Purpose**: Bootstraps the Alembic migration environment.
- **Imports**: `logging`, `alembic.context`, `database.Base`, `models`.
- **Classes**: None.
- **Functions**: `run_migrations_offline()`, `run_migrations_online()`.
- **Data flow**: Reads DB url -> connects -> compares Model metadata with DB schema -> generates/runs SQL migrations.
- **DB interaction**: Directly manipulates database DDL (tables, columns, indexes).
- **Security**: Migrations must not inadvertently drop sensitive data tables or alter permissions.
- **Failure**: Migration failures can leave the DB in an inconsistent state (requires transaction rollbacks).
- **Interview Questions**: How do schema migrations work? Why is `env.py` important in Alembic?
- **30-sec explanation**: The script that figures out how to update the database schema when you change a Python Model.
- **2-min explanation**: When you add a column to a SQLAlchemy model, Alembic uses `env.py` to connect to the database, look at the current schema, and generate a migration script (like `ALTER TABLE`) to safely update the database to match your code.
- **Deep explanation**: `env.py` bridges your SQLAlchemy `Base.metadata` and the Alembic execution context. It configures the database URL dynamically (often overriding `alembic.ini` with environment variables) and sets up the transaction for running migrations, ensuring that schema changes are tracked in version control.

---

## 4. Business Logic & Processing

### `storage/`
- **Purpose**: Abstracts file storage (local disk, AWS S3, Azure Blob).
- **Imports**: `boto3` (for S3), `os`, `shutil`.
- **Classes**: `StorageService`, `S3Storage`, `LocalStorage`.
- **Functions**: `upload_file()`, `download_file()`, `delete_file()`.
- **Data flow**: Route -> Storage Service -> Cloud Provider/Disk.
- **DB interaction**: None (only stores file pointers/URLs in the DB, not the files themselves).
- **Security**: Handles presigned URLs for secure access; ensures uploaded files are not malicious.
- **Failure**: Network timeouts to S3, disk out of space, permission denied.
- **Interview Questions**: Why shouldn't you store large files in a PostgreSQL database?
- **30-sec explanation**: Saves user-uploaded files (like PDFs) to a hard drive or cloud storage.
- **2-min explanation**: Provides an interface for saving and retrieving files. By abstracting it behind a class, the app can easily switch from saving files in a local folder during development to saving them in AWS S3 in production without changing the rest of the code.
- **Deep explanation**: Storage modules implement the Repository pattern for binary blobs. They handle chunked uploads for large files to avoid memory exhaustion, generate secure signed URLs for private downloads, and handle provider-specific exceptions gracefully.

### `processing/` & `extraction/` & `validation/`
- **Purpose**: The core logic of ClinExtract: parsing clinical documents, running ML/rules, and validating medical data.
- **Imports**: PDF parsers (`PyMuPDF`), NLP libraries (`spaCy`, `transformers`), validation rules.
- **Classes**: `ClinicalExtractor`, `OCRProcessor`, `DataValidator`.
- **Functions**: `process_document()`, `extract_entities()`, `validate_fhir_schema()`.
- **Data flow**: Raw File -> Text Extraction (OCR/PDF) -> NLP Extraction -> Schema Validation -> DB.
- **DB interaction**: Reads configuration rules; writes extracted structured data.
- **Security**: Must handle malformed or malicious PDFs (e.g., zip bombs) safely. Protects PHI (Protected Health Information).
- **Failure**: Unreadable documents, unsupported formats, NLP model timeouts, out-of-memory errors on large PDFs.
- **Interview Questions**: How do you handle long-running extraction tasks in a web API?
- **30-sec explanation**: The "brain" of the app. It reads medical PDFs and pulls out the important data.
- **2-min explanation**: These modules take a raw document, convert it to text, and use rules or AI to find medical terms (like diagnoses or medications). The validation module then ensures the extracted data makes medical sense before saving it.
- **Deep explanation**: This is the domain logic. `processing/` handles the physical file (OCR, text splitting). `extraction/` applies domain-specific algorithms (NER, regex, LLM prompts) to structure unstructured text. `validation/` enforces strict healthcare standards (like FHIR compliance, value set checking). These operations are CPU-bound and usually offloaded to background workers.

### `worker/` (Background Tasks)
- **Purpose**: Handles async, long-running background jobs (like document processing).
- **Imports**: `celery`, `redis`, processing modules.
- **Classes**: Celery Task definitions.
- **Functions**: `@celery.task def run_extraction_job(...)`.
- **Data flow**: API queues message in Redis/RabbitMQ -> Worker picks up message -> Processes -> Updates DB.
- **DB interaction**: Updates task status (Pending -> Processing -> Completed/Failed).
- **Security**: Workers need secure access to the DB and Storage, often running in private subnets.
- **Failure**: Task failures require retry logic, dead-letter queues, and error logging.
- **Interview Questions**: Why use Celery/RabbitMQ instead of `BackgroundTasks` in FastAPI?
- **30-sec explanation**: A separate program that runs heavy tasks in the background so the main API stays fast.
- **2-min explanation**: When a user uploads a 100-page PDF, we can't make them wait 5 minutes for the HTTP response. The API quickly replies "Upload received," and puts a message in a queue. The `worker` picks up that message and processes the document asynchronously.
- **Deep explanation**: Built on Celery or a similar task queue, the worker module isolates CPU-intensive or long-running IO tasks from the ASGI event loop. It provides durability (if the worker crashes, the message remains in the broker to be retried) and scalability (you can spin up 10 worker containers independently of the API containers).

---

## 5. Frontend UI/UX

### `frontend context/` (React/Vue Context)
- **Purpose**: Manages global state in the frontend application.
- **Imports**: `createContext`, `useContext`, `useReducer`.
- **Classes/Functions**: `AuthProvider`, `AppStateProvider`.
- **Data flow**: API calls -> Context State -> UI Components react to state changes.
- **DB interaction**: None directly (communicates entirely via API).
- **Security**: Stores JWTs (preferably in HttpOnly cookies, but often in state/local storage).
- **Failure**: Stale state if not properly synced with the backend.
- **Interview Questions**: When should you use Context vs. Redux vs. local component state?
- **30-sec explanation**: The frontend's memory, keeping track of who is logged in and what data is loaded.
- **2-min explanation**: React Context provides a way to pass data through the component tree without having to pass props down manually at every level. It's used for global themes, user authentication status, and shared application data.
- **Deep explanation**: Context mitigates "prop drilling." It establishes a provider at the root level holding state and dispatch functions. Any deeply nested component can consume this context to trigger API calls or update the UI, providing a centralized store for global client-side state.

### `routes/` & `pages/`
- **Purpose**: Defines frontend navigation and high-level view structures.
- **Imports**: `react-router-dom`, layout components, specific page views.
- **Classes/Functions**: `AppRouter`, `DashboardPage`, `UploadPage`.
- **Data flow**: URL change -> Router mounts Page component -> Page fetches data -> Renders UI.
- **DB interaction**: None.
- **Security**: Route guards (e.g., `ProtectedRoute`) redirect unauthenticated users to login.
- **Failure**: 404 pages for unknown routes, ErrorBoundaries for rendering crashes.
- **Interview Questions**: How does client-side routing differ from server-side routing?
- **30-sec explanation**: Determines what screen to show based on the URL the user is on.
- **2-min explanation**: Pages are the big screens of the app (like the Dashboard or Settings). The routes file maps URLs (like `/settings`) to these Page components, allowing the user to navigate the app without the browser reloading the page.
- **Deep explanation**: Client-side routing intercepts browser navigation events and dynamically swaps out the React DOM tree. `pages/` act as "smart" container components that orchestrate data fetching (via React Query/SWR) and pass that data down to "dumb" presentation components.

### `services/` (Frontend API Clients)
- **Purpose**: Handles all HTTP communication with the backend API.
- **Imports**: `axios` or native `fetch`.
- **Classes/Functions**: `apiClient`, `authService.login()`, `documentService.upload()`.
- **Data flow**: Component -> Service function -> Axios -> Network -> API.
- **DB interaction**: None.
- **Security**: Attaches authorization headers (Bearer tokens) to outbound requests. Handles CSRF tokens.
- **Failure**: Handles network errors, timeouts, and translates API 400/500s into user-friendly error messages.
- **Interview Questions**: How do you implement global error handling or token refresh in an Axios instance?
- **30-sec explanation**: The frontend's messenger that talks to the backend API.
- **2-min explanation**: Instead of writing `fetch()` calls inside UI buttons, all network logic is grouped into services. This makes it easy to add authorization tokens to every request and gives a single place to handle scenarios like logging a user out if the server says their token expired.
- **Deep explanation**: Usually implemented as an Axios instance with interceptors. Request interceptors automatically attach JWTs. Response interceptors globally catch 401 Unauthorized responses to trigger token refresh flows or redirect to the login page, abstracting network complexity away from the UI components.

---

## 6. Infrastructure & Deployment

### `Dockerfile`
- **Purpose**: Defines the blueprint for building isolated, reproducible application images.
- **Imports**: Base images (e.g., `FROM python:3.11-slim`).
- **Commands**: `RUN apt-get`, `COPY requirements.txt`, `WORKDIR`, `CMD`.
- **Data flow**: Source code + OS dependencies -> Docker Build -> Immutable Image.
- **DB interaction**: None at build time.
- **Security**: Must run as a non-root user. Should minimize image surface area (slim images).
- **Failure**: Build fails if dependencies clash. Container crashes on boot if `CMD` fails.
- **Interview Questions**: What is a multi-stage Docker build and why use it?
- **30-sec explanation**: A recipe that packages the app and all its dependencies into a single runnable box.
- **2-min explanation**: It starts with a base operating system, installs Python, copies our code in, and installs the required libraries. This guarantees that if the app works on a developer's laptop, it will work exactly the same way on the production server.
- **Deep explanation**: Dockerfiles provide immutable infrastructure. Best practices dictate ordering commands to maximize layer caching (e.g., copying `requirements.txt` and installing dependencies before copying source code). Multi-stage builds can be used to compile assets and then copy only the final artifacts into a minimal runtime image, reducing attack surface and image size.

### `docker-compose.yml`
- **Purpose**: Orchestrates multi-container applications (API, Database, Redis, Workers).
- **Imports**: None (YAML configuration file).
- **Definitions**: `services`, `volumes`, `networks`.
- **Data flow**: `docker-compose up` -> Docker daemon reads config -> Starts DB -> Starts Redis -> Starts API/Workers.
- **DB interaction**: Spins up the PostgreSQL database container and mounts persistent volumes.
- **Security**: Defines private internal networks so the DB is not exposed to the public internet.
- **Failure**: A service might crash on boot if it depends on the DB but the DB isn't fully ready yet (requires `depends_on` and healthchecks).
- **Interview Questions**: How does networking work between containers in Docker Compose?
- **30-sec explanation**: A single file that starts the database, the backend, the frontend, and the workers all together.
- **2-min explanation**: While a Dockerfile defines *one* piece of the app, Compose defines the *whole system*. It tells Docker to run Postgres, Redis, the web API, and the Celery worker, and wires them together so they can talk to each other using simple names like `http://database:5432`.
- **Deep explanation**: Compose defines infrastructure as code for local development and simple deployments. It manages named volumes to ensure database data survives container restarts. It sets environment variables, maps ports to the host machine, and defines startup orders and restart policies, replicating a production-like microservice architecture locally.
