from celery import Celery
from backend.config import settings

celery_app = Celery(
    "satquery_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
    include=["backend.tasks.vlm_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
