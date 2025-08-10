import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logger = logging.getLogger(__name__)

def add_main_menu_button(keyboard: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Добавляет кнопку 'Главное меню' к существующей клавиатуре"""
    new_keyboard = keyboard.model_copy()
    # Проверяем, что inline_keyboard существует и является списком
    if not hasattr(new_keyboard, 'inline_keyboard') or new_keyboard.inline_keyboard is None:
        new_keyboard.inline_keyboard = []
    new_keyboard.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
    return new_keyboard


async def update_message_with_menu(
    callback: CallbackQuery, 
    text: str, 
    keyboard: InlineKeyboardMarkup,
    add_main_menu: bool = True
) -> None:
    """Обновляет сообщение с новым меню, удаляя предыдущее"""
    logger.info(f"update_message_with_menu called for user {callback.from_user.id}")
    logger.info(f"Text: {text}")
    logger.info(f"Add main menu: {add_main_menu}")
    
    try:
        # Удаляем предыдущее сообщение
        await callback.message.delete()
        logger.info(f"Previous message deleted for user {callback.from_user.id}")
    except Exception as e:
        # Логируем конкретные ошибки для отладки
        if "message to delete not found" in str(e).lower():
            logger.debug(f"Message already deleted for user {callback.from_user.id}")
        elif "message can't be deleted" in str(e).lower():
            logger.warning(f"Bot doesn't have permission to delete message for user {callback.from_user.id}")
        else:
            logger.debug(f"Ignore delete_message error: {e}")
        # Продолжаем выполнение даже при ошибке удаления
    
    # Добавляем кнопку главного меню если нужно
    if add_main_menu:
        keyboard = add_main_menu_button(keyboard)
        logger.info(f"Main menu button added for user {callback.from_user.id}")
    
    # Отправляем новое сообщение
    await callback.message.answer(text, reply_markup=keyboard)
    logger.info(f"New message sent for user {callback.from_user.id}")
