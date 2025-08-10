from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler


from app.config import Settings
from app.db.repo import MetricsRepo, UserRepo, TopPostRepo
from app.db.models import Metrics
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
        # Рассчитываем рейтинг
        score = metrics.days - (metrics.relapses * 3)
        # Добавляем информацию о рецидивах и рейтинге
        relapse_text = f" (рецидивов: {metrics.relapses}, рейтинг: {score})" if metrics.relapses > 0 else f" (рейтинг: {score})"
        lines.append(f"{prefix} {name} — {metrics.days} дн.{relapse_text}")

    text = "ТОП-10:\n" + "\n".join(lines)

    # В ежедневном посте не показываем кнопки - только список
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    try:
        # Удаляем предыдущий пост ТОПа, если был
        top_repo = TopPostRepo(session)
        prev = await top_repo.get_for_chat(settings.group_chat_id, None)
        if prev is not None:
            try:
                # Проверяем права бота перед удалением
                me = await bot.get_me()
                member = await bot.get_chat_member(settings.group_chat_id, me.id)
                if getattr(member, "can_delete_messages", False) or member.status in ("creator", "administrator"):
                    await bot.delete_message(chat_id=settings.group_chat_id, message_id=prev.message_id)
                else:
                    structlog.get_logger().info("Skip delete: no rights in chat %s", settings.group_chat_id)
            except Exception as e:  # noqa: BLE001
                structlog.get_logger().warning("daily_top_prev_delete_failed", error=str(e))

        # Отправляем новый пост
        sent = await bot.send_message(chat_id=settings.group_chat_id, text=text, reply_markup=kb)
        
        # Сохраняем информацию о новом посте
        await top_repo.set(settings.group_chat_id, sent.message_id, None)
        await session.commit()
        
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
            # Получаем текущие метрики для сохранения количества рецидивов
            current_metrics = await session.get(Metrics, user.user_id)
            if current_metrics and current_metrics.relapses > 0:
                # Если есть рецидивы, сбрасываем дни только если их больше 3
                if current_metrics.relapses > 3:
                    m.days = 0
                # Сохраняем количество рецидивов
                await metrics_repo.upsert_metrics_with_relapses(user.user_id, m.days, m.saved_money, current_metrics.relapses)
            else:
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

    # ВНИМАНИЕ: тестовый интервал. В продакшене заменить на >= 3600 секунд.
    # Оставляем 30 сек по задаче.
    
    # Для тестирования: ТОП-10 каждые 30 секунд
    scheduler.add_job(
        func=daily_post_top,
        args=[bot, session_factory, settings],
        trigger="interval",
        seconds=30,
        id="test_top_post",
        replace_existing=True,
    )

    # Для тестирования: обновление метрик каждые 30 секунд
    scheduler.add_job(
        func=daily_update,
        args=[bot, session_factory, settings],
        trigger="interval",
        seconds=30,
        id="test_metrics_update",
        replace_existing=True,
    )

    return scheduler
