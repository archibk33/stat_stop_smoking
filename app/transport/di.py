from __future__ import annotations

from typing import Any, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__()
        self.session_factory = session_factory

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Any], event: TelegramObject, data: dict[str, Any]) -> Any:  # type: ignore[override]
        data["session_factory"] = self.session_factory
        return await handler(event, data)
