from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SyncResponse(BaseModel):
    queued: bool
    task_id: str


class SyncMetaResponse(BaseModel):
    count: int
    last_synced_at: str | None
    failed_result_pages: int = 0
    failed_detail_pages: int = 0


class FilterOption(BaseModel):
    value: str
    label: str


class AvailableFilters(BaseModel):
    makes: list[FilterOption] = Field(default_factory=list)
    body_types: list[FilterOption] = Field(default_factory=list)
    fuel_types: list[FilterOption] = Field(default_factory=list)
    transmissions: list[FilterOption] = Field(default_factory=list)
    drive_types: list[FilterOption] = Field(default_factory=list)
    locations: list[FilterOption] = Field(default_factory=list)
    colors: list[FilterOption] = Field(default_factory=list)


class CarListItem(BaseModel):
    listing_id: str
    url: str | None = None
    title: str | None = None
    make: str | None = None
    model: str | None = None
    location: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    base_price_yen: int | None = None
    total_price_yen: int | None = None
    engine_volume_cc: int | None = None
    doors: int | None = None
    seats: int | None = None
    photos: list[str] = Field(default_factory=list)
    main_photo: str | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    drive_type: str | None = None
    color: str | None = None
    shop_name: str | None = None


class CarListResponse(BaseModel):
    items: list[CarListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    available_filters: AvailableFilters


class CarDetailResponse(BaseModel):
    item: dict[str, Any]


SortBy = Literal["price", "year", "mileage", "synced_at"]
SortOrder = Literal["asc", "desc"]
