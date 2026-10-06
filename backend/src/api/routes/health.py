from fastapi import APIRouter, Depends
from src.schemas.health import HealthResponse
from src.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
from src.worker.celery_app import celery_app
import asyncio
import aio_pika
from src.core.config import settings
from src.api.deps import get_current_user
from src.db.models.user import User

router = APIRouter()

@router.get("", response_model=HealthResponse)
async def check_health():
    # Liveness
    return HealthResponse(
        status="healthy",
        service="ClinExtract API"
    )

@router.get("/detailed", response_model=Dict[str, Any])
async def check_health_detailed(
    db: AsyncSession = Depends(get_db),
    # Infrastructure details are not public; any signed-in user may view them
    current_user: User = Depends(get_current_user),
):
    status_db = "unavailable"
    status_rmq = "unavailable"
    status_worker = "unavailable"
    status_storage = "healthy" # Local filesystem storage is implicitly healthy if API runs
    
    # Check DB
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
        status_db = "healthy"
    except Exception:
        pass
        
    # Check RabbitMQ
    try:
        connection = await asyncio.wait_for(
            aio_pika.connect_robust(settings.CELERY_BROKER_URL), timeout=2.0
        )
        await connection.close()
        status_rmq = "healthy"
    except Exception:
        pass
        
    # Check Celery Worker
    try:
        # celery ping
        inspector = celery_app.control.inspect(timeout=1.0)
        ping_result = await asyncio.to_thread(inspector.ping)
        if ping_result:
            status_worker = "healthy"
    except Exception:
        pass
        
    overall = "healthy"
    if status_db != "healthy" or status_rmq != "healthy" or status_worker != "healthy":
        overall = "degraded"
        
    return {
        "status": overall,
        "service": "ClinExtract API",
        "dependencies": {
            "database": status_db,
            "rabbitmq": status_rmq,
            "worker": status_worker,
            "storage": status_storage
        }
    }
