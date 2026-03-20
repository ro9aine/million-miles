from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from back.database import Database
from back.localization import slugify_text
from parser import CarListing, CarSensorParser, ListingPreview


logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, database: Database, parser: CarSensorParser) -> None:
        self.database = database
        self.parser = parser

    async def sync(self, *, max_pages: int | None, max_listings: int | None) -> dict[str, Any]:
        synced_at = datetime.now(timezone.utc).isoformat()
        result: dict[str, Any] = {
            "synced": 0,
            "failed": 0,
            "existing_seen": 0,
            "processed_preview_batches": 0,
            "retried_failed_detail_pages": 0,
            "retried_failed_result_pages": 0,
            "last_synced_at": synced_at,
        }

        logger.info(
            "Sync pass started synced_at=%s max_pages=%s max_listings=%s",
            synced_at,
            max_pages,
            max_listings,
        )

        if await self._process_failed_detail_pages(result=result, synced_at=synced_at, max_listings=max_listings):
            return await self._finalize_result(result)

        if await self._process_failed_result_pages(result=result, synced_at=synced_at, max_listings=max_listings):
            return await self._finalize_result(result)

        async for page_results in self.parser.iter_preview_page_batches(max_pages=max_pages):
            result["processed_preview_batches"] += 1
            for page_result in page_results:
                if page_result.error is not None:
                    await self.database.record_failed_result_page(
                        page_number=page_result.page_number,
                        page_url=page_result.url,
                        error=page_result.error,
                    )
                    result["failed"] += 1
                    continue

                await self.database.clear_failed_result_page(page_result.page_number)
                if await self._process_previews(
                    page_result.previews,
                    result=result,
                    synced_at=synced_at,
                    max_listings=max_listings,
                ):
                    return await self._finalize_result(result)

        result = await self._finalize_result(result)
        logger.info("Sync pass finished result=%s", result)
        return result

    async def _process_failed_detail_pages(
        self,
        *,
        result: dict[str, Any],
        synced_at: str,
        max_listings: int | None,
    ) -> bool:
        failed_pages = await self.database.list_failed_detail_pages()
        if not failed_pages:
            return False

        previews = [
            ListingPreview(url=item["listing_url"], listing_id=item["listing_id"])
            for item in failed_pages
        ]
        result["retried_failed_detail_pages"] = len(previews)
        logger.info("Retrying failed detail pages count=%s", len(previews))
        return await self._process_previews(
            previews,
            result=result,
            synced_at=synced_at,
            max_listings=max_listings,
        )

    async def _process_failed_result_pages(
        self,
        *,
        result: dict[str, Any],
        synced_at: str,
        max_listings: int | None,
    ) -> bool:
        failed_pages = await self.database.list_failed_result_pages()
        if not failed_pages:
            return False

        page_numbers = [item["page_number"] for item in failed_pages]
        result["retried_failed_result_pages"] = len(page_numbers)
        logger.info("Retrying failed result pages page_numbers=%s", page_numbers)
        for page_result in await self.parser.fetch_preview_pages(page_numbers):
            if page_result.error is not None:
                await self.database.record_failed_result_page(
                    page_number=page_result.page_number,
                    page_url=page_result.url,
                    error=page_result.error,
                )
                result["failed"] += 1
                continue

            await self.database.clear_failed_result_page(page_result.page_number)
            if await self._process_previews(
                page_result.previews,
                result=result,
                synced_at=synced_at,
                max_listings=max_listings,
            ):
                return True
        return False

    async def _process_previews(
        self,
        previews: list[ListingPreview],
        *,
        result: dict[str, Any],
        synced_at: str,
        max_listings: int | None,
    ) -> bool:
        batch = await self._limit_previews(previews, result=result, max_listings=max_listings)
        if not batch:
            return self._limit_reached(result=result, max_listings=max_listings)

        logger.info(
            "Prepared preview batch size=%s existing_seen=%s",
            len(batch),
            result["existing_seen"],
        )

        for preview, listing, error in await self.parser.fetch_listings_with_status(batch):
            if error is not None:
                result["failed"] += 1
                await self.database.record_failed_detail_page(
                    listing_id=preview.listing_id,
                    listing_url=preview.url,
                    error=str(error),
                )
                logger.warning(
                    "Failed to fetch listing %s",
                    preview.url,
                    exc_info=(type(error), error, error.__traceback__),
                )
                continue
            if not listing.listing_id or not listing.url:
                result["failed"] += 1
                await self.database.record_failed_detail_page(
                    listing_id=preview.listing_id,
                    listing_url=preview.url,
                    error="Missing listing_id or url after detail parse",
                )
                logger.warning("Skipping listing without listing_id or url source=%s", preview.url)
                continue

            await self.database.clear_failed_detail_page(preview.url)
            await self.database.upsert_car(self._build_record(listing, synced_at))
            result["synced"] += 1
            logger.info(
                "Upserted listing listing_id=%s synced=%s failed=%s existing_seen=%s",
                listing.listing_id,
                result["synced"],
                result["failed"],
                result["existing_seen"],
            )
            if self._limit_reached(result=result, max_listings=max_listings):
                logger.info("Sync pass reached max_listings result=%s", result)
                return True

        return False

    async def _limit_previews(
        self,
        previews: list[ListingPreview],
        *,
        result: dict[str, Any],
        max_listings: int | None,
    ) -> list[ListingPreview]:
        if max_listings is not None:
            remaining = max_listings - result["synced"]
            if remaining <= 0:
                return []
            previews = previews[:remaining]

        for preview in previews:
            listing_id = preview.listing_id or self.parser.extract_listing_id(preview.url)
            if listing_id and await self.database.has_car(listing_id):
                result["existing_seen"] += 1
        return previews

    def _limit_reached(self, *, result: dict[str, Any], max_listings: int | None) -> bool:
        return max_listings is not None and result["synced"] >= max_listings

    async def _finalize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        result["pending_failed_result_pages"] = await self.database.count_failed_result_pages()
        result["pending_failed_detail_pages"] = await self.database.count_failed_detail_pages()
        return result

    def _build_record(self, listing: CarListing, synced_at: str) -> dict[str, Any]:
        payload_ja = self._base_payload(listing)

        return {
            "listing_id": listing.listing_id,
            "source_url": listing.url,
            "payload_ja": json.dumps(payload_ja, ensure_ascii=False),
            "payload_en": json.dumps(payload_ja, ensure_ascii=False),
            "payload_ru": json.dumps(payload_ja, ensure_ascii=False),
            "raw_json": json.dumps(listing.raw, ensure_ascii=False),
            "photos_json": json.dumps(listing.photos, ensure_ascii=False),
            "title_ja": payload_ja.get("title"),
            "title_en": payload_ja.get("title"),
            "title_ru": payload_ja.get("title"),
            "make_ja": payload_ja.get("make"),
            "make_en": payload_ja.get("make"),
            "make_ru": payload_ja.get("make"),
            "model_ja": payload_ja.get("model"),
            "model_en": payload_ja.get("model"),
            "model_ru": payload_ja.get("model"),
            "location_ja": payload_ja.get("location"),
            "location_en": payload_ja.get("location"),
            "location_ru": payload_ja.get("location"),
            "body_type_ja": payload_ja.get("body_type"),
            "body_type_en": payload_ja.get("body_type"),
            "body_type_ru": payload_ja.get("body_type"),
            "fuel_type_ja": payload_ja.get("fuel_type"),
            "fuel_type_en": payload_ja.get("fuel_type"),
            "fuel_type_ru": payload_ja.get("fuel_type"),
            "transmission_ja": payload_ja.get("transmission"),
            "transmission_en": payload_ja.get("transmission"),
            "transmission_ru": payload_ja.get("transmission"),
            "drive_type_ja": payload_ja.get("drive_type"),
            "drive_type_en": payload_ja.get("drive_type"),
            "drive_type_ru": payload_ja.get("drive_type"),
            "color_ja": payload_ja.get("color"),
            "color_en": payload_ja.get("color"),
            "color_ru": payload_ja.get("color"),
            "shop_name_ja": payload_ja.get("shop_name"),
            "shop_name_en": payload_ja.get("shop_name"),
            "shop_name_ru": payload_ja.get("shop_name"),
            "year": listing.year,
            "mileage_km": listing.mileage_km,
            "base_price_yen": listing.base_price_yen,
            "total_price_yen": listing.total_price_yen,
            "engine_volume_cc": listing.engine_volume_cc,
            "doors": listing.doors,
            "seats": listing.seats,
            "make_key": slugify_text(listing.make),
            "body_type_key": slugify_text(listing.body_type),
            "fuel_type_key": slugify_text(listing.fuel_type),
            "transmission_key": slugify_text(listing.transmission),
            "drive_type_key": slugify_text(listing.drive_type),
            "location_key": slugify_text(listing.location),
            "color_key": slugify_text(listing.color),
            "synced_at": synced_at,
        }

    def _base_payload(self, listing: CarListing) -> dict[str, Any]:
        payload = listing.model_dump()
        payload.pop("raw", None)
        return payload
