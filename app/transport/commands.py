from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats


async def setup_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="top_members", description="ТОП-10 стажа"),
    ]
    await bot.set_my_commands(commands=commands, scope=BotCommandScopeAllGroupChats())
