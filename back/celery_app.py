from __future__ import annotations

from celery import Celery

from back.config import settings


celery_app = Celery(
    "million_miles",
    broker=settings.celery_broker_url,
    backend=settings.resolved_celery_result_backend,
)

celery_app.conf.update(
    timezone="Europe/Moscow",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    beat_schedule={
        "carsensor-sync-watchdog": {
            "task": "back.tasks.ensure_sync_due",
            "schedule": 60.0,
        }
    },
)

celery_app.autodiscover_tasks(["back"])
