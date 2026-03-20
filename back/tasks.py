from __future__ import annotations

import asyncio
import json
import logging

from back.bootstrap import initialize_runtime
from back.celery_app import celery_app
from back.config import settings
from back.database import Database
from back.localization import build_localized_listing_columns
from back.services import SyncService
from parser import CarSensorParser


database = Database(settings.database_url)
sync_service = SyncService(database=database, parser=CarSensorParser())
JOB_NAME = "carsensor-sync"
TRANSLATION_JOB_NAME = "carsensor-translation"
logger = logging.getLogger(__name__)


async def _translate_sources(sources: list[dict[str, object]]) -> int:
    translated = 0
    for source in sources:
        missing_langs = tuple(source.get("missing_langs", []))
        if not missing_langs:
            continue

        localized = build_localized_listing_columns(
            source["payload_ja"],
            langs=missing_langs,
        )
        updates = {
            key: json.dumps(value, ensure_ascii=False) if key.startswith("payload_") else value
            for key, value in localized.items()
        }
        await database.update_car_localizations(source["listing_id"], updates)
        translated += 1
    return translated


async def _run_sync_async(*, force: bool) -> dict[str, str | int | bool]:
    await initialize_runtime(database)
    logger.info(
        "Evaluating sync job %s force=%s interval_seconds=%s",
        JOB_NAME,
        force,
        settings.sync_interval_seconds,
    )
    should_start = await database.start_job_if_due(
        JOB_NAME,
        interval_seconds=settings.sync_interval_seconds,
        force=force,
    )
    if not should_start:
        logger.info("Skipping sync job %s because it is not due or already running", JOB_NAME)
        return {"started": False, "synced": 0}

    succeeded = False
    try:
        logger.info(
            "Starting sync job %s max_pages=%s max_listings=%s",
            JOB_NAME,
            settings.sync_max_pages,
            settings.sync_max_listings,
        )
        result = await sync_service.sync(
            max_pages=settings.sync_max_pages,
            max_listings=settings.sync_max_listings,
        )
        succeeded = True
        result["started"] = True
        logger.info("Completed sync job %s result=%s", JOB_NAME, result)
        return result
    except Exception:
        logger.exception("Sync job failed")
        raise
    finally:
        await database.finish_job(JOB_NAME, succeeded=succeeded)


def _run_sync(*, force: bool) -> dict[str, str | int | bool]:
    try:
        return asyncio.run(_run_sync_async(force=force))
    finally:
        asyncio.run(database.engine.dispose())


@celery_app.task(name="back.tasks.ensure_sync_due")
def ensure_sync_due() -> dict[str, str | int | bool]:
    logger.info("Received scheduled sync watchdog task")
    return _run_sync(force=False)


@celery_app.task(name="back.tasks.sync_cars_now")
def sync_cars_now() -> dict[str, str | int | bool]:
    logger.info("Received manual sync task")
    return _run_sync(force=True)


async def _ensure_translation_due_async() -> dict[str, int | bool]:
    await initialize_runtime(database)
    logger.info(
        "Evaluating translation job %s interval_seconds=%s batch_size=%s",
        TRANSLATION_JOB_NAME,
        settings.translation_interval_seconds,
        settings.translation_batch_size,
    )
    should_start = await database.start_job_if_due(
        TRANSLATION_JOB_NAME,
        interval_seconds=settings.translation_interval_seconds,
        force=False,
    )
    if not should_start:
        logger.info("Skipping translation job %s because it is not due or already running", TRANSLATION_JOB_NAME)
        return {"started": False, "translated": 0, "missing": 0}

    succeeded = False
    pending = await database.get_cars_missing_localization(settings.translation_batch_size)
    try:
        translated = await _translate_sources(pending)

        succeeded = True
        result = {
            "started": True,
            "translated": translated,
            "missing": max(0, len(pending) - translated),
        }
        logger.info("Completed translation job %s result=%s", TRANSLATION_JOB_NAME, result)
        return result
    finally:
        await database.finish_job(TRANSLATION_JOB_NAME, succeeded=succeeded)


@celery_app.task(name="back.tasks.ensure_translation_due")
def ensure_translation_due() -> dict[str, int | bool]:
    try:
        return asyncio.run(_ensure_translation_due_async())
    finally:
        asyncio.run(database.engine.dispose())


async def _translate_cars_batch_async(listing_ids: list[str]) -> dict[str, int | bool]:
    await initialize_runtime(database)
    logger.info("Received compatibility translation task listing_count=%s", len(listing_ids))

    if not listing_ids:
        return {"started": False, "translated": 0, "missing": 0}

    sources = await database.get_cars_by_listing_ids(listing_ids)
    translated = await _translate_sources(sources)
    result = {
        "started": True,
        "translated": translated,
        "missing": max(0, len(listing_ids) - translated),
    }
    logger.info("Completed compatibility translation task result=%s", result)
    return result


@celery_app.task(name="back.tasks.translate_cars_batch")
def translate_cars_batch(listing_ids: list[str] | None = None) -> dict[str, int | bool]:
    listing_ids = listing_ids or []
    try:
        return asyncio.run(_translate_cars_batch_async(listing_ids))
    finally:
        asyncio.run(database.engine.dispose())
