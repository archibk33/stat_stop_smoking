import asyncio
import aiohttp
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatMemberUpdated
from app.transport.handlers.menu_utils import update_message_with_menu
from app.db.session import async_sessionmaker, AsyncSession
import logging

logger = logging.getLogger(__name__)

router = Router()


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats:open")],
            [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating:menu")],
            [InlineKeyboardButton(text="🔔 Напоминания: Вкл/Выкл", callback_data="notify:toggle")],
            [InlineKeyboardButton(text="🚬 Выкурил сигарету", callback_data="add_relapse")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
            [InlineKeyboardButton(text="🗑️ Сброс статистики", callback_data="reset:confirm")],
        ]
    )


def registration_menu_kb() -> InlineKeyboardMarkup:
    """Клавиатура для незарегистрированных пользователей"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Зарегистрироваться", callback_data="reg:start")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
        ]
    )


@router.message(CommandStart())
async def on_start(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Обработчик команды /start с проверкой регистрации"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return
        
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    async with session_factory() as session:
        from app.db.repo import UserRepo
        users = UserRepo(session)
        user = await users.get_by_id(user_id)
        
        if user and user.quit_date:
            # Пользователь уже зарегистрирован - показываем главное меню
            await message.answer("Главное меню", reply_markup=main_menu_kb())
        else:
            # Пользователь не зарегистрирован - показываем меню регистрации
            await message.answer("Добро пожаловать! Для начала работы необходимо зарегистрироваться.", 
                               reply_markup=registration_menu_kb())


@router.message(Command("menu"))
async def show_menu_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Обработчик команды /menu для показа главного меню"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return
        
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    async with session_factory() as session:
        from app.db.repo import UserRepo
        users = UserRepo(session)
        user = await users.get_by_id(user_id)
        
        if user and user.quit_date:
            # Пользователь уже зарегистрирован - показываем главное меню
            await message.answer("Главное меню", reply_markup=main_menu_kb())
        else:
            # Пользователь не зарегистрирован - показываем меню регистрации
            await message.answer("Для начала работы необходимо зарегистрироваться.", 
                               reply_markup=registration_menu_kb())


@router.message(Command("help"))
async def show_help(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Обработчик команды /help для показа справки"""
    # Проверяем, что это личное сообщение
    if message.chat.type != "private":
        return
        
    help_text = """
🤖 **Справка по боту "Путь Свободного"**

**Основные команды:**
/start - Запустить бота
/menu - Показать главное меню
/help - Показать эту справку

**Функции бота:**
• 📊 Просмотр личной статистики
• 🏆 Рейтинг участников
• 🔔 Настройка напоминаний
• 🚬 Отметка о выкуренной сигарете
• 🗑️ Сброс статистики

**Как использовать:**
1. Зарегистрируйтесь один раз, указав дату последней сигареты
2. Используйте кнопку "🚬 Выкурил сигарету" при рецидиве
3. Следите за своим прогрессом в статистике
4. Соревнуйтесь с другими участниками в рейтинге
5. При необходимости можете сбросить статистику и начать заново

**Примечание:** Регистрация возможна только один раз. При рецидивах счетчик дней не сбрасывается до 3-го рецидива. Сброс статистики удаляет все данные безвозвратно.
"""
    
    await message.answer(help_text, parse_mode="Markdown")


@router.message(~F.text.regexp(r"^\d{4}-\d{2}-\d{2}$") & ~F.text.regexp(r"^\d+(?:[\.,]\d+)?$"))
async def handle_any_message(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Обработчик для любых текстовых сообщений в личных чатах, кроме дат и цен
    
    ВАЖНО: Этот обработчик должен регистрироваться ПОСЛЕ специализированных обработчиков
    (registration.py), чтобы не перехватывать сообщения с датами и ценами.
    
    Фильтры исключают:
    - Даты в формате YYYY-MM-DD (например: 2025-01-01)
    - Цены в формате числа с десятичными знаками (например: 250, 250.50)
    """
    # Проверяем, что это личное сообщение (не групповой чат)
    if message.chat.type != "private":
        return
    
    user_id = message.from_user.id
    logger.info(f"handle_any_message: processing message '{message.text}' from user {user_id}")
    
    # Проверяем, зарегистрирован ли пользователь
    async with session_factory() as session:
        from app.db.repo import UserRepo
        users = UserRepo(session)
        user = await users.get_by_id(user_id)
        
        if user and user.quit_date:
            # Пользователь уже зарегистрирован - показываем главное меню
            await message.answer("Главное меню", reply_markup=main_menu_kb())
        else:
            # Пользователь не зарегистрирован - показываем меню регистрации
            await message.answer("Добро пожаловать! Для начала работы необходимо зарегистрироваться.", 
                               reply_markup=registration_menu_kb())


@router.callback_query(F.data == "help:show")
async def show_help_callback(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Помощь' в главном меню"""
    await callback.answer()
    
    help_text = """
🤖 **Справка по боту "Путь Свободного"**

**Основные команды:**
/start - Запустить бота
/menu - Показать главное меню
/help - Показать эту справку

**Функции бота:**
• 📊 Просмотр личной статистики
• 🏆 Рейтинг участников
• 🔔 Настройка напоминаний
• 🚬 Отметка о выкуренной сигарете
• 🗑️ Сброс статистики

**Как использовать:**
1. Зарегистрируйтесь один раз, указав дату последней сигареты
2. Используйте кнопку "🚬 Выкурил сигарету" при рецидиве
3. Следите за своим прогрессом в статистике
4. Соревнуйтесь с другими участниками в рейтинге
5. При необходимости можете сбросить статистику и начать заново

**Примечание:** Регистрация возможна только один раз. При рецидивах счетчик дней не сбрасывается до 3-го рецидива. Сброс статистики удаляет все данные безвозвратно.
"""
    
    # Создаем клавиатуру с кнопкой возврата в главное меню
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )
    
    await update_message_with_menu(callback, help_text, kb, add_main_menu=False)


@router.callback_query(F.data == "menu:main")
async def return_to_main_menu(callback: CallbackQuery) -> None:
    """Возврат в главное меню"""
    await update_message_with_menu(callback, "Главное меню", main_menu_kb(), add_main_menu=False)


@router.callback_query(F.data == "add_relapse")
async def add_relapse_from_menu(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Добавляет рецидив пользователю из главного меню"""
    await callback.answer()
    
    # Импортируем здесь чтобы избежать циклических импортов
    from app.transport.handlers.group import add_relapse_callback
    await add_relapse_callback(callback, session_factory)


def rating_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🥇 ТОП-10", callback_data="rating:top10")],
            [InlineKeyboardButton(text="🏅 ТОП-50", callback_data="rating:top50")],
            [InlineKeyboardButton(text="🎖️ ТОП-100", callback_data="rating:top100")],
            [InlineKeyboardButton(text="📊 Вся таблица", callback_data="rating:all")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
        ]
    )


@router.callback_query(F.data == "rating:menu")
async def show_rating_menu(callback: CallbackQuery) -> None:
    """Показывает меню рейтинга"""
    await update_message_with_menu(callback, "Выберите тип рейтинга:", rating_menu_kb(), add_main_menu=False)


@router.callback_query(F.data.startswith("rating:top"))
async def show_top_rating(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Показывает ТОП рейтинг"""
    await callback.answer()
    
    # Импортируем здесь чтобы избежать циклических импортов
    from app.transport.handlers.group import build_top_text
    
    # Определяем лимит по типу рейтинга
    rating_type = callback.data.split(":")[-1]
    if rating_type == "top10":
        limit = 10
        title = "ТОП-10"
    elif rating_type == "top50":
        limit = 50
        title = "ТОП-50"
    elif rating_type == "top100":
        limit = 100
        title = "ТОП-100"
    else:
        limit = 10
        title = "ТОП-10"
    
    # Получаем текст рейтинга
    text = await build_top_text(session_factory, limit)
    
    # Создаем клавиатуру с кнопкой возврата в меню рейтинга
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Меню рейтинга", callback_data="rating:menu")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )
    
    await update_message_with_menu(callback, f"{title}:\n\n{text}", kb, add_main_menu=False)


@router.callback_query(F.data == "rating:all")
async def show_all_rating(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Показывает всю таблицу рейтинга"""
    await callback.answer()
    
    # Импортируем здесь чтобы избежать циклических импортов
    from app.transport.handlers.group import build_top_text
    
    # Получаем весь рейтинг (без лимита)
    text = await build_top_text(session_factory, limit=None)
    
    # Создаем клавиатуру с кнопкой возврата в меню рейтинга
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Меню рейтинга", callback_data="rating:menu")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help:show")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )
    
    await update_message_with_menu(callback, f"Вся таблица рейтинга:\n\n{text}", kb, add_main_menu=False)


@router.my_chat_member()
async def on_bot_status_change(event: ChatMemberUpdated, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Обработчик изменения статуса бота - автоматически показывает меню при перезапуске"""
    # Проверяем, что бот стал участником чата (перезапустился)
    # И что это изменение произошло недавно (в течение последних 5 минут)
    if (event.new_chat_member.status in ["member", "administrator"] and 
        event.date.timestamp() > asyncio.get_event_loop().time() - 300):  # 5 минут
        
        # Отправляем главное меню всем пользователям, которые уже зарегистрированы
        async with session_factory() as session:
            from app.db.repo import UserRepo
            users = UserRepo(session)
            registered_users = await users.list_all_members()
            
            # Ограничиваем количество одновременных отправок
            semaphore = asyncio.Semaphore(5)  # Максимум 5 одновременных отправок
            
            async def send_menu_to_user(user_id: int):
                async with semaphore:
                    try:
                        await event.bot.send_message(
                            chat_id=user_id,
                            text="🏠 Главное меню (бот перезапущен)",
                            reply_markup=main_menu_kb()
                        )
                        # Небольшая задержка между отправками
                        await asyncio.sleep(0.1)
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        logger.warning(f"Network issue sending menu to user {user_id}: {e}")
                    except ValueError as e:
                        logger.info(f"Validation error sending menu to user {user_id}: {e}")
                    except Exception as e:
                        # Оставляем один действительно общий перехват, но без спама
                        if "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                            logger.debug(f"User {user_id} blocked bot or is deactivated")
                        elif "chat not found" in str(e).lower():
                            logger.debug(f"Chat not found for user {user_id}")
                        else:
                            logger.warning(f"Failed to send menu to user {user_id}: {e}")
            
            # Создаем задачи для отправки сообщений
            tasks = [send_menu_to_user(user.user_id) for user in registered_users]
            
            # Запускаем все задачи одновременно
            if tasks:
                logger.info(f"Sending menu to {len(tasks)} users after bot restart")
                await asyncio.gather(*tasks, return_exceptions=True)

# Логируем загрузку модуля
logger.info("Start handlers module loaded successfully")
logger.info("Registered handlers:")
logger.info("- on_start: CommandStart()")
logger.info("- show_menu_command: Command('menu')")
logger.info("- show_help: Command('help')")
logger.info("- handle_any_message: ~F.text.regexp patterns (excluding dates and prices)")
logger.info("- show_help_callback: help:show")
logger.info("- return_to_main_menu: menu:main")
logger.info("- add_relapse_from_menu: add_relapse")
logger.info("- show_rating_menu: rating:menu")
logger.info("- show_top_rating: rating:top*")
logger.info("- show_all_rating: rating:all")
logger.info("- on_bot_status_change: my_chat_member")
    







    
