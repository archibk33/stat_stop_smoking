from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.db.repo import UserRepo
from app.db.session import AsyncSession, async_sessionmaker
from app.transport.handlers.menu_utils import update_message_with_menu

router = Router()


@router.callback_query(F.data == "notify:toggle")
async def on_notify_toggle(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    async with session_factory() as session:
        repo = UserRepo(session)
        user = await repo.get_by_id(user_id)
        enabled = not (user.notifications if user else False)
        if user is None:
            # создадим запись с пустыми полями
            await repo.upsert_user(
                user_id=user_id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name,
                quit_date=None,
                pack_price=None,
            )
        await repo.set_notifications(user_id, enabled)
        await session.commit()

    # Создаем клавиатуру с кнопками
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )
    
    status_text = "✅ Включены" if enabled else "❌ Выключены"
    await update_message_with_menu(
        callback, 
        f"🔔 Напоминания: {status_text}", 
        kb, 
        add_main_menu=False
    )
