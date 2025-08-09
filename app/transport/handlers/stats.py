from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.db.models import Metrics
from app.db.session import AsyncSession, async_sessionmaker
from app.domain.services import rank_text

router = Router()


@router.callback_query(F.data == "stats:open")
async def on_stats(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    async with session_factory() as session:
        metrics = await session.get(Metrics, user_id)

    if metrics is None:
        await callback.message.answer("Вы ещё не зарегистрированы. Нажмите: ‘Зарегистрироваться / Обновить дату’.")
        return

    rank = rank_text(metrics.days)
    await callback.message.answer(
        f"Ваша статистика:\n\n"
        f"Стаж: {metrics.days} дн.\n"
        f"Экономия: {metrics.saved_money:.0f}₽\n"
        f"Ранг: {rank}"
    )
