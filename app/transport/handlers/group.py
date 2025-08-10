from __future__ import annotations

import structlog
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.db.repo import MetricsRepo, TopPostRepo
from app.db.session import AsyncSession, async_sessionmaker
from app.transport.handlers.menu_utils import update_message_with_menu

router = Router()


async def build_top_text(session_factory: async_sessionmaker[AsyncSession], limit: int | None = 10) -> str:
    async with session_factory() as session:
        repo = MetricsRepo(session)
        top = await repo.get_top(limit=limit)

    if not top:
        return "Пока нет участников в рейтинге."

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for idx, (user, metrics) in enumerate(top, start=1):
        # Добавляем медальки только для первых трех мест
        if idx <= 3:
            prefix = medals[idx - 1]
        else:
            prefix = f"{idx}."
        
        name = user.full_name or user.username or str(user.user_id)
        # Рассчитываем рейтинг
        score = metrics.days - (metrics.relapses * 3)
        # Добавляем информацию о рецидивах и рейтинге
        relapse_text = f" (рецидивов: {metrics.relapses}, рейтинг: {score})" if metrics.relapses > 0 else f" (рейтинг: {score})"
        lines.append(f"{prefix} {name} — {metrics.days} дн.{relapse_text}")

    # Формируем заголовок в зависимости от лимита
    if limit is None:
        header = "Вся таблица рейтинга:"
    elif limit == 10:
        header = "ТОП-10:"
    elif limit == 50:
        header = "ТОП-50:"
    elif limit == 100:
        header = "ТОП-100:"
    else:
        header = f"ТОП-{limit}:"
    
    return f"{header}\n" + "\n".join(lines)


@router.callback_query(lambda c: c.data == "add_relapse")
async def add_relapse_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Добавляет рецидив пользователю через кнопку"""
    log = structlog.get_logger()
    bot = callback.bot
    
    # Получаем ID пользователя из callback
    user_id = callback.from_user.id
    
    async with session_factory() as session:
        metrics_repo = MetricsRepo(session)
        try:
            metrics = await metrics_repo.add_relapse(user_id)
            relapse_count = metrics.relapses
            
            if relapse_count <= 3:
                text = f"Рецидив добавлен. У вас {relapse_count} рецидивов. Счетчик дней не сброшен."
            else:
                text = f"Рецидив добавлен. У вас {relapse_count} рецидивов. Счетчик дней сброшен."
            
            # Импортируем здесь чтобы избежать циклических импортов
            from app.transport.handlers.menu_utils import update_message_with_menu
            
            # Создаем клавиатуру с кнопками
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
                ]
            )
            
            # Используем update_message_with_menu для добавления кнопки "Главное меню"
            await update_message_with_menu(callback, text, kb, add_main_menu=True)
            
            await session.commit()
            log.info("relapse_added", user_id=user_id, relapse_count=relapse_count)
            
        except Exception as e:
            log.error("relapse_add_failed", user_id=user_id, error=str(e))
            
            # Импортируем здесь чтобы избежать циклических импортов
            from app.transport.handlers.menu_utils import update_message_with_menu
            
            # Создаем клавиатуру с кнопками
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
                ]
            )
            
            # Используем update_message_with_menu для добавления кнопки "Главное меню"
            await update_message_with_menu(callback, "Ошибка при добавлении рецидива. Попробуйте позже.", kb, add_main_menu=True)


@router.callback_query(F.data == "top:show")
async def show_top_in_private(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Показывает ТОП-10 в приватном чате"""
    await callback.answer()
    
    text = await build_top_text(session_factory, limit=10)
    
    # Создаем клавиатуру с кнопками
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
        ]
    )
    
    await update_message_with_menu(callback, text, kb, add_main_menu=True)


@router.message(Command("top_members"))
async def top_members(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    log = structlog.get_logger()
    
    # Проверяем, что это групповой чат
    if message.chat.type == "private":
        log.info("top_members_command_in_private", user_id=message.from_user.id)
        return
    
    bot = message.bot
    text = await build_top_text(session_factory, limit=10)

    # В общем чате не показываем кнопки - только список
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    # Определяем параметры для отправки сообщения
    topic_id = message.message_thread_id
    params = {}
    if topic_id is not None:
        params["message_thread_id"] = topic_id

    # Удалим предыдущий пост ТОПа, если был в том же топике
    async with session_factory() as session:
        top_repo = TopPostRepo(session)
        prev = await top_repo.get_for_chat(message.chat.id, topic_id)
        if prev is not None:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=prev.message_id)
            except Exception as e:  # noqa: BLE001
                log.warning("top_prev_delete_failed", error=str(e))

        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=kb,
            **params,
        )

        await top_repo.set(message.chat.id, sent.message_id, topic_id)
        await session.commit()

    # Диагностика прав бота
    try:
        me = await bot.get_me()
        me_member = await bot.get_chat_member(message.chat.id, me.id)
        can_delete = getattr(getattr(me_member, "can_delete_messages", None), "__bool__", lambda: False)()
        log.info("bot_rights", can_delete_messages=bool(getattr(me_member, "can_delete_messages", False)))
    except Exception as e:  # noqa: BLE001
        log.warning("bot_rights_check_failed", error=str(e))

    # Пытаемся удалить командное сообщение пользователя (требуются права delete_messages)
    try:
        # Проверяем права бота перед удалением
        me = await bot.get_me()
        me_member = await bot.get_chat_member(message.chat.id, me.id)
        can_delete = getattr(me_member, "can_delete_messages", False)
        
        if can_delete:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            log.info("Command message deleted successfully")
        else:
            log.info("Bot doesn't have permission to delete messages")
    except Exception as e:  # noqa: BLE001
        log.warning("top_command_delete_failed", error=str(e))
