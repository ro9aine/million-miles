from __future__ import annotations

from back.auth import hash_password
from back.database import Database


def initialize_runtime(database: Database) -> None:
    database.init()
    database.seed_user("admin", hash_password("admin123"))
