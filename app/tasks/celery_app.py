"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "lipread_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.transcription_tasks.*": {"queue": "transcription"},
    },
    task_default_queue="default",
    task_default_priority=5,
    worker_concurrency=4,
    task_soft_time_limit=1800,
    task_time_limit=1860,
    task_max_retries=3,
    task_default_retry_delay=60,
    result_expires=3600,
    broker_transport_options={
        "visibility_timeout": 3600,
        "fanout_prefix": True,
        "fanout_patterns": True,
    },
    beat_schedule={
        "cleanup-old-videos": {
            "task": "app.tasks.transcription_tasks.cleanup_old_videos",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)
