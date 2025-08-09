from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from app.config import get_settings
from app.db.repo import MetricsRepo, TopPostRepo
from app.db.session import AsyncSession, async_sessionmaker

router = Router()


def top_inline_kb(bot_username: str) -> InlineKeyboardMarkup:
    deep_link = f"https://t.me/{bot_username}?start=me"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Мой статус в ЛС", url=deep_link)],
            [InlineKeyboardButton(text="🔄 Обновить ТОП", callback_data="top:refresh")],
            [InlineKeyboardButton(text="📌 Закрепить", callback_data="top:pin")],
        ]
    )


async def build_top_text(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        repo = MetricsRepo(session)
        top = await repo.get_top(limit=10)

    if not top:
        return "Пока нет участников в рейтинге."

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for idx, (user, metrics) in enumerate(top, start=1):
        prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
        name = user.full_name or user.username or str(user.user_id)
        lines.append(f"{prefix} {name} — {metrics.days} дн.")

    return "ТОП-10:\n" + "\n".join(lines)


@router.message(Command("top_members"))
async def top_members(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    log = structlog.get_logger()
    bot = message.bot
    me = await bot.get_me()
    text = await build_top_text(session_factory)

    settings = get_settings()
    params = {}
    if settings.topic_id is not None and message.chat.id == settings.group_chat_id:
        params["message_thread_id"] = settings.topic_id

    # Удалим предыдущий пост ТОПа, если был
    async with session_factory() as session:
        top_repo = TopPostRepo(session)
        prev = await top_repo.get_for_chat(message.chat.id)
        if prev is not None:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=prev.message_id)
            except Exception as e:  # noqa: BLE001
                log.warning("top_prev_delete_failed", error=str(e))

        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=top_inline_kb(me.username),
            **params,
        )

        await top_repo.set(message.chat.id, sent.message_id)
        await session.commit()

    # Диагностика прав бота
    try:
        me_member = await bot.get_chat_member(message.chat.id, me.id)
        can_delete = getattr(getattr(me_member, "can_delete_messages", None), "__bool__", lambda: False)()
        log.info("bot_rights", can_delete_messages=bool(getattr(me_member, "can_delete_messages", False)))
    except Exception as e:  # noqa: BLE001
        log.warning("bot_rights_check_failed", error=str(e))

    # Пытаемся удалить командное сообщение пользователя (требуются права delete_messages)
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except Exception as e:  # noqa: BLE001
        log.warning("top_command_delete_failed", error=str(e))


@router.callback_query(lambda c: c.data == "top:refresh")
async def top_refresh(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    bot = callback.message.bot
    me = await bot.get_me()
    new_text = await build_top_text(session_factory)

    if (callback.message.text or "").strip() == new_text.strip():
        await callback.answer("ТОП уже актуален", show_alert=False)
        return

    await callback.message.edit_text(new_text, reply_markup=top_inline_kb(me.username))


@router.callback_query(lambda c: c.data == "top:pin")
async def top_pin(callback: CallbackQuery) -> None:
    await callback.answer()
    settings = get_settings()
    try:
        await callback.message.bot.pin_chat_message(chat_id=settings.group_chat_id, message_id=callback.message.message_id)
    except Exception:
        pass
