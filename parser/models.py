from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CarListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: str | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    title: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    base_price_yen: int | None = None
    total_price_yen: int | None = None
    currency: str = "JPY"
    url: str | None = None
    location: str | None = None
    color: str | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    drive_type: str | None = None
    engine_volume_cc: int | None = None
    doors: int | None = None
    seats: int | None = None
    inspection: str | None = None
    repair_history: str | None = None
    maintenance: str | None = None
    guarantee: str | None = None
    shop_name: str | None = None
    shop_url: str | None = None
    photos: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def to_localized_dict(self, lang: str = "ja") -> dict[str, Any]:
        from parser.carsensor import ContentTranslator

        translator = ContentTranslator(lang=lang)
        return translator.translate_payload(self.to_dict())


class ListingPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    listing_id: str | None = None
    make: str | None = None
    title: str | None = None
    base_price_yen: int | None = None
    total_price_yen: int | None = None
    year: int | None = None
    mileage_km: int | None = None
    image_url: str | None = None
    shop_name: str | None = None
    shop_url: str | None = None


class PreviewPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int
    url: str
    previews: list[ListingPreview] = Field(default_factory=list)
    error: str | None = None
