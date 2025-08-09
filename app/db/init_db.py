from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine


async def ensure_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS top_posts (
                chat_id BIGINT PRIMARY KEY,
                message_id INTEGER NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
