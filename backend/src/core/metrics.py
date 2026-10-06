"""
Prometheus metrics.

Request metrics are recorded by MetricsMiddleware. Pipeline metrics (queue depth, failures,
review backlog) are read from the database at scrape time, so they are correct no matter how
many API/worker processes run.
"""
import time

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter(
    "clinextract_http_requests_total", "HTTP requests", ["method", "route", "status"], registry=REGISTRY,
)
HTTP_LATENCY = Histogram(
    "clinextract_http_request_duration_seconds", "HTTP request latency", ["method", "route"], registry=REGISTRY,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
DOCUMENTS_BY_STATUS = Gauge(
    "clinextract_documents", "Documents by status", ["status"], registry=REGISTRY,
)
JOBS_BY_STATUS = Gauge(
    "clinextract_processing_jobs", "Processing jobs by status", ["status"], registry=REGISTRY,
)
OLDEST_PENDING_REVIEW_AGE = Gauge(
    "clinextract_oldest_pending_review_age_seconds", "Age of the oldest document awaiting review", registry=REGISTRY,
)
DEPENDENCY_UP = Gauge(
    "clinextract_dependency_up", "1 if the dependency is reachable", ["dependency"], registry=REGISTRY,
)

def _route_template(request: Request) -> str:
    """
    Full route template (e.g. /api/v1/documents/{document_id}) to keep label cardinality
    bounded. Rebuilt from the concrete path because included routes only know their
    router-relative path.
    """
    if request.scope.get("route") is None:
        return "unmatched"
    path = request.scope.get("path", "")
    for name, value in (request.scope.get("path_params") or {}).items():
        path = path.replace(f"/{value}", f"/{{{name}}}", 1)
    return path

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            path = _route_template(request)
            HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)

def render_latest() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
