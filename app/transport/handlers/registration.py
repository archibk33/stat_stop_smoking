from __future__ import annotations

import logging
from datetime import date, timedelta, datetime, timezone
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
from app.transport.handlers.menu_utils import update_message_with_menu

logger = logging.getLogger(__name__)

router = Router()

# Простое in-memory хранилище выбранной даты на время мастера (MVP)
REG_STATE: Dict[int, date] = {}

logger.info("Registration handlers module loaded successfully")

def _parse_user_date(date_str: str) -> Optional[datetime]:
    """
    Допускаем форматы: YYYY-MM-DD и DD.MM.YYYY.
    Возвращаем timezone-aware datetime (UTC) или None, если дата некорректна/будущая.
    """
    candidates = ["%Y-%m-%d", "%d.%m.%Y"]
    for fmt in candidates:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            if dt > datetime.now(timezone.utc):
                return None
            return dt
        except ValueError:
            continue
    return None

# Логируем регистрацию обработчиков для отладки
logger.info("Registering registration handlers:")
logger.info("- reg_start: callback_query with data='reg:start'")
logger.info("- reg_date: callback_query with data starting with 'reg:date:'")
logger.info("- reg_date_custom: message with regex pattern '^\\d{4}-\\d{2}-\\d{2}$'")
logger.info("- reg_price: callback_query with data starting with 'reg:price:'")
logger.info("- reg_price_custom: message with regex pattern '^\\d+(?:[\\.,]\\d+)?$'")


def price_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="200", callback_data="reg:price:200")],
            [InlineKeyboardButton(text="250", callback_data="reg:price:250")],
            [InlineKeyboardButton(text="300", callback_data="reg:price:300")],
            [InlineKeyboardButton(text="Другая", callback_data="reg:price:custom")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
        ]
    )


def date_selection_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора даты"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сегодня", callback_data="reg:date:today")],
            [InlineKeyboardButton(text="Вчера", callback_data="reg:date:yesterday")],
            [InlineKeyboardButton(text="3 дня назад", callback_data="reg:date:3")],
            [InlineKeyboardButton(text="7 дней назад", callback_data="reg:date:7")],
            [InlineKeyboardButton(text="Другая дата", callback_data="reg:date:custom")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
        ]
    )


@router.callback_query(F.data == "reg:start")
async def reg_start(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    logger.info(f"=== REG_START DEBUG START ===")
    logger.info(f"User {user_id} started registration process")
    logger.info(f"REG_STATE before clearing: {REG_STATE}")
    
    # Очищаем предыдущее состояние регистрации, если было
    if user_id in REG_STATE:
        logger.info(f"Clearing previous registration state for user {user_id}")
        REG_STATE.pop(user_id, None)
    
    # Инициализируем состояние регистрации для пользователя
    REG_STATE[user_id] = None
    logger.info(f"Initialized registration state for user {user_id}")
    logger.info(f"REG_STATE after initialization: {REG_STATE}")
    
    await update_message_with_menu(callback, "Дата последней сигареты:", date_selection_kb())
    logger.info(f"Date selection menu sent to user {user_id}")
    logger.info(f"=== REG_START DEBUG END ===")


@router.callback_query(F.data.startswith("reg:date:"))
async def reg_date(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected date option: {callback.data}")

    today = date.today()
    choice = callback.data.split(":")[-1]
    logger.info(f"Date choice: {choice}")
    
    # Очищаем предыдущее состояние регистрации
    if user_id in REG_STATE:
        logger.info(f"Clearing previous registration state for user {user_id}")
        REG_STATE.pop(user_id, None)
    
    if choice == "today":
        qd = today
        logger.info(f"User {user_id} selected today: {qd}")
    elif choice == "yesterday":
        qd = today - timedelta(days=1)
        logger.info(f"User {user_id} selected yesterday: {qd}")
    elif choice.isdigit():
        qd = today - timedelta(days=int(choice))
        logger.info(f"User {user_id} selected {choice} days ago: {qd}")
    elif choice == "custom":
        logger.info(f"User {user_id} chose custom date, entering custom date mode")
        # Добавляем пользователя в состояние регистрации для custom date
        REG_STATE[user_id] = None  # Временно устанавливаем None, дата будет установлена позже
        logger.info(f"Added user {user_id} to REG_STATE for custom date input")
        logger.info(f"REG_STATE after custom date selection: {REG_STATE}")
        await update_message_with_menu(callback, "Введите дату в формате YYYY-MM-DD", InlineKeyboardMarkup(inline_keyboard=[]))
        logger.info(f"Custom date input prompt sent to user {user_id}")
        return
    else:
        logger.warning(f"Unknown date choice: {choice}")
        await update_message_with_menu(callback, "Неизвестный выбор даты. Попробуйте еще раз.", InlineKeyboardMarkup(inline_keyboard=[]))
        return

    # Сохраняем временно и переходим к цене
    REG_STATE[user_id] = qd
    logger.info(f"User {user_id} selected date {qd}, moving to price selection")

    await update_message_with_menu(
        callback,
        f"Выбрана дата: {qd.isoformat()}\nТеперь выберите цену пачки:",
        price_menu_kb()
    )
    logger.info(f"Price selection menu sent to user {user_id}")
    logger.info(f"REG_STATE after date selection: {REG_STATE}")


@router.message(F.text.regexp(r"^\d{4}-\d{2}-\d{2}$"))
async def reg_date_custom(message: Message) -> None:
    try:
        # Дополнительное логирование для отладки
        logger.info(f"=== REG_DATE_CUSTOM DEBUG START ===")
        logger.info(f"Message text: '{message.text}'")
        logger.info(f"Message chat type: {message.chat.type}")
        logger.info(f"Message from user: {message.from_user.id} (@{message.from_user.username})")
        logger.info(f"REG_STATE before processing: {REG_STATE}")
        
        # Проверяем, что это личное сообщение
        if message.chat.type != "private":
            logger.info(f"Ignoring date input in non-private chat: {message.chat.type}")
            return
            
        user_id = message.from_user.id
        logger.info(f"Received date input: {message.text} from user {user_id}")
        
        # Проверяем, что пользователь находится в процессе регистрации
        if user_id not in REG_STATE:
            logger.info(f"User {user_id} not in registration state, starting registration process")
            # Пользователь не в процессе регистрации - начинаем процесс заново
            # Очищаем предыдущее состояние и инициализируем новое
            if user_id in REG_STATE:
                REG_STATE.pop(user_id, None)
            REG_STATE[user_id] = None
            logger.info(f"Initialized registration state for user {user_id}")
        
        # Проверяем, что пользователь в режиме custom date (REG_STATE[user_id] может быть None)
        if REG_STATE[user_id] is not None:
            logger.info(f"User {user_id} already has a date set ({REG_STATE[user_id]}), ignoring message")
            return
        
        # Используем новую функцию валидации даты
        last_smoke = _parse_user_date(message.text)
        if not last_smoke:
            temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
            temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
            await message.answer("Некорректная дата. Пример: 2024-12-31 или 31.12.2024. Дата не должна быть в будущем.", reply_markup=temp_kb)
            return
        
        # Конвертируем datetime в date для совместимости
        qd = last_smoke.date()
        logger.info(f"Successfully parsed and validated date: {qd} for user {user_id}")

        # Сохраняем дату в состоянии регистрации
        REG_STATE[user_id] = qd
        logger.info(f"Stored date {qd} in REG_STATE for user {user_id}")
        logger.info(f"REG_STATE after storing date: {REG_STATE}")

        # Отправляем новое сообщение с клавиатурой выбора цены
        await message.answer("Выберите цену пачки:", reply_markup=price_menu_kb())
        logger.info(f"Sent price selection message to user {user_id}")
        
        # НЕ очищаем состояние регистрации здесь - оно нужно для следующего шага
        logger.info(f"Keeping REG_STATE for user {user_id} for price selection")
        logger.info(f"=== REG_DATE_CUSTOM DEBUG END ===")
        
    except Exception as e:
        logger.error(f"Error in reg_date_custom for user {message.from_user.id}: {e}", exc_info=True)
        # Отправляем сообщение об ошибке пользователю
        try:
            temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
            temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
            await message.answer("Произошла ошибка при обработке даты. Попробуйте еще раз или начните регистрацию заново.", reply_markup=temp_kb)
        except Exception as send_error:
            logger.error(f"Failed to send error message to user {message.from_user.id}: {send_error}")
        logger.info(f"=== REG_DATE_CUSTOM ERROR END ===")


@router.callback_query(F.data.startswith("reg:price:"))
async def reg_price(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    choice = callback.data.split(":")[-1]
    logger.info(f"User {user_id} selected price option: {choice}")

    if choice == "custom":
        logger.info(f"User {user_id} chose custom price, entering custom price mode")
        await update_message_with_menu(callback, "Введите стоимость пачки (число)", InlineKeyboardMarkup(inline_keyboard=[]))
        logger.info(f"Custom price input prompt sent to user {user_id}")
        return

    if not choice.isdigit():
        logger.warning(f"Invalid price choice: {choice}")
        await update_message_with_menu(callback, "Неверное значение цены. Попробуйте еще раз.", InlineKeyboardMarkup(inline_keyboard=[]))
        return

    price = float(choice)
    logger.info(f"User {user_id} selected price {price}, proceeding to save_and_confirm")
    
    await save_and_confirm(callback, session_factory, user_id, price)
    logger.info(f"save_and_confirm completed for user {user_id}")


@router.message(F.text.regexp(r"^\d+(?:[\.,]\d+)?$"))
async def reg_price_custom(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    try:
        # Дополнительное логирование для отладки
        logger.info(f"=== REG_PRICE_CUSTOM DEBUG START ===")
        logger.info(f"Message text: '{message.text}'")
        logger.info(f"Message chat type: {message.chat.type}")
        logger.info(f"Message from user: {message.from_user.id} (@{message.from_user.username})")
        logger.info(f"REG_STATE before processing: {REG_STATE}")
        
        # Проверяем, что это личное сообщение
        if message.chat.type != "private":
            logger.info(f"Ignoring price input in non-private chat: {message.chat.type}")
            return
            
        user_id = message.from_user.id
        logger.info(f"Received price input: {message.text} from user {user_id}")
        
        # Проверяем, что пользователь находится в процессе регистрации
        logger.info(f"Checking registration state for user {user_id}")
        
        if user_id not in REG_STATE:
            logger.info(f"User {user_id} not in registration state, starting registration process")
            # Пользователь не в процессе регистрации - начинаем процесс заново
            # Очищаем предыдущее состояние и инициализируем новое
            if user_id in REG_STATE:
                REG_STATE.pop(user_id, None)
            REG_STATE[user_id] = None
            logger.info(f"Initialized registration state for user {user_id}")
        
        # Проверяем, что у пользователя уже установлена дата
        if REG_STATE[user_id] is None:
            logger.info(f"User {user_id} doesn't have a date set yet, starting date selection")
            # Пользователь не установил дату - предлагаем выбрать дату
            await message.answer("Сначала нужно выбрать дату. Выберите один из вариантов:", reply_markup=date_selection_kb())
            return
        
        logger.info(f"User {user_id} has date {REG_STATE[user_id]} set, proceeding with price {message.text}")
        
        try:
            price = float(message.text.replace(",", "."))  # type: ignore[union-attr]
            logger.info(f"Parsed price {price} for user {user_id}")
            await save_and_confirm(message, session_factory, user_id, price)
            logger.info(f"save_and_confirm completed for user {user_id}")
        except ValueError:
            # Обрабатываем ошибку парсинга цены
            temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
            temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
            await message.answer("Неверная цена. Введите число (например: 250 или 250.50)", reply_markup=temp_kb)
            return
        
        logger.info(f"=== REG_PRICE_CUSTOM DEBUG END ===")
        
    except Exception as e:
        logger.error(f"Error in reg_price_custom for user {message.from_user.id}: {e}", exc_info=True)
        # Отправляем сообщение об ошибке пользователю
        try:
            temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
            temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
            await message.answer("Произошла ошибка при обработке цены. Попробуйте еще раз или начните регистрацию заново.", reply_markup=temp_kb)
        except Exception as send_error:
            logger.error(f"Failed to send error message to user {message.from_user.id}: {send_error}")
        logger.info(f"=== REG_PRICE_CUSTOM ERROR END ===")


async def save_and_confirm(
    source: Message | CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    pack_price: float,
) -> None:
    logger.info(f"=== SAVE_AND_CONFIRM DEBUG START ===")
    logger.info(f"Starting save_and_confirm for user {user_id} with price {pack_price}")
    logger.info(f"REG_STATE at start of save_and_confirm: {REG_STATE}")
    
    qd: Optional[date] = REG_STATE.get(user_id)
    logger.info(f"Retrieved date {qd} from REG_STATE for user {user_id}")

    if qd is None:
        logger.warning(f"User {user_id} has no date set in REG_STATE")
        if isinstance(source, CallbackQuery):
            await update_message_with_menu(source, "Сначала выберите дату", InlineKeyboardMarkup(inline_keyboard=[]))
        else:
            temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
            temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
            await source.answer("Сначала нужно выбрать дату. Начните регистрацию заново.", reply_markup=temp_kb)  # type: ignore[attr-defined]
        return

    settings = get_settings()

    # Проверка членства в группе
    bot: Bot = source.bot  # type: ignore[assignment]
    try:
        member = await bot.get_chat_member(chat_id=settings.group_chat_id, user_id=user_id)
        status = getattr(member, "status", None)
        is_member = status in {"member", "administrator", "creator"}
        logger.info(f"User {user_id} group membership check: status={status}, is_member={is_member}")
    except Exception as e:
        logger.warning(f"Membership check failed for %s: %s", user_id, e)
        error_msg = "Не удалось проверить членство. Попробуйте ещё раз позже."
        if isinstance(source, CallbackQuery):
            await update_message_with_menu(source, error_msg, InlineKeyboardMarkup(inline_keyboard=[]))
        else:
            temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
            temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
            await source.answer(error_msg, reply_markup=temp_kb)
        return

    if not is_member:
        join_hint = "Для регистрации необходимо быть участником нашей группы. Вступите в группу и попробуйте снова."
        if isinstance(source, CallbackQuery):
            await update_message_with_menu(source, join_hint, InlineKeyboardMarkup(inline_keyboard=[]))
        else:
            temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
            temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
            await source.answer(join_hint, reply_markup=temp_kb)
        return

    # Проверяем, не зарегистрирован ли уже пользователь
    async with session_factory() as session:
        users = UserRepo(session)
        existing_user = await users.get_by_id(user_id)
        
        if existing_user and existing_user.quit_date:
            logger.info(f"User {user_id} is already registered with quit_date {existing_user.quit_date}")
            # Пользователь уже зарегистрирован
            if isinstance(source, CallbackQuery):
                await update_message_with_menu(source, "Вы уже зарегистрированы! Нельзя повторно регистрироваться.", InlineKeyboardMarkup(inline_keyboard=[]))
            else:
                temp_kb = InlineKeyboardMarkup(inline_keyboard=[])
                temp_kb.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
                await source.answer("Вы уже зарегистрированы! Нельзя повторно регистрироваться. Используйте главное меню для управления.", reply_markup=temp_kb)
            return

        # Сохраняем пользователя и метрики
        logger.info(f"Saving user {user_id} with quit_date {qd} and pack_price {pack_price}")
        await users.upsert_user(
            user_id=user_id,
            username=source.from_user.username if source.from_user else None,  # type: ignore[attr-defined]
            full_name=source.from_user.full_name if source.from_user else None,  # type: ignore[attr-defined]
            quit_date=qd,
            pack_price=pack_price,
            is_member=True,
        )

        metrics_repo = MetricsRepo(session)
        metrics = calculate_metrics(qd, pack_price)
        logger.info(f"Calculated metrics for user {user_id}: days={metrics.days}, saved_money={metrics.saved_money}")
        await metrics_repo.upsert_metrics(user_id=user_id, days=metrics.days, saved_money=metrics.saved_money)
        await session.commit()
        logger.info(f"Successfully saved user {user_id} and metrics to database")

    # Очищаем временное состояние только после успешного сохранения
    logger.info(f"About to clear REG_STATE for user {user_id}. REG_STATE before clearing: {REG_STATE}")
    REG_STATE.pop(user_id, None)
    logger.info(f"Cleared REG_STATE for user {user_id} after successful save. REG_STATE after clearing: {REG_STATE}")
    
    logger.info(f"Proceeding with admin promotion and title setting for user {user_id}")

    # Промоут до микро-админа и установка кастом-тайтла
    title = generate_admin_title(metrics.days)
    logger.info(f"Generated admin title '{title}' for user {user_id}")
    
    # Проверяем права бота перед промоушеном
    try:
        bot_member = await bot.get_chat_member(chat_id=settings.group_chat_id, user_id=bot.id)
        can_promote = getattr(bot_member, "can_promote_members", False)
        
        if not can_promote:
            logger.warning(f"Bot doesn't have permission to promote members in group {settings.group_chat_id}")
            title = "0д"  # Устанавливаем базовый тайтл
        else:
            # Владельцу (creator) Telegram не позволяет ставить кастом‑тайтл ботом
            if status != "creator":
                logger.info(f"Promoting user {user_id} to admin with title '{title}'")
                try:
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
                    logger.info(f"Successfully promoted user {user_id} and set custom title")
                except Exception as promote_error:
                    logger.warning(f"Promotion failed for %s: %s", user_id, promote_error)
                    title = "0д"  # Устанавливаем базовый тайтл
            else:
                logger.info(f"User {user_id} is creator, skipping promotion")
    except Exception as e:
        logger.error(f"Failed to check bot permissions or promote user {user_id}: {e}")
        title = "0д"  # Устанавливаем базовый тайтл

    rank = rank_text(metrics.days)
    text = (
        f"Сохранено!\n\n"
        f"Стаж: {metrics.days} дн.\n"
        f"Экономия: {metrics.saved_money:.0f}₽\n"
        f"Ранг: {rank}\n"
        f"Тайтл для админа: {title}\n"
    )
    logger.info(f"Generated confirmation text for user {user_id}: {text}")

    # Создаем клавиатуру с кнопками действий
    action_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats:open")],
            [InlineKeyboardButton(text="🏆 ТОП-10", callback_data="top:show")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )

    if isinstance(source, CallbackQuery):
        logger.info(f"Sending confirmation to user {user_id} via callback")
        await update_message_with_menu(source, text, action_kb, add_main_menu=False)
    else:
        logger.info(f"Sending confirmation to user {user_id} via message")
        await source.answer(text, reply_markup=action_kb)
    
    logger.info(f"Registration completed successfully for user {user_id}")
    logger.info(f"=== SAVE_AND_CONFIRM DEBUG END ===")
