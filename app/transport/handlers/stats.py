from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.db.models import Metrics
from app.db.session import AsyncSession, async_sessionmaker
from app.domain.services import rank_text
from app.transport.handlers.menu_utils import update_message_with_menu

router = Router()


@router.callback_query(F.data == "stats:open")
async def on_stats(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    async with session_factory() as session:
        metrics = await session.get(Metrics, user_id)

    if metrics is None:
        # Создаем клавиатуру с кнопкой регистрации и помощи
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Зарегистрироваться", callback_data="reg:start")],
                [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
            ]
        )
        await update_message_with_menu(
            callback, 
            "Вы ещё не зарегистрированы. Нажмите 'Зарегистрироваться' для начала работы.", 
            kb,
            add_main_menu=False
        )
        return

    rank = rank_text(metrics.days)
    text = (
        f"Ваша статистика:\n\n"
        f"Стаж: {metrics.days} дн.\n"
        f"Экономия: {metrics.saved_money:.0f}₽\n"
        f"Рецидивы: {metrics.relapses}\n"
        f"Ранг: {rank}"
    )
    
    # Создаем клавиатуру с кнопкой главного меню
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )
    
    await update_message_with_menu(callback, text, kb, add_main_menu=False)
