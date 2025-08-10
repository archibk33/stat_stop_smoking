from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeDefault


async def setup_bot_commands(bot: Bot) -> None:
    # Команды для групповых чатов
    group_commands = [
        BotCommand(command="top_members", description="ТОП-10 стажа"),
    ]
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllGroupChats())
    
    # Команды для личных чатов
    private_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="help", description="Справка по боту"),
    ]
    await bot.set_my_commands(commands=private_commands, scope=BotCommandScopeDefault())
