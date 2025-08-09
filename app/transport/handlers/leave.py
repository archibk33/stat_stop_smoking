from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.db.repo import UserRepo
from app.db.session import AsyncSession, async_sessionmaker

router = Router()


def confirm_leave_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="leave:confirm:yes")],
            [InlineKeyboardButton(text="Нет", callback_data="leave:confirm:no")],
        ]
    )


@router.callback_query(F.data == "leave:open")
async def on_leave_open(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Вы действительно хотите выйти из рейтинга?", reply_markup=confirm_leave_kb())


@router.callback_query(F.data.startswith("leave:confirm:"))
async def on_leave_confirm(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    choice = callback.data.split(":")[-1]
    if choice == "no":
        await callback.message.answer("Остались в рейтинге.")
        return

    user_id = callback.from_user.id
    async with session_factory() as session:
        repo = UserRepo(session)
        await repo.set_is_member(user_id, False)
        await session.commit()

    await callback.message.answer("Вы исключены из рейтинга. Возврат возможен через регистрацию.")
