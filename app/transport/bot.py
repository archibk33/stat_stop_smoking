from contextlib import AsyncExitStack
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties

from app.config import Settings
from app.transport.handlers import start as start_handlers
from app.transport.handlers import registration, stats, notify, group, reset
from app.transport.di import DbSessionMiddleware
from app.db.session import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


def build_bot(settings: Settings) -> Bot:
    return Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=None))


def build_dispatcher(session_factory: async_sessionmaker[AsyncSession] | None = None) -> Dispatcher:
    dp = Dispatcher()

    if session_factory is not None:
        dp.update.middleware(DbSessionMiddleware(session_factory))

    # Регистрируем специализированные обработчики ПЕРЕД общими
    logger.info("Registering specialized routers first:")
    dp.include_router(registration.router)
    logger.info("✓ registration.router registered")
    dp.include_router(stats.router)
    logger.info("✓ stats.router registered")
    dp.include_router(notify.router)
    logger.info("✓ notify.router registered")
    dp.include_router(group.router)
    logger.info("✓ group.router registered")
    dp.include_router(reset.router)
    logger.info("✓ reset.router registered")
    
    # Регистрируем общие обработчики ПОСЛЕ специализированных
    logger.info("Registering general routers last:")
    dp.include_router(start_handlers.router)
    logger.info("✓ start_handlers.router registered")
    
    logger.info("All routers registered successfully")
    return dp
