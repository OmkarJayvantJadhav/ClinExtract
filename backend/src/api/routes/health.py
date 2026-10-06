import asyncio
import os
import secrets
from datetime import datetime, timezone
from typing import Dict, Any

import aio_pika
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.health import HealthResponse
from src.core.database import get_db
from src.core.config import settings
from src.core import metrics
from src.worker.celery_app import celery_app
from src.api.deps import get_current_user
from src.db.models.user import User
from src.db.models.document import Document, DocumentStatus
from src.db.models.processing_job import ProcessingJob

router = APIRouter()

async def _check_dependencies(db: AsyncSession) -> Dict[str, str]:
    status = {"database": "unavailable", "rabbitmq": "unavailable", "worker": "unavailable", "storage": "unavailable"}

    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
        status["database"] = "healthy"
    except Exception:
        pass

    try:
        # Plain (non-robust) connect: a robust connection keeps reconnecting in the background after a timeout
        connection = await asyncio.wait_for(aio_pika.connect(settings.CELERY_BROKER_URL, timeout=2.0), timeout=3.0)
        await connection.close()
        status["rabbitmq"] = "healthy"
    except Exception:
        pass

    try:
        inspector = celery_app.control.inspect(timeout=1.0)
        if await asyncio.to_thread(inspector.ping):
            status["worker"] = "healthy"
    except Exception:
        pass

    storage_dir = os.getenv("STORAGE_DIR", "/app/data/documents")
    if os.path.isdir(storage_dir) and os.access(storage_dir, os.W_OK):
        status["storage"] = "healthy"

    return status

@router.get("", response_model=HealthResponse)
async def check_health():
    # Liveness: the process is up and serving requests
    return HealthResponse(status="healthy", service="ClinExtract API")

@router.get("/ready")
async def check_ready(db: AsyncSession = Depends(get_db)):
    """Readiness: 200 only when the database is reachable (used by health checks / load balancers)."""
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
    return {"status": "ready"}

@router.get("/detailed", response_model=Dict[str, Any])
async def check_health_detailed(
    db: AsyncSession = Depends(get_db),
    # Infrastructure details are not public; any signed-in user may view them
    current_user: User = Depends(get_current_user),
):
    dependencies = await _check_dependencies(db)
    overall = "healthy" if all(v == "healthy" for v in dependencies.values()) else "degraded"
    return {"status": overall, "service": "ClinExtract API", "dependencies": dependencies}

def _authorize_metrics(request: Request) -> None:
    token = settings.METRICS_TOKEN
    if token:
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied, f"Bearer {token}"):
            raise HTTPException(status_code=401, detail="Invalid metrics token")
    elif settings.APP_ENV == "production":
        raise HTTPException(status_code=404, detail="Not Found")

@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Prometheus scrape endpoint. Requires `Authorization: Bearer $METRICS_TOKEN` when a token is
    configured; disabled in production without one.
    """
    _authorize_metrics(request)

    for dep, state in (await _check_dependencies(db)).items():
        metrics.DEPENDENCY_UP.labels(dep).set(1 if state == "healthy" else 0)

    try:
        doc_counts = dict((await db.execute(select(Document.status, func.count()).group_by(Document.status))).all())
        for st in DocumentStatus:
            metrics.DOCUMENTS_BY_STATUS.labels(st.value).set(doc_counts.get(st, 0))
        for st, count in (await db.execute(select(ProcessingJob.status, func.count()).group_by(ProcessingJob.status))).all():
            metrics.JOBS_BY_STATUS.labels(st.value).set(count)
        oldest = await db.scalar(select(func.min(Document.created_at)).where(Document.status == DocumentStatus.REVIEW_REQUIRED))
        metrics.OLDEST_PENDING_REVIEW_AGE.set((datetime.now(timezone.utc) - oldest).total_seconds() if oldest else 0)
    except Exception:
        pass  # dependency gauges above already report the outage

    body, content_type = metrics.render_latest()
    return Response(content=body, media_type=content_type)
