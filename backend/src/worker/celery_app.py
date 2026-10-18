from celery import Celery
from celery.schedules import crontab
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
    # Documents take seconds to minutes each, so a worker process should only reserve the job
    # it is running. With the default (4) idle processes can sit waiting while one busy
    # process holds several queued documents.
    worker_prefetch_multiplier=1,
    # In a testing environment, we can run tasks eagerly
    task_always_eager=settings.APP_ENV == "testing",
    task_eager_propagates=True,
    # Run by the `beat` service (see docker-compose). The retention purge is a no-op unless
    # DOCUMENT_RETENTION_DAYS > 0; the stuck-job sweep resends jobs whose message was lost.
    beat_schedule={
        "purge-expired-documents": {
            "task": "purge_expired_documents",
            "schedule": crontab(hour=3, minute=0),
        },
        "requeue-stuck-jobs": {
            "task": "requeue_stuck_jobs",
            "schedule": crontab(minute="*/10"),
        },
    },
)
