from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Dict

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)
from aiogram import Bot

from app.config import get_settings
from app.db.repo import MetricsRepo, UserRepo
from app.db.session import AsyncSession, async_sessionmaker
from app.domain.services import calculate_metrics, generate_admin_title, rank_text

router = Router()

# Простое in-memory хранилище выбранной даты на время мастера (MVP)
REG_STATE: Dict[int, date] = {}


# Простые callback_data без HMAC пока (MVP)

def registration_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data="reg:date:today")],
            [InlineKeyboardButton(text="Вчера", callback_data="reg:date:yesterday")],
            [InlineKeyboardButton(text="3 дня назад", callback_data="reg:date:3")],
            [InlineKeyboardButton(text="7 дней назад", callback_data="reg:date:7")],
            [InlineKeyboardButton(text="Другая дата", callback_data="reg:date:custom")],
        ]
    )


def price_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="200", callback_data="reg:price:200")],
            [InlineKeyboardButton(text="250", callback_data="reg:price:250")],
            [InlineKeyboardButton(text="300", callback_data="reg:price:300")],
            [InlineKeyboardButton(text="Другая", callback_data="reg:price:custom")],
        ]
    )


@router.callback_query(F.data == "reg:start")
async def reg_start(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Дата последней сигареты:", reply_markup=registration_menu_kb())


@router.callback_query(F.data.startswith("reg:date:"))
async def reg_date(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    today = date.today()
    choice = callback.data.split(":")[-1]
    if choice == "today":
        qd = today
    elif choice == "yesterday":
        qd = today - timedelta(days=1)
    elif choice.isdigit():
        qd = today - timedelta(days=int(choice))
    elif choice == "custom":
        await callback.message.answer("Введите дату в формате YYYY-MM-DD")
        return
    else:
        await callback.message.answer("Неизвестный выбор")
        return

    # Сохраняем временно и переходим к цене
    REG_STATE[user_id] = qd

    await callback.message.answer(
        f"Выбрана дата: {qd.isoformat()}\nТеперь выберите цену пачки:", reply_markup=price_menu_kb()
    )


@router.message(F.text.regexp(r"^\d{4}-\d{2}-\d{2}$"))
async def reg_date_custom(message: Message) -> None:
    try:
        parts = [int(p) for p in message.text.split("-")]  # type: ignore[union-attr]
        qd = date(parts[0], parts[1], parts[2])
    except Exception:
        await message.answer("Неверная дата. Введите в формате YYYY-MM-DD")
        return

    REG_STATE[message.from_user.id] = qd  # type: ignore[union-attr]

    await message.answer("Выберите цену пачки:", reply_markup=price_menu_kb())


@router.callback_query(F.data.startswith("reg:price:"))
async def reg_price(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    choice = callback.data.split(":")[-1]

    if choice == "custom":
        await callback.message.answer("Введите стоимость пачки (число)")
        return

    if not choice.isdigit():
        await callback.message.answer("Неверное значение цены")
        return

    price = float(choice)
    await save_and_confirm(callback, session_factory, user_id, price)


@router.message(F.text.regexp(r"^\d+(?:[\.,]\d+)?$"))
async def reg_price_custom(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    price = float(message.text.replace(",", "."))  # type: ignore[union-attr]
    user_id = message.from_user.id
    await save_and_confirm(message, session_factory, user_id, price)


async def save_and_confirm(
    source: Message | CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    pack_price: float,
) -> None:
    qd: Optional[date] = REG_STATE.get(user_id)

    if qd is None:
        if isinstance(source, CallbackQuery):
            await source.message.answer("Сначала выберите дату")
        else:
            await source.answer("Сначала выберите дату")  # type: ignore[attr-defined]
        return

    settings = get_settings()

    # Проверка членства в группе
    bot: Bot = source.bot  # type: ignore[assignment]
    try:
        member = await bot.get_chat_member(chat_id=settings.group_chat_id, user_id=user_id)
        status = getattr(member, "status", None)
        is_member = status in {"member", "administrator", "creator"}
    except Exception:
        is_member = False
        status = None

    if not is_member:
        join_hint = "Вступите в нашу группу и попробуйте снова."
        if isinstance(source, CallbackQuery):
            await source.message.answer(join_hint)
        else:
            await source.answer(join_hint)
        return

    # Сохраняем пользователя и метрики
    async with session_factory() as session:
        users = UserRepo(session)
        metrics_repo = MetricsRepo(session)

        await users.upsert_user(
            user_id=user_id,
            username=source.from_user.username if source.from_user else None,  # type: ignore[attr-defined]
            full_name=source.from_user.full_name if source.from_user else None,  # type: ignore[attr-defined]
            quit_date=qd,
            pack_price=pack_price,
            is_member=True,
        )

        metrics = calculate_metrics(qd, pack_price)
        await metrics_repo.upsert_metrics(user_id=user_id, days=metrics.days, saved_money=metrics.saved_money)
        await session.commit()

    # очищаем временное состояние
    REG_STATE.pop(user_id, None)

    # Промоут до микро-админа и установка кастом-тайтла
    title = generate_admin_title(metrics.days)
    try:
        # Владельцу (creator) Telegram не позволяет ставить кастом‑тайтл ботом
        if status != "creator":
            await bot.promote_chat_member(
                chat_id=settings.group_chat_id,
                user_id=user_id,
                can_pin_messages=True,
                can_change_info=False,
                can_invite_users=False,
                can_manage_topics=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_manage_chat=False,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
            )
            await bot.set_chat_administrator_custom_title(
                chat_id=settings.group_chat_id,
                user_id=user_id,
                custom_title=title,
            )
    except Exception:
        # Игнорируем ошибки промоушена/тайтла
        pass

    rank = rank_text(metrics.days)
    text = (
        f"Сохранено!\n\n"
        f"Стаж: {metrics.days} дн.\n"
        f"Экономия: {metrics.saved_money:.0f}₽\n"
        f"Ранг: {rank}\n"
        f"Тайтл для админа: {title}\n"
    )

    if isinstance(source, CallbackQuery):
        await source.message.answer(text)
    else:
        await source.answer(text)
