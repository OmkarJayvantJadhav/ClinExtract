# ClinExtract Troubleshooting Handbook

This handbook provides a systematic guide to diagnosing and resolving 22 common failure scenarios in the ClinExtract application.

---

## 1. Backend Startup
**SYMPTOM:** FastAPI backend crashes immediately upon `docker-compose up` or `uvicorn` start.
**CAUSE:** Missing environment variables, database connection failure, or syntax error in Python code.
**WHERE TO LOOK:** Backend container logs or terminal output.
**COMMAND:** `docker logs clinextract-backend`
**FIX:** Ensure `.env` file exists and has correct DB credentials. Check for missing dependencies or syntax errors in the logs.
**PREVENTION:** Use `.env.example` to enforce environment variable requirements. Add pre-commit hooks for syntax checking.

## 2. Frontend Startup
**SYMPTOM:** React/Vite development server fails to start, or blank white screen on load.
**CAUSE:** Missing `node_modules`, incompatible Node version, or incorrect environment variables (e.g., missing API URL).
**WHERE TO LOOK:** Frontend terminal output, browser console.
**COMMAND:** `npm install && npm run dev`
**FIX:** Run `npm install`. Check `.env` for `VITE_API_BASE_URL`. Verify Node version matches `.nvmrc` or `package.json` engines.
**PREVENTION:** Use Docker for consistent frontend environments or strictly enforce Node versions via `nvm`.

## 3. DB (Database Connection Failure)
**SYMPTOM:** Backend starts but logs show "Connection refused" or "Authentication failed" for PostgreSQL.
**CAUSE:** PostgreSQL container is not running, wrong credentials, or DB not initialized.
**WHERE TO LOOK:** Backend logs, PostgreSQL logs.
**COMMAND:** `docker logs clinextract-db` and `docker ps`
**FIX:** Ensure DB container is up. Verify `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `DATABASE_URL` match.
**PREVENTION:** Implement connection retries in the backend startup script. Use health checks in `docker-compose.yml`.

## 4. RabbitMQ Connection Failure
**SYMPTOM:** Celery worker or backend throws "AMQP connection error" or "Connection reset by peer".
**CAUSE:** RabbitMQ container not ready, wrong AMQP URL, or port mismatch.
**WHERE TO LOOK:** Backend logs, Celery worker logs.
**COMMAND:** `docker logs clinextract-rabbitmq`
**FIX:** Verify `CELERY_BROKER_URL` matches RabbitMQ credentials and hostname. Restart RabbitMQ.
**PREVENTION:** Add wait-for-it script or Docker healthcheck to delay worker/backend startup until RabbitMQ is fully ready.

## 5. Worker (Celery/Background Worker Failure)
**SYMPTOM:** Tasks remain in "Pending" state, or worker logs show exceptions during processing.
**CAUSE:** Worker container crashed, missing dependencies for OCR/AI, or unhandled exceptions in task code.
**WHERE TO LOOK:** Celery worker logs.
**COMMAND:** `docker logs clinextract-worker`
**FIX:** Inspect stack trace. Ensure worker has access to necessary volumes (e.g., for uploaded files) and external API keys.
**PREVENTION:** Implement comprehensive error handling and retries for Celery tasks. Set up Dead Letter Queues (DLQ).

## 6. HTTP 401 Unauthorized
**SYMPTOM:** API requests return 401 Unauthorized. User is logged out unexpectedly.
**CAUSE:** Missing, expired, or invalid JWT access token in the `Authorization` header.
**WHERE TO LOOK:** Frontend network tab, backend FastAPI logs.
**COMMAND:** Inspect request headers in browser dev tools.
**FIX:** Clear local storage and log in again. Ensure backend JWT secret matches the token signature. Check token expiration time.
**PREVENTION:** Implement silent token refresh mechanisms in the frontend before the access token expires.

## 7. HTTP 403 Forbidden
**SYMPTOM:** User is logged in but receives 403 Forbidden when accessing certain endpoints.
**CAUSE:** User lacks the necessary role or permissions to perform the action.
**WHERE TO LOOK:** Backend route dependencies (e.g., RoleCheck).
**COMMAND:** Query user role in the database: `SELECT role FROM users WHERE id = <user_id>;`
**FIX:** Assign the correct role to the user in the database or via an admin interface.
**PREVENTION:** Clearly document role-based access control (RBAC) requirements for each endpoint. Return descriptive error messages.

## 8. HTTP 413 Payload Too Large
**SYMPTOM:** File uploads fail with 413 error.
**CAUSE:** Uploaded document exceeds the maximum allowed file size set by Nginx, FastAPI, or the frontend.
**WHERE TO LOOK:** Nginx error logs, FastAPI middleware, frontend network tab.
**COMMAND:** Check `client_max_body_size` in Nginx config.
**FIX:** Increase Nginx `client_max_body_size` or FastAPI `UploadFile` size limits. Configure frontend to reject files exceeding the limit before uploading.
**PREVENTION:** Implement clear file size limits in the UI and validate file size on the client side before initiating the upload.

## 9. HTTP 415 Unsupported Media Type
**SYMPTOM:** File upload fails with 415 error.
**CAUSE:** Uploaded file is not a supported format (e.g., uploading a Word doc when only PDF/Images are allowed).
**WHERE TO LOOK:** FastAPI upload endpoint validation.
**COMMAND:** Inspect the `Content-Type` header of the failed request.
**FIX:** Ensure the client sends the correct `Content-Type`. Update backend validation to accept the necessary MIME types.
**PREVENTION:** Use `accept` attributes on frontend file inputs and provide clear UI guidance on supported formats.

## 10. Stuck Tasks (Processing Never Completes)
**SYMPTOM:** Document status remains "Processing" indefinitely.
**CAUSE:** Celery task crashed silently, worker ran out of memory (OOM), or a long-running process (like OCR) deadlocked.
**WHERE TO LOOK:** Celery worker logs, server memory metrics.
**COMMAND:** `docker stats` to check memory usage, or Celery Flower to monitor task states.
**FIX:** Restart the worker. Increase container memory limits. Implement task timeouts.
**PREVENTION:** Set `soft_time_limit` and `time_limit` on Celery tasks to prevent infinite hanging.

## 11. OCR Failure
**SYMPTOM:** Text extraction returns empty or garbled text, or OCR library throws an error.
**CAUSE:** Unreadable/blurry image, unsupported PDF format, missing system dependencies (e.g., Tesseract or Poppler).
**WHERE TO LOOK:** Celery worker logs.
**COMMAND:** `docker exec -it clinextract-worker tesseract --version` (if using Tesseract).
**FIX:** Ensure system packages for OCR are installed in the Docker image. Improve image pre-processing.
**PREVENTION:** Add basic image quality checks before sending to OCR. Include sample test files in CI/CD to verify OCR functionality.

## 12. Gemini API Failure
**SYMPTOM:** Data extraction fails, backend logs show API errors from Gemini.
**CAUSE:** Invalid prompt, Gemini service outage, or exceeding token limits (context window).
**WHERE TO LOOK:** Celery worker logs for Gemini SDK exceptions.
**COMMAND:** Try a manual curl request to the Gemini API endpoint to test connectivity.
**FIX:** Review and optimize the prompt. Ensure the document size is within the token limit. Handle API exceptions gracefully.
**PREVENTION:** Implement fallback mechanisms or retries with exponential backoff for transient API errors.

## 13. Gemini Auth
**SYMPTOM:** Immediate failure when calling Gemini API with "Unauthorized" or "Invalid API Key" error.
**CAUSE:** `GEMINI_API_KEY` is missing, expired, or invalid.
**WHERE TO LOOK:** Worker environment variables.
**COMMAND:** `docker exec -it clinextract-worker env | grep GEMINI`
**FIX:** Provide a valid Google AI API key in the `.env` file and restart the worker.
**PREVENTION:** Validate API key presence during application startup and fail fast if it's missing.

## 14. Rate Limit Exceeded
**SYMPTOM:** API responds with 429 Too Many Requests, or Gemini API throws quota exceeded errors.
**CAUSE:** Too many requests from a single IP, or exceeding the allowed RPS (Requests Per Second) for external APIs.
**WHERE TO LOOK:** FastAPI rate limiter logs or external API response headers.
**COMMAND:** Check response headers for `Retry-After`.
**FIX:** Wait for the rate limit to reset. If external, consider requesting a quota increase. If internal, adjust FastAPI rate limiting thresholds if legitimate.
**PREVENTION:** Implement rate limiting middleware properly. Use caching to reduce duplicate external API calls.

## 15. Validation Error (Pydantic)
**SYMPTOM:** API returns 422 Unprocessable Entity during request or webhook.
**CAUSE:** Payload does not match the Pydantic schema (e.g., missing required field, wrong data type).
**WHERE TO LOOK:** FastAPI response body detailing the specific field that failed validation.
**COMMAND:** Inspect the JSON body of the 422 response in the browser network tab.
**FIX:** Correct the frontend payload to match the expected schema.
**PREVENTION:** Share TypeScript interfaces generated from OpenAPI specs between frontend and backend to ensure schema consistency.

## 16. Review Conflict
**SYMPTOM:** Clinician tries to save edits to an extracted document, but receives an error or overwrites someone else's work.
**CAUSE:** Concurrent edits by multiple users without optimistic concurrency control.
**WHERE TO LOOK:** Database records, backend update endpoint.
**COMMAND:** Check the `updated_at` or `version` column of the document record.
**FIX:** Reload the document to get the latest version and re-apply edits.
**PREVENTION:** Implement optimistic locking (e.g., passing a `version` or `last_updated` timestamp and failing the update if it mismatches).

## 17. Ownership/Access Violation
**SYMPTOM:** User A can view or edit User B's private documents.
**CAUSE:** Missing tenant/user isolation in database queries.
**WHERE TO LOOK:** Backend CRUD endpoints for documents.
**COMMAND:** Review the SQLAlchemy query for the endpoint.
**FIX:** Always filter queries by `user_id` or `tenant_id` (e.g., `.filter(Document.owner_id == current_user.id)`).
**PREVENTION:** Implement row-level security (RLS) in PostgreSQL or enforce strict ownership checks in repository layer.

## 18. MissingGreenlet (SQLAlchemy)
**SYMPTOM:** Backend throws `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`.
**CAUSE:** Attempting to lazily load a relationship synchronously inside an asynchronous FastAPI endpoint or session.
**WHERE TO LOOK:** FastAPI logs for the stack trace pointing to an SQLAlchemy model attribute access.
**COMMAND:** Search codebase for lazy loading patterns in async contexts.
**FIX:** Use `selectinload` or `joinedload` to eagerly load the required relationships in the async query.
**PREVENTION:** Configure SQLAlchemy with `lazy="raise"` for async setups to catch these issues during development.

## 19. Alembic Migration Failure
**SYMPTOM:** `alembic upgrade head` fails with SQL syntax errors or missing columns.
**CAUSE:** Database schema is out of sync with migration history, or conflicting migration files.
**WHERE TO LOOK:** Terminal output from the Alembic command.
**COMMAND:** `alembic current` and `alembic history`
**FIX:** Resolve conflicts by merging migration branches, or carefully drop and recreate tables (in development only).
**PREVENTION:** Never modify migration files once merged. Always run migrations locally before merging to the main branch.

## 20. Docker Networking Issues
**SYMPTOM:** Containers cannot communicate (e.g., backend cannot reach DB by hostname).
**CAUSE:** Containers are on different Docker networks, or DNS resolution fails.
**WHERE TO LOOK:** Docker network inspection.
**COMMAND:** `docker network inspect clinextract_default`
**FIX:** Ensure all dependent services are declared within the same `docker-compose.yml` network. Use service names (e.g., `db`, `rabbitmq`) as hostnames.
**PREVENTION:** Use explicit networks in `docker-compose.yml` and test container communication via `ping` during initial setup.

## 21. CORS Errors
**SYMPTOM:** Frontend requests are blocked by the browser with a CORS policy error.
**CAUSE:** FastAPI backend is not configured to allow requests from the frontend's origin (URL/Port).
**WHERE TO LOOK:** Browser console errors.
**COMMAND:** Check FastAPI `CORSMiddleware` configuration.
**FIX:** Add the exact frontend URL (including http/https and port) to the `allow_origins` list in the backend configuration.
**PREVENTION:** Configure `CORS_ORIGINS` via environment variables to easily adjust for dev, staging, and production environments.

## 22. CSRF Failures
**SYMPTOM:** Form submissions or state-changing API requests fail with 403 Forbidden or CSRF token mismatch.
**CAUSE:** Missing or invalid CSRF token in headers or cookies when using cookie-based authentication.
**WHERE TO LOOK:** Backend CSRF middleware logs, browser network tab (cookies and headers).
**COMMAND:** Inspect the `X-CSRF-Token` header in the request.
**FIX:** Ensure the frontend extracts the CSRF token from the cookie and attaches it to the request header.
**PREVENTION:** If using pure JWTs in Authorization headers, CSRF is generally not a concern. If using HttpOnly cookies, ensure CSRF protection is properly configured in both frontend and backend.
