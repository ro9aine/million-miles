from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Index, Integer, String, Text, func, inspect, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


LANG_COLUMNS = {
    "ja": ("payload_ja", "title_ja", "make_ja", "model_ja", "location_ja"),
    "en": ("payload_en", "title_en", "make_en", "model_en", "location_en"),
    "ru": ("payload_ru", "title_ru", "make_ru", "model_ru", "location_ru"),
}


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class CarRecord(Base):
    __tablename__ = "cars"
    __table_args__ = (
        Index("ix_cars_source_url", "source_url"),
        Index("ix_cars_color_key", "color_key"),
        Index("ix_cars_base_price_yen", "base_price_yen"),
        Index("ix_cars_make_key", "make_key"),
        Index("ix_cars_body_type_key", "body_type_key"),
        Index("ix_cars_fuel_type_key", "fuel_type_key"),
        Index("ix_cars_transmission_key", "transmission_key"),
        Index("ix_cars_drive_type_key", "drive_type_key"),
        Index("ix_cars_location_key", "location_key"),
        Index("ix_cars_synced_at", "synced_at"),
        Index("ix_cars_synced_at_listing_id", "synced_at", "listing_id"),
        Index("ix_cars_price_listing_id", "base_price_yen", "listing_id"),
        Index("ix_cars_year_listing_id", "year", "listing_id"),
        Index("ix_cars_mileage_listing_id", "mileage_km", "listing_id"),
    )

    listing_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    payload_ja: Mapped[str] = mapped_column(Text, nullable=False)
    payload_en: Mapped[str] = mapped_column(Text, nullable=False)
    payload_ru: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    photos_json: Mapped[str] = mapped_column(Text, nullable=False)
    title_ja: Mapped[str | None] = mapped_column(String)
    title_en: Mapped[str | None] = mapped_column(String)
    title_ru: Mapped[str | None] = mapped_column(String)
    make_ja: Mapped[str | None] = mapped_column(String)
    make_en: Mapped[str | None] = mapped_column(String)
    make_ru: Mapped[str | None] = mapped_column(String)
    model_ja: Mapped[str | None] = mapped_column(String)
    model_en: Mapped[str | None] = mapped_column(String)
    model_ru: Mapped[str | None] = mapped_column(String)
    location_ja: Mapped[str | None] = mapped_column(String)
    location_en: Mapped[str | None] = mapped_column(String)
    location_ru: Mapped[str | None] = mapped_column(String)
    body_type_ja: Mapped[str | None] = mapped_column(String)
    body_type_en: Mapped[str | None] = mapped_column(String)
    body_type_ru: Mapped[str | None] = mapped_column(String)
    fuel_type_ja: Mapped[str | None] = mapped_column(String)
    fuel_type_en: Mapped[str | None] = mapped_column(String)
    fuel_type_ru: Mapped[str | None] = mapped_column(String)
    transmission_ja: Mapped[str | None] = mapped_column(String)
    transmission_en: Mapped[str | None] = mapped_column(String)
    transmission_ru: Mapped[str | None] = mapped_column(String)
    drive_type_ja: Mapped[str | None] = mapped_column(String)
    drive_type_en: Mapped[str | None] = mapped_column(String)
    drive_type_ru: Mapped[str | None] = mapped_column(String)
    color_ja: Mapped[str | None] = mapped_column(String)
    color_en: Mapped[str | None] = mapped_column(String)
    color_ru: Mapped[str | None] = mapped_column(String)
    shop_name_ja: Mapped[str | None] = mapped_column(String)
    shop_name_en: Mapped[str | None] = mapped_column(String)
    shop_name_ru: Mapped[str | None] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer)
    mileage_km: Mapped[int | None] = mapped_column(Integer)
    base_price_yen: Mapped[int | None] = mapped_column(Integer)
    total_price_yen: Mapped[int | None] = mapped_column(Integer)
    engine_volume_cc: Mapped[int | None] = mapped_column(Integer)
    doors: Mapped[int | None] = mapped_column(Integer)
    seats: Mapped[int | None] = mapped_column(Integer)
    make_key: Mapped[str | None] = mapped_column(String)
    body_type_key: Mapped[str | None] = mapped_column(String)
    fuel_type_key: Mapped[str | None] = mapped_column(String)
    transmission_key: Mapped[str | None] = mapped_column(String)
    drive_type_key: Mapped[str | None] = mapped_column(String)
    location_key: Mapped[str | None] = mapped_column(String)
    color_key: Mapped[str | None] = mapped_column(String)
    synced_at: Mapped[str] = mapped_column(String, nullable=False)


class SyncStateRecord(Base):
    __tablename__ = "sync_state"

    job_name: Mapped[str] = mapped_column(String, primary_key=True)
    is_running: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_started_at: Mapped[str | None] = mapped_column(String)
    last_finished_at: Mapped[str | None] = mapped_column(String)
    last_succeeded_at: Mapped[str | None] = mapped_column(String)


class FailedResultPageRecord(Base):
    __tablename__ = "failed_result_pages"
    __table_args__ = (Index("ix_failed_result_pages_last_failed_at", "last_failed_at"),)

    page_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_url: Mapped[str] = mapped_column(String, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_failed_at: Mapped[str] = mapped_column(String, nullable=False)
    last_failed_at: Mapped[str] = mapped_column(String, nullable=False)


class FailedDetailPageRecord(Base):
    __tablename__ = "failed_detail_pages"
    __table_args__ = (
        Index("ix_failed_detail_pages_last_failed_at", "last_failed_at"),
        Index("ix_failed_detail_pages_listing_id", "listing_id"),
    )

    listing_url: Mapped[str] = mapped_column(String, primary_key=True)
    listing_id: Mapped[str | None] = mapped_column(String)
    last_error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_failed_at: Mapped[str] = mapped_column(String, nullable=False)
    last_failed_at: Mapped[str] = mapped_column(String, nullable=False)


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    async def init(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await self._migrate_schema(connection)

    async def seed_user(self, username: str, password_hash: str) -> None:
        payload = {
            "username": username,
            "password_hash": password_hash,
            "created_at": _utc_now(),
        }
        statement = insert(UserRecord).values(**payload)
        statement = statement.on_conflict_do_nothing(index_elements=["username"])
        async with self.session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def get_user(self, username: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            record = await session.get(UserRecord, username)
            if record is None:
                return None
            return {
                "username": record.username,
                "password_hash": record.password_hash,
            }

    async def upsert_car(self, record: dict[str, Any]) -> None:
        statement = insert(CarRecord).values(**record)
        update_map = {
            key: getattr(statement.excluded, key)
            for key in record
            if key != "listing_id"
        }
        statement = statement.on_conflict_do_update(
            index_elements=["listing_id"],
            set_=update_map,
        )
        async with self.session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def count_cars(self) -> int:
        async with self.session_factory() as session:
            value = await session.scalar(select(func.count()).select_from(CarRecord))
        return int(value or 0)

    async def has_car(self, listing_id: str) -> bool:
        async with self.session_factory() as session:
            value = await session.scalar(
                select(func.count())
                .select_from(CarRecord)
                .where(CarRecord.listing_id == listing_id)
            )
        return bool(value)

    async def get_cars_missing_localization(self, limit: int) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(CarRecord)
                    .where(
                        or_(
                            CarRecord.payload_en == CarRecord.payload_ja,
                            CarRecord.payload_ru == CarRecord.payload_ja,
                        )
                    )
                    .order_by(CarRecord.synced_at.asc(), CarRecord.listing_id.asc())
                    .limit(limit)
                )
            ).all()

        result: list[dict[str, Any]] = []
        for row in rows:
            missing_langs: list[str] = []
            if row.payload_en == row.payload_ja:
                missing_langs.append("en")
            if row.payload_ru == row.payload_ja:
                missing_langs.append("ru")
            if not missing_langs:
                continue
            result.append(
                {
                    "listing_id": row.listing_id,
                    "payload_ja": json.loads(row.payload_ja),
                    "missing_langs": missing_langs,
                }
            )
        return result

    async def get_cars_by_listing_ids(self, listing_ids: list[str]) -> list[dict[str, Any]]:
        if not listing_ids:
            return []

        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(CarRecord)
                    .where(CarRecord.listing_id.in_(listing_ids))
                    .order_by(CarRecord.listing_id.asc())
                )
            ).all()

        result: list[dict[str, Any]] = []
        for row in rows:
            missing_langs: list[str] = []
            if row.payload_en == row.payload_ja:
                missing_langs.append("en")
            if row.payload_ru == row.payload_ja:
                missing_langs.append("ru")

            result.append(
                {
                    "listing_id": row.listing_id,
                    "payload_ja": json.loads(row.payload_ja),
                    "missing_langs": missing_langs,
                }
            )
        return result

    async def update_car_localizations(self, listing_id: str, localized_values: dict[str, Any]) -> None:
        async with self.session_factory() as session:
            record = await session.get(CarRecord, listing_id)
            if record is None:
                return

            for key, value in localized_values.items():
                setattr(record, key, value)
            await session.commit()

    async def record_failed_result_page(self, *, page_number: int, page_url: str, error: str) -> None:
        timestamp = _utc_now()
        async with self.session_factory() as session:
            record = await session.get(FailedResultPageRecord, page_number)
            if record is None:
                record = FailedResultPageRecord(
                    page_number=page_number,
                    page_url=page_url,
                    last_error=error,
                    attempts=1,
                    first_failed_at=timestamp,
                    last_failed_at=timestamp,
                )
                session.add(record)
            else:
                record.page_url = page_url
                record.last_error = error
                record.attempts += 1
                record.last_failed_at = timestamp
            await session.commit()

    async def clear_failed_result_page(self, page_number: int) -> None:
        async with self.session_factory() as session:
            record = await session.get(FailedResultPageRecord, page_number)
            if record is not None:
                await session.delete(record)
                await session.commit()

    async def list_failed_result_pages(self, limit: int | None = None) -> list[dict[str, Any]]:
        query = select(FailedResultPageRecord).order_by(
            FailedResultPageRecord.last_failed_at.asc(),
            FailedResultPageRecord.page_number.asc(),
        )
        if limit is not None:
            query = query.limit(limit)

        async with self.session_factory() as session:
            rows = (await session.scalars(query)).all()

        return [
            {
                "page_number": row.page_number,
                "page_url": row.page_url,
                "last_error": row.last_error,
                "attempts": row.attempts,
            }
            for row in rows
        ]

    async def count_failed_result_pages(self) -> int:
        async with self.session_factory() as session:
            value = await session.scalar(select(func.count()).select_from(FailedResultPageRecord))
        return int(value or 0)

    async def record_failed_detail_page(self, *, listing_id: str | None, listing_url: str, error: str) -> None:
        timestamp = _utc_now()
        async with self.session_factory() as session:
            record = await session.get(FailedDetailPageRecord, listing_url)
            if record is None:
                record = FailedDetailPageRecord(
                    listing_url=listing_url,
                    listing_id=listing_id,
                    last_error=error,
                    attempts=1,
                    first_failed_at=timestamp,
                    last_failed_at=timestamp,
                )
                session.add(record)
            else:
                record.listing_id = listing_id or record.listing_id
                record.last_error = error
                record.attempts += 1
                record.last_failed_at = timestamp
            await session.commit()

    async def clear_failed_detail_page(self, listing_url: str) -> None:
        async with self.session_factory() as session:
            record = await session.get(FailedDetailPageRecord, listing_url)
            if record is not None:
                await session.delete(record)
                await session.commit()

    async def list_failed_detail_pages(self, limit: int | None = None) -> list[dict[str, Any]]:
        query = select(FailedDetailPageRecord).order_by(
            FailedDetailPageRecord.last_failed_at.asc(),
            FailedDetailPageRecord.listing_url.asc(),
        )
        if limit is not None:
            query = query.limit(limit)

        async with self.session_factory() as session:
            rows = (await session.scalars(query)).all()

        return [
            {
                "listing_id": row.listing_id,
                "listing_url": row.listing_url,
                "last_error": row.last_error,
                "attempts": row.attempts,
            }
            for row in rows
        ]

    async def count_failed_detail_pages(self) -> int:
        async with self.session_factory() as session:
            value = await session.scalar(select(func.count()).select_from(FailedDetailPageRecord))
        return int(value or 0)

    async def list_cars(
        self,
        *,
        lang: str,
        page: int,
        page_size: int,
        filters: dict[str, Any],
        sort_by: str,
        sort_order: str,
    ) -> dict[str, Any]:
        payload_attr, title_attr, make_attr, model_attr, location_attr = LANG_COLUMNS[lang]
        title_column = getattr(CarRecord, title_attr)
        make_column = getattr(CarRecord, make_attr)
        model_column = getattr(CarRecord, model_attr)
        location_column = getattr(CarRecord, location_attr)
        payload_column = getattr(CarRecord, payload_attr)

        query = select(CarRecord)
        query = self._apply_filters(
            query,
            filters=filters,
            search_columns=[title_column, make_column, model_column, location_column],
        )

        async with self.session_factory() as session:
            total = await session.scalar(select(func.count()).select_from(query.subquery(CarRecord.listing_id))) or 0

            rows = (
                await session.scalars(
                    query.order_by(*self._resolve_order_by(sort_by, sort_order))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()

            filters_payload = await self._load_filter_options(session, lang)

        items = [
            self._row_to_list_item(
                row,
                payload_column=payload_column.key,
                title_column=title_column.key,
                make_column=make_column.key,
                model_column=model_column.key,
                location_column=location_column.key,
            )
            for row in rows
        ]
        total_pages = max(1, math.ceil(total / page_size)) if total else 1

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "total_pages": total_pages,
            "available_filters": filters_payload,
        }

    async def get_car(self, listing_id: str, lang: str) -> dict[str, Any] | None:
        payload_column = LANG_COLUMNS[lang][0]
        async with self.session_factory() as session:
            record = await session.get(CarRecord, listing_id)
            if record is None:
                return None
            return json.loads(getattr(record, payload_column))

    async def get_sync_meta(self) -> dict[str, Any]:
        async with self.session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(CarRecord)) or 0
            last_synced_at = await session.scalar(select(func.max(CarRecord.synced_at)))
            failed_result_pages = await session.scalar(
                select(func.count()).select_from(FailedResultPageRecord)
            ) or 0
            failed_detail_pages = await session.scalar(
                select(func.count()).select_from(FailedDetailPageRecord)
            ) or 0
        return {
            "count": int(count),
            "last_synced_at": last_synced_at,
            "failed_result_pages": int(failed_result_pages),
            "failed_detail_pages": int(failed_detail_pages),
        }

    async def start_job_if_due(
        self,
        job_name: str,
        *,
        interval_seconds: int,
        force: bool = False,
    ) -> bool:
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            async with session.begin():
                insert_statement = insert(SyncStateRecord).values(
                    job_name=job_name,
                    is_running=0,
                )
                insert_statement = insert_statement.on_conflict_do_nothing(index_elements=["job_name"])
                await session.execute(insert_statement)

                state = await session.scalar(
                    select(SyncStateRecord)
                    .where(SyncStateRecord.job_name == job_name)
                    .with_for_update()
                )
                if state is None:
                    return False

                if state.is_running:
                    if force:
                        state.is_running = 0
                    else:
                        return False

                if not force and state.last_succeeded_at:
                    last_succeeded_at = datetime.fromisoformat(state.last_succeeded_at)
                    if (now - last_succeeded_at).total_seconds() < interval_seconds:
                        return False

                state.is_running = 1
                state.last_started_at = now.isoformat()

            await session.commit()
            return True

    async def finish_job(self, job_name: str, *, succeeded: bool) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                insert_statement = insert(SyncStateRecord).values(job_name=job_name, is_running=0)
                insert_statement = insert_statement.on_conflict_do_nothing(index_elements=["job_name"])
                await session.execute(insert_statement)

                state = await session.scalar(
                    select(SyncStateRecord)
                    .where(SyncStateRecord.job_name == job_name)
                    .with_for_update()
                )
                if state is None:
                    return

                state.is_running = 0
                state.last_finished_at = _utc_now()
                if succeeded:
                    state.last_succeeded_at = state.last_finished_at

            await session.commit()

    async def _migrate_schema(self, connection) -> None:
        def inspect_columns(sync_connection) -> set[str] | None:
            inspector = inspect(sync_connection)
            tables = set(inspector.get_table_names())
            if "sync_state" not in tables:
                return None
            return {column["name"] for column in inspector.get_columns("sync_state")}

        columns = await connection.run_sync(inspect_columns)
        if columns is None or "last_succeeded_at" in columns:
            return

        await connection.execute(text("ALTER TABLE sync_state ADD COLUMN last_succeeded_at VARCHAR"))

    def _apply_filters(
        self,
        query,
        *,
        filters: dict[str, Any],
        search_columns: list[Any],
    ):
        search_value = filters.get("query")
        if search_value:
            pattern = f"%{search_value.lower()}%"
            query = query.where(
                or_(*[func.lower(column).like(pattern) for column in search_columns])
            )

        exact_filters = {
            "make": CarRecord.make_key,
            "body_type": CarRecord.body_type_key,
            "fuel_type": CarRecord.fuel_type_key,
            "transmission": CarRecord.transmission_key,
            "drive_type": CarRecord.drive_type_key,
            "location": CarRecord.location_key,
            "color": CarRecord.color_key,
        }
        for key, column in exact_filters.items():
            value = filters.get(key)
            if value:
                query = query.where(column == value)

        range_filters = [
            ("min_year", CarRecord.year, ">="),
            ("max_year", CarRecord.year, "<="),
            ("min_price", CarRecord.base_price_yen, ">="),
            ("max_price", CarRecord.base_price_yen, "<="),
            ("min_mileage", CarRecord.mileage_km, ">="),
            ("max_mileage", CarRecord.mileage_km, "<="),
        ]
        for key, column, operator in range_filters:
            value = filters.get(key)
            if value is None:
                continue
            if operator == ">=":
                query = query.where(column >= value)
            else:
                query = query.where(column <= value)
        return query

    async def _load_filter_options(
        self,
        session: AsyncSession,
        lang: str,
    ) -> dict[str, list[dict[str, str]]]:
        suffix = lang
        filter_map = {
            "makes": (CarRecord.make_key, getattr(CarRecord, f"make_{suffix}")),
            "body_types": (CarRecord.body_type_key, getattr(CarRecord, f"body_type_{suffix}")),
            "fuel_types": (CarRecord.fuel_type_key, getattr(CarRecord, f"fuel_type_{suffix}")),
            "transmissions": (CarRecord.transmission_key, getattr(CarRecord, f"transmission_{suffix}")),
            "drive_types": (CarRecord.drive_type_key, getattr(CarRecord, f"drive_type_{suffix}")),
            "locations": (CarRecord.location_key, getattr(CarRecord, f"location_{suffix}")),
            "colors": (CarRecord.color_key, getattr(CarRecord, f"color_{suffix}")),
        }
        result: dict[str, list[dict[str, str]]] = {}

        for key, (value_column, label_column) in filter_map.items():
            rows = (
                await session.execute(
                    select(value_column, label_column)
                    .where(value_column.is_not(None), label_column.is_not(None))
                    .distinct()
                    .order_by(label_column.asc())
                )
            ).all()
            result[key] = [
                {"value": value, "label": label}
                for value, label in rows
                if value and label
            ]

        return result

    def _row_to_list_item(
        self,
        row: CarRecord,
        *,
        payload_column: str,
        title_column: str,
        make_column: str,
        model_column: str,
        location_column: str,
    ) -> dict[str, Any]:
        photos = json.loads(row.photos_json)
        payload = json.loads(getattr(row, payload_column))
        return {
            "listing_id": row.listing_id,
            "url": row.source_url,
            "title": getattr(row, title_column),
            "make": getattr(row, make_column),
            "model": getattr(row, model_column),
            "location": getattr(row, location_column),
            "year": row.year,
            "mileage_km": row.mileage_km,
            "base_price_yen": row.base_price_yen,
            "total_price_yen": row.total_price_yen,
            "engine_volume_cc": row.engine_volume_cc,
            "doors": row.doors,
            "seats": row.seats,
            "photos": photos,
            "main_photo": photos[0] if photos else None,
            "body_type": payload.get("body_type"),
            "fuel_type": payload.get("fuel_type"),
            "transmission": payload.get("transmission"),
            "drive_type": payload.get("drive_type"),
            "color": payload.get("color"),
            "shop_name": payload.get("shop_name"),
        }

    def _resolve_order_by(self, sort_by: str, sort_order: str) -> tuple[Any, Any]:
        allowed = {
            "price": CarRecord.base_price_yen,
            "year": CarRecord.year,
            "mileage": CarRecord.mileage_km,
            "synced_at": CarRecord.synced_at,
        }
        column = allowed.get(sort_by, CarRecord.synced_at)
        ordered = column.desc() if sort_order == "desc" else column.asc()
        return ordered, CarRecord.listing_id.asc()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
