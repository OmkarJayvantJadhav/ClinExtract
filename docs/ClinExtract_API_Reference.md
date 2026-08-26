# ClinExtract API Reference

This document provides a comprehensive reference for the ClinExtract API, built with FastAPI. It covers all endpoints across authentication, users, documents, jobs, extractions, reviews, audit, analytics, and health services.

## Base URL
`/api/v1`

## Authentication
Most endpoints require a valid JWT bearer token.
- **Header**: `Authorization: Bearer <token>`

## Role-Based Access Control (RBAC)
Roles:
- `ADMIN`: Full access to all resources.
- `REVIEWER`: Can claim, review, and complete document reviews.
- `OPERATOR`: Can upload documents and trigger jobs.
- `VIEWER`: Read-only access to documents and analytics.

---

## 1. Auth (`/auth`)

### 1.1 Login
- **Method**: `POST`
- **Path**: `/auth/login`
- **Auth**: None
- **RBAC**: None
- **Request Body**: `OAuth2PasswordRequestForm` (username, password)
- **Response**: `UserResponse` (includes `access_token` and `token_type`)
- **Status Codes**: 
  - `200 OK`
  - `401 Unauthorized` (Invalid credentials)
- **DB Effect**: None
- **Security**: Rate limited.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/auth/login" \
       -H "Content-Type: application/x-www-form-urlencoded" \
       -d "username=admin&password=secret"
  ```

### 1.2 Logout
- **Method**: `POST`
- **Path**: `/auth/logout`
- **Auth**: Required
- **RBAC**: Any authenticated user
- **Request Body**: None
- **Response**: `{"message": "Successfully logged out"}`
- **Status Codes**: `200 OK`, `401 Unauthorized`
- **DB Effect**: Invalidates current token session.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/auth/logout" \
       -H "Authorization: Bearer <token>"
  ```

### 1.3 Get Current User
- **Method**: `GET`
- **Path**: `/auth/me`
- **Auth**: Required
- **RBAC**: Any authenticated user
- **Response**: `UserResponse`
- **Status Codes**: `200 OK`, `401 Unauthorized`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/auth/me" \
       -H "Authorization: Bearer <token>"
  ```

---

## 2. Users (`/users`)

### 2.1 Admin Only Route
- **Method**: `GET`
- **Path**: `/users/admin-only`
- **Auth**: Required
- **RBAC**: `ADMIN`
- **Response**: `List[UserResponse]`
- **Status Codes**: `200 OK`, `403 Forbidden`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/users/admin-only" -H "Authorization: Bearer <token>"
  ```

### 2.2 Reviewer Plus
- **Method**: `GET`
- **Path**: `/users/reviewer-plus`
- **Auth**: Required
- **RBAC**: `REVIEWER`, `ADMIN`
- **Response**: `List[UserResponse]`
- **Status Codes**: `200 OK`, `403 Forbidden`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/users/reviewer-plus" -H "Authorization: Bearer <token>"
  ```

### 2.3 Operator Plus
- **Method**: `GET`
- **Path**: `/users/operator-plus`
- **Auth**: Required
- **RBAC**: `OPERATOR`, `ADMIN`
- **Response**: `List[UserResponse]`
- **Status Codes**: `200 OK`, `403 Forbidden`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/users/operator-plus" -H "Authorization: Bearer <token>"
  ```

### 2.4 Viewer Plus
- **Method**: `GET`
- **Path**: `/users/viewer-plus`
- **Auth**: Required
- **RBAC**: `VIEWER`, `OPERATOR`, `REVIEWER`, `ADMIN`
- **Response**: `List[UserResponse]`
- **Status Codes**: `200 OK`, `403 Forbidden`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/users/viewer-plus" -H "Authorization: Bearer <token>"
  ```

### 2.5 Dummy Mutation
- **Method**: `POST`
- **Path**: `/users/dummy-mutation`
- **Auth**: Required
- **RBAC**: `ADMIN`
- **Response**: `{"status": "success"}`
- **Status Codes**: `200 OK`, `403 Forbidden`
- **DB Effect**: Test mutation on user record.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/users/dummy-mutation" -H "Authorization: Bearer <token>"
  ```

---

## 3. Documents (`/documents`)

### 3.1 List Documents
- **Method**: `GET`
- **Path**: `/documents`
- **Auth**: Required
- **RBAC**: `VIEWER` and above
- **Query Params**: `page` (int), `size` (int), `status` (string)
- **Response**: `PaginatedDocumentResponse`
- **Status Codes**: `200 OK`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/documents?page=1&size=10" -H "Authorization: Bearer <token>"
  ```

### 3.2 Upload Document
- **Method**: `POST`
- **Path**: `/documents`
- **Auth**: Required
- **RBAC**: `OPERATOR` and above
- **Request Body**: `multipart/form-data` (file)
- **Response**: `DocumentResponse`
- **Status Codes**: `201 Created`, `400 Bad Request`
- **DB Effect**: Creates a new document record. Uploads file to object storage.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/documents" \
       -H "Authorization: Bearer <token>" \
       -F "file=@/path/to/clinical_record.pdf"
  ```

### 3.3 Get Document Details
- **Method**: `GET`
- **Path**: `/documents/{document_id}`
- **Auth**: Required
- **RBAC**: `VIEWER` and above
- **Response**: `DocumentDetailResponse`
- **Status Codes**: `200 OK`, `404 Not Found`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/documents/123" -H "Authorization: Bearer <token>"
  ```

---

## 4. Jobs (`/jobs`)

### 4.1 Get Job Status
- **Method**: `GET`
- **Path**: `/jobs/{job_id}`
- **Auth**: Required
- **RBAC**: `VIEWER` and above
- **Response**: `JobResponse` (id, status, progress, error)
- **Status Codes**: `200 OK`, `404 Not Found`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/jobs/job_abc123" -H "Authorization: Bearer <token>"
  ```

---

## 5. Extractions (`/extractions`)

### 5.1 Trigger Extraction
- **Method**: `POST`
- **Path**: `/extractions/{document_id}`
- **Auth**: Required
- **RBAC**: `OPERATOR` and above
- **Request Body**: Extraction parameters (optional)
- **Response**: `{"job_id": "string", "status": "processing"}`
- **Status Codes**: `202 Accepted`, `404 Not Found`
- **DB Effect**: Enqueues an extraction job in the background.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/extractions/123" -H "Authorization: Bearer <token>"
  ```

### 5.2 Get Extraction Results
- **Method**: `GET`
- **Path**: `/extractions/{document_id}`
- **Auth**: Required
- **RBAC**: `VIEWER` and above
- **Response**: `ExtractionResultResponse` (extracted clinical entities, confidence scores)
- **Status Codes**: `200 OK`, `404 Not Found`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/extractions/123" -H "Authorization: Bearer <token>"
  ```

---

## 6. Reviews (`/reviews`)

### 6.1 Claim Document for Review
- **Method**: `POST`
- **Path**: `/reviews/{document_id}/claim`
- **Auth**: Required
- **RBAC**: `REVIEWER` and above
- **Response**: `ReviewResponse`
- **Status Codes**: `201 Created`, `400 Bad Request` (already claimed), `404 Not Found`
- **DB Effect**: Assigns document review to the current user. Updates document status to `IN_REVIEW`.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/reviews/123/claim" -H "Authorization: Bearer <token>"
  ```

### 6.2 Complete Review
- **Method**: `POST`
- **Path**: `/reviews/{document_id}/complete`
- **Auth**: Required
- **RBAC**: `REVIEWER` and above (must be the assignee)
- **Request Body**: `ReviewCompletionRequest` (corrections, notes)
- **Response**: `ReviewResponse`
- **Status Codes**: `200 OK`, `403 Forbidden` (not assigned to you), `404 Not Found`
- **DB Effect**: Updates extracted data, marks document as `COMPLETED`.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/reviews/123/complete" \
       -H "Authorization: Bearer <token>" \
       -H "Content-Type: application/json" \
       -d '{"notes": "Verified patient demographics"}'
  ```

### 6.3 Release Review
- **Method**: `POST`
- **Path**: `/reviews/{document_id}/release`
- **Auth**: Required
- **RBAC**: `REVIEWER` and above
- **Response**: `ReviewResponse`
- **Status Codes**: `200 OK`, `404 Not Found`
- **DB Effect**: Unassigns document, reverts status to `PENDING_REVIEW`.
- **cURL Example**:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/reviews/123/release" -H "Authorization: Bearer <token>"
  ```

### 6.4 Get Review Details
- **Method**: `GET`
- **Path**: `/reviews/{document_id}`
- **Auth**: Required
- **RBAC**: `REVIEWER` and above
- **Response**: `ReviewResponse`
- **Status Codes**: `200 OK`, `404 Not Found`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/reviews/123" -H "Authorization: Bearer <token>"
  ```

---

## 7. Audit (`/audit`)

### 7.1 Get Audit Logs
- **Method**: `GET`
- **Path**: `/audit`
- **Auth**: Required
- **RBAC**: `ADMIN`
- **Query Params**: `start_date`, `end_date`, `user_id`, `action`
- **Response**: `Dict[str, Any]` (paginated logs)
- **Status Codes**: `200 OK`, `403 Forbidden`
- **DB Effect**: None
- **Security**: Sensitive audit data, restricted to ADMIN.
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/audit?action=LOGIN" -H "Authorization: Bearer <token>"
  ```

---

## 8. Analytics (`/analytics`)

### 8.1 Get Metrics
- **Method**: `GET`
- **Path**: `/analytics/metrics`
- **Auth**: Required
- **RBAC**: `VIEWER` and above
- **Response**: `Dict[str, Any]` (total documents, processing success rate, average review time)
- **Status Codes**: `200 OK`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/analytics/metrics" -H "Authorization: Bearer <token>"
  ```

---

## 9. Health (`/health`)

### 9.1 Basic Health Check
- **Method**: `GET`
- **Path**: `/health`
- **Auth**: None
- **RBAC**: None
- **Response**: `HealthResponse` (`{"status": "ok"}`)
- **Status Codes**: `200 OK`, `503 Service Unavailable`
- **DB Effect**: None
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/health"
  ```

### 9.2 Detailed Health Check
- **Method**: `GET`
- **Path**: `/health/detailed`
- **Auth**: Required
- **RBAC**: `ADMIN`
- **Response**: `Dict[str, Any]` (DB status, redis status, external API status)
- **Status Codes**: `200 OK`, `503 Service Unavailable`
- **DB Effect**: Pings database to check connection.
- **cURL Example**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/health/detailed" -H "Authorization: Bearer <token>"
  ```
