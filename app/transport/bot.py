from contextlib import AsyncExitStack

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties

from app.config import Settings
from app.transport.handlers import start as start_handlers
from app.transport.handlers import registration, stats, notify, leave, group
from app.transport.di import DbSessionMiddleware
from app.db.session import AsyncSession, async_sessionmaker


def build_bot(settings: Settings) -> Bot:
    return Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=None))


def build_dispatcher(session_factory: async_sessionmaker[AsyncSession] | None = None) -> Dispatcher:
    dp = Dispatcher()

    if session_factory is not None:
        dp.update.middleware(DbSessionMiddleware(session_factory))

    dp.include_router(start_handlers.router)
    dp.include_router(registration.router)
    dp.include_router(stats.router)
    dp.include_router(notify.router)
    dp.include_router(leave.router)
    dp.include_router(group.router)
    return dp
