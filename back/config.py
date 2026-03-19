from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    api_title: str = "Million Miles API"
    cors_origin: str = os.getenv("CORS_ORIGIN", "http://localhost:3000")
    jwt_secret: str = os.getenv("JWT_SECRET", "million-miles-dev-secret")
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = int(os.getenv("TOKEN_EXPIRE_MINUTES", "720"))
    sync_interval_seconds: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "3600"))
    sync_max_pages: int = int(os.getenv("SYNC_MAX_PAGES", "2"))
    sync_max_listings: int = int(os.getenv("SYNC_MAX_LISTINGS", "40"))
    startup_sync_enabled: bool = os.getenv("STARTUP_SYNC_ENABLED", "1") == "1"
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
    celery_result_backend: str = os.getenv(
        "CELERY_RESULT_BACKEND",
        os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"),
    )
    database_path: Path = Path(
        os.getenv("DATABASE_PATH", Path("back") / "data" / "million_miles.db")
    )


settings = Settings()
