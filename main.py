import asyncio

import structlog
from aiogram import Bot

from app.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.db.models import Base
from app.logging import configure_logging
from app.scheduler.jobs import setup_scheduler
from app.transport.bot import build_bot, build_dispatcher
from app.transport.commands import setup_bot_commands


async def main() -> None:
    configure_logging()
    log = structlog.get_logger()

    settings = get_settings()
    log.info("settings_loaded", tz=settings.tz)

    engine = create_engine(settings.database_url)

    # Автоматическое создание схемы (MVP). В проде использовать Alembic.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    log.info("db_engine_created")

    bot: Bot = build_bot(settings)
    await setup_bot_commands(bot)
    dp = build_dispatcher(session_factory)

    scheduler = setup_scheduler(settings, bot, session_factory)
    scheduler.start()
    log.info("scheduler_started")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()
        scheduler.shutdown(wait=False)
        log.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
