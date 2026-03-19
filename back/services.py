from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from back.database import Database
from back.localization import localize_listing_payload, slugify_text
from parser import CarListing, CarSensorParser


class SyncService:
    def __init__(self, database: Database, parser: CarSensorParser) -> None:
        self.database = database
        self.parser = parser

    def sync(self, *, max_pages: int, max_listings: int | None) -> dict[str, Any]:
        synced_at = datetime.now(timezone.utc).isoformat()
        synced = 0

        for listing in self.parser.iter_listings(
            max_pages=max_pages,
            max_listings=max_listings,
        ):
            if not listing.listing_id or not listing.url:
                continue
            self.database.upsert_car(self._build_record(listing, synced_at))
            synced += 1

        return {
            "synced": synced,
            "last_synced_at": synced_at,
        }

    def _build_record(self, listing: CarListing, synced_at: str) -> dict[str, Any]:
        payload_ja = self._base_payload(listing)
        payload_en = localize_listing_payload(payload_ja, "en")
        payload_ru = localize_listing_payload(payload_ja, "ru")

        return {
            "listing_id": listing.listing_id,
            "source_url": listing.url,
            "payload_ja": json.dumps(payload_ja, ensure_ascii=False),
            "payload_en": json.dumps(payload_en, ensure_ascii=False),
            "payload_ru": json.dumps(payload_ru, ensure_ascii=False),
            "raw_json": json.dumps(listing.raw, ensure_ascii=False),
            "photos_json": json.dumps(listing.photos, ensure_ascii=False),
            "title_ja": payload_ja.get("title"),
            "title_en": payload_en.get("title"),
            "title_ru": payload_ru.get("title"),
            "make_ja": payload_ja.get("make"),
            "make_en": payload_en.get("make"),
            "make_ru": payload_ru.get("make"),
            "model_ja": payload_ja.get("model"),
            "model_en": payload_en.get("model"),
            "model_ru": payload_ru.get("model"),
            "location_ja": payload_ja.get("location"),
            "location_en": payload_en.get("location"),
            "location_ru": payload_ru.get("location"),
            "body_type_ja": payload_ja.get("body_type"),
            "body_type_en": payload_en.get("body_type"),
            "body_type_ru": payload_ru.get("body_type"),
            "fuel_type_ja": payload_ja.get("fuel_type"),
            "fuel_type_en": payload_en.get("fuel_type"),
            "fuel_type_ru": payload_ru.get("fuel_type"),
            "transmission_ja": payload_ja.get("transmission"),
            "transmission_en": payload_en.get("transmission"),
            "transmission_ru": payload_ru.get("transmission"),
            "drive_type_ja": payload_ja.get("drive_type"),
            "drive_type_en": payload_en.get("drive_type"),
            "drive_type_ru": payload_ru.get("drive_type"),
            "color_ja": payload_ja.get("color"),
            "color_en": payload_en.get("color"),
            "color_ru": payload_ru.get("color"),
            "shop_name_ja": payload_ja.get("shop_name"),
            "shop_name_en": payload_en.get("shop_name"),
            "shop_name_ru": payload_ru.get("shop_name"),
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
        payload = asdict(listing)
        payload.pop("raw", None)
        return payload
