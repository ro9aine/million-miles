from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Integer, String, Text, create_engine, func, or_, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


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
    base_price_yen: Mapped[int | None] = mapped_column(Integer, index=True)
    total_price_yen: Mapped[int | None] = mapped_column(Integer)
    engine_volume_cc: Mapped[int | None] = mapped_column(Integer)
    doors: Mapped[int | None] = mapped_column(Integer)
    seats: Mapped[int | None] = mapped_column(Integer)
    make_key: Mapped[str | None] = mapped_column(String, index=True)
    body_type_key: Mapped[str | None] = mapped_column(String, index=True)
    fuel_type_key: Mapped[str | None] = mapped_column(String, index=True)
    transmission_key: Mapped[str | None] = mapped_column(String, index=True)
    drive_type_key: Mapped[str | None] = mapped_column(String, index=True)
    location_key: Mapped[str | None] = mapped_column(String, index=True)
    color_key: Mapped[str | None] = mapped_column(String)
    synced_at: Mapped[str] = mapped_column(String, nullable=False, index=True)


class SyncStateRecord(Base):
    __tablename__ = "sync_state"

    job_name: Mapped[str] = mapped_column(String, primary_key=True)
    is_running: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_started_at: Mapped[str | None] = mapped_column(String)
    last_finished_at: Mapped[str | None] = mapped_column(String)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.path}",
            connect_args={"check_same_thread": False},
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self._write_lock = threading.Lock()

    def init(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.session_factory()

    def seed_user(self, username: str, password_hash: str) -> None:
        with self._write_lock, self.session() as session:
            payload = {
                "username": username,
                "password_hash": password_hash,
                "created_at": _utc_now(),
            }
            statement = insert(UserRecord).values(**payload)
            statement = statement.on_conflict_do_nothing(index_elements=["username"])
            session.execute(statement)
            session.commit()

    def get_user(self, username: str) -> dict[str, Any] | None:
        with self.session() as session:
            record = session.get(UserRecord, username)
            if record is None:
                return None
            return {
                "username": record.username,
                "password_hash": record.password_hash,
            }

    def upsert_car(self, record: dict[str, Any]) -> None:
        with self._write_lock, self.session() as session:
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
            session.execute(statement)
            session.commit()

    def count_cars(self) -> int:
        with self.session() as session:
            value = session.scalar(select(func.count()).select_from(CarRecord))
        return int(value or 0)

    def list_cars(
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

        with self.session() as session:
            total = session.scalar(
                select(func.count()).select_from(query.subquery())
            ) or 0

            rows = session.scalars(
                query.order_by(*self._resolve_order_by(sort_by, sort_order))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()

            filters_payload = self._load_filter_options(session, lang)

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

    def get_car(self, listing_id: str, lang: str) -> dict[str, Any] | None:
        payload_column = LANG_COLUMNS[lang][0]
        with self.session() as session:
            record = session.get(CarRecord, listing_id)
            if record is None:
                return None
            return json.loads(getattr(record, payload_column))

    def get_sync_meta(self) -> dict[str, Any]:
        with self.session() as session:
            count = session.scalar(select(func.count()).select_from(CarRecord)) or 0
            last_synced_at = session.scalar(select(func.max(CarRecord.synced_at)))
        return {"count": int(count), "last_synced_at": last_synced_at}

    def start_job_if_due(
        self,
        job_name: str,
        *,
        interval_seconds: int,
        force: bool = False,
    ) -> bool:
        now = datetime.now(timezone.utc)

        with self._write_lock, self.session() as session:
            state = session.get(SyncStateRecord, job_name)
            if state is None:
                state = SyncStateRecord(job_name=job_name, is_running=0)
                session.add(state)
                session.flush()

            if state.is_running:
                session.rollback()
                return False

            if not force and state.last_finished_at:
                last_finished_at = datetime.fromisoformat(state.last_finished_at)
                if (now - last_finished_at).total_seconds() < interval_seconds:
                    session.rollback()
                    return False

            state.is_running = 1
            state.last_started_at = now.isoformat()
            session.commit()
            return True

    def finish_job(self, job_name: str) -> None:
        with self._write_lock, self.session() as session:
            state = session.get(SyncStateRecord, job_name)
            if state is None:
                state = SyncStateRecord(job_name=job_name)
                session.add(state)
            state.is_running = 0
            state.last_finished_at = _utc_now()
            session.commit()

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

    def _load_filter_options(self, session: Session, lang: str) -> dict[str, list[dict[str, str]]]:
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
            rows = session.execute(
                select(value_column, label_column)
                .where(value_column.is_not(None), label_column.is_not(None))
                .distinct()
                .order_by(label_column.asc())
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
