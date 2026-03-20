from __future__ import annotations

from back.auth import hash_password
from back.database import Database


async def initialize_runtime(database: Database) -> None:
    await database.init()
    await database.seed_user("admin", hash_password("admin123"))
