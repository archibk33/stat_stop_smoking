from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot

from app.config import get_settings
from app.db.repo import UserRepo
from app.db.session import AsyncSession, async_sessionmaker
from app.transport.handlers.menu_utils import update_message_with_menu

router = Router()


def confirm_reset_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, сбросить", callback_data="reset:yes")],
            [InlineKeyboardButton(text="Нет, отменить", callback_data="reset:no")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
        ]
    )


@router.callback_query(F.data == "reset:confirm")
async def on_reset_confirm(callback: CallbackQuery) -> None:
    """Показывает подтверждение сброса статистики"""
    await callback.answer()
    await callback.message.answer(
        "⚠️ **Внимание!**\n\n"
        "Вы действительно хотите сбросить всю статистику?\n\n"
        "Это действие:\n"
        "• Удалит все ваши данные из рейтинга\n"
        "• Сбросит счетчик дней без сигарет\n"
        "• Удалит историю рецидивов\n"
        "• Снимет права администратора в группе\n\n"
        "**Действие необратимо!**",
        reply_markup=confirm_reset_kb(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "reset:no")
async def on_reset_cancel(callback: CallbackQuery) -> None:
    """Отменяет сброс статистики"""
    await callback.answer()
    
    # Создаем клавиатуру с кнопками
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )
    await update_message_with_menu(callback, "Сброс статистики отменен.", kb, add_main_menu=False)


@router.callback_query(F.data == "reset:yes")
async def on_reset_execute(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Выполняет сброс статистики пользователя"""
    await callback.answer()
    
    user_id = callback.from_user.id
    settings = get_settings()
    
    async with session_factory() as session:
        # Снимаем права администратора в группе
        bot: Bot = callback.bot
        try:
            await bot.promote_chat_member(
                chat_id=settings.group_chat_id,
                user_id=user_id,
                can_pin_messages=False,
                can_promote_members=False,
                can_restrict_members=False,
                can_delete_messages=False,
                can_edit_messages=False,
                can_invite_users=False,
                can_manage_chat=False,
                can_manage_video_chats=False,
                can_manage_topics=False
            )
            
            # Обновляем custom title админа на "0д"
            await bot.set_chat_administrator_custom_title(
                chat_id=settings.group_chat_id,
                user_id=user_id,
                custom_title="0д"
            )
        except Exception:
            # Игнорируем ошибки при снятии прав
            pass
        
        # Удаляем все данные пользователя из БД
        repo = UserRepo(session)
        await repo.delete_user_data(user_id)
        await session.commit()
    
    # Показываем сообщение об успешном сбросе с кнопкой регистрации
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Зарегистрироваться", callback_data="reg:start")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
        ]
    )
    
    await update_message_with_menu(
        callback, 
        "✅ **Статистика успешно сброшена!**\n\n"
        "Все ваши данные удалены из рейтинга.\n"
        "Теперь вы можете зарегистрироваться заново.",
        kb, 
        add_main_menu=False
    )
