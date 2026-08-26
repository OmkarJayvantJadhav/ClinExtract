from celery import Celery
from src.core.config import settings

celery_app = Celery(
    "clinextract_worker",
    broker=settings.CELERY_BROKER_URL,
    include=["src.worker.tasks"]
)

# Optional celery configurations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # In a testing environment, we can run tasks eagerly
    task_always_eager=settings.APP_ENV == "testing",
    task_eager_propagates=True,
)
