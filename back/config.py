from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_title: str = "Million Miles API"
    cors_origin: str = "http://localhost:3000"
    jwt_secret: str = "million-miles-dev-secret"
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = 720
    auth_cookie_name: str = "million_miles_auth"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "lax"
    sync_interval_seconds: int = 3600 * 2
    translation_interval_seconds: int = 60
    translation_batch_size: int = 25
    sync_max_pages: int | None = None
    sync_max_listings: int | None = None
    startup_sync_enabled: bool = True
    celery_broker_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str | None = None
    database_path: Path = Field(default=Path("back") / "data" / "million_miles.db")

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.celery_broker_url


settings = Settings()
