from __future__ import annotations

from aiogram import Bot

from bot.config import Settings
from bot.database.db import Database
from bot.texts import MENU_NOT_FOUND, SENDING_MENUS


MENU_MESSAGE_ID_KEY = "last_menu_message_id"


async def save_menu_message(db: Database, message_id: int) -> None:
    await db.set_setting(MENU_MESSAGE_ID_KEY, str(message_id))


async def get_saved_menu_message_id(db: Database) -> int | None:
    value = await db.get_setting(MENU_MESSAGE_ID_KEY)
    if value:
        return int(value)
    return None


async def send_menus_to_guest(
    bot: Bot,
    db: Database,
    settings: Settings,
    chat_id: int,
) -> None:
    await bot.send_message(chat_id=chat_id, text=SENDING_MENUS)

    menu_message_id = await get_saved_menu_message_id(db)
    daily_sent = False

    if menu_message_id:
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=settings.menu_chat_ref,
                message_id=menu_message_id,
            )
            daily_sent = True
        except Exception:
            daily_sent = False

    if not daily_sent:
        await bot.send_message(chat_id=chat_id, text=MENU_NOT_FOUND)

    await send_permanent_menu(bot, settings, chat_id)


async def send_permanent_menu(bot: Bot, settings: Settings, chat_id: int) -> None:
    from aiogram.types import FSInputFile

    if settings.permanent_menu_file_id:
        await bot.send_photo(
            chat_id=chat_id,
            photo=settings.permanent_menu_file_id,
            caption="📋 Постоянное меню",
        )
        return

    if settings.permanent_menu_path.exists():
        photo = FSInputFile(settings.permanent_menu_path)
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption="📋 Постоянное меню",
        )
        return

    await bot.send_message(
        chat_id=chat_id,
        text="Постоянное меню временно недоступно.",
    )
