from __future__ import annotations

from back.bootstrap import initialize_runtime
from back.celery_app import celery_app
from back.config import settings
from back.database import Database
from back.services import SyncService
from parser import CarSensorParser


database = Database(settings.database_path)
sync_service = SyncService(database=database, parser=CarSensorParser())
JOB_NAME = "carsensor-sync"


def _run_sync(*, force: bool) -> dict[str, str | int | bool]:
    initialize_runtime(database)
    should_start = database.start_job_if_due(
        JOB_NAME,
        interval_seconds=settings.sync_interval_seconds,
        force=force,
    )
    if not should_start:
        return {"started": False, "synced": 0}

    try:
        result = sync_service.sync(
            max_pages=settings.sync_max_pages,
            max_listings=settings.sync_max_listings,
        )
        result["started"] = True
        return result
    finally:
        database.finish_job(JOB_NAME)


@celery_app.task(name="back.tasks.ensure_sync_due")
def ensure_sync_due() -> dict[str, str | int | bool]:
    return _run_sync(force=False)


@celery_app.task(name="back.tasks.sync_cars_now")
def sync_cars_now() -> dict[str, str | int | bool]:
    return _run_sync(force=True)
