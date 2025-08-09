from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings
from app.db.repo import MetricsRepo, UserRepo
from app.db.session import AsyncSession, async_sessionmaker
from app.domain.services import calculate_metrics, generate_admin_title


async def daily_post_top(bot: Bot, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
    async with session_factory() as session:
        repo = MetricsRepo(session)
        top = await repo.get_top(limit=10)

    if not top:
        return

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for idx, (user, metrics) in enumerate(top, start=1):
        prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
        name = user.full_name or user.username or str(user.user_id)
        lines.append(f"{prefix} {name} — {metrics.days} дн.")

    text = "ТОП-10:\n" + "\n".join(lines)

    me = await bot.get_me()
    deep_link = f"https://t.me/{me.username}?start=me"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 Мой статус в ЛС", url=deep_link)]])

    try:
        await bot.send_message(chat_id=settings.group_chat_id, text=text, reply_markup=kb, message_thread_id=settings.topic_id)
    except Exception as e:  # noqa: BLE001
        structlog.get_logger().warning("daily_top_post_failed", error=str(e))


async def daily_update(bot: Bot, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
    log = structlog.get_logger()
    async with session_factory() as session:
        users = UserRepo(session)
        metrics_repo = MetricsRepo(session)
        members = await users.list_all_members()
        for user in members:
            m = calculate_metrics(user.quit_date, user.pack_price)
            await metrics_repo.upsert_metrics(user.user_id, m.days, m.saved_money)
            try:
                if m.days > 0:
                    member = await bot.get_chat_member(settings.group_chat_id, user.user_id)
                    # Пропускаем владельца — ему нельзя ставить кастом‑тайтл ботом
                    if isinstance(member, ChatMemberOwner):
                        continue
                    title = generate_admin_title(m.days)
                    await bot.set_chat_administrator_custom_title(
                        chat_id=settings.group_chat_id,
                        user_id=user.user_id,
                        custom_title=title,
                    )
            except Exception as e:  # noqa: BLE001
                log.warning("custom_title_update_failed", user_id=user.user_id, error=str(e))
        await session.commit()

    # Личные уведомления
    try:
        async with session_factory() as session:
            users = UserRepo(session)
            notify_users = await users.list_with_notifications()
            for u in notify_users:
                m = calculate_metrics(u.quit_date, u.pack_price)
                await bot.send_message(chat_id=u.user_id, text=f"Доброе утро! Ваш стаж: {m.days} дн., экономия: {m.saved_money:.0f}₽")
    except Exception as e:  # noqa: BLE001
        log = structlog.get_logger()
        log.warning("notify_failed", error=str(e))

    log.info("daily_metrics_updated")


def setup_scheduler(settings: Settings, bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.tz))

    scheduler.add_job(
        func=lambda: daily_post_top(bot, session_factory, settings),
        trigger=CronTrigger(hour=settings.daily_post_hour, minute=settings.daily_post_minute),
        id="daily_top_post",
        replace_existing=True,
    )

    scheduler.add_job(
        func=lambda: daily_update(bot, session_factory, settings),
        trigger=CronTrigger(hour=settings.daily_post_hour, minute=settings.daily_post_minute),
        id="daily_metrics_update",
        replace_existing=True,
    )

    return scheduler
