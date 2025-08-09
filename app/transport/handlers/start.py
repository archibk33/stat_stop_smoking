from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Зарегистрироваться / Обновить дату", callback_data="reg:start")],
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats:open")],
            [InlineKeyboardButton(text="🔔 Напоминания: Вкл/Выкл", callback_data="notify:toggle")],
            [InlineKeyboardButton(text="↩️ Выйти из рейтинга", callback_data="leave:open")],
        ]
    )


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer("Главное меню", reply_markup=main_menu_kb())
