from __future__ import annotations

import logging

from aiogram import Bot

from bot.config import Settings
from bot.database.db import Database
from bot.services.working_hours import is_breakfast_hours
from bot.texts import SENDING_BREAKFAST_MENU, SENDING_MENUS

logger = logging.getLogger(__name__)

MENU_MESSAGE_ID_KEY = "last_menu_message_id"
MENU_CHAT_ID_KEY = "last_menu_chat_id"


async def save_menu_message(db: Database, message_id: int, chat_id: int) -> None:
    await db.set_setting(MENU_MESSAGE_ID_KEY, str(message_id))
    await db.set_setting(MENU_CHAT_ID_KEY, str(chat_id))
    logger.info("Daily menu saved: chat=%s message=%s", chat_id, message_id)


async def get_saved_menu(db: Database) -> tuple[int, int] | None:
    msg = await db.get_setting(MENU_MESSAGE_ID_KEY)
    chat = await db.get_setting(MENU_CHAT_ID_KEY)
    if msg and chat:
        return int(chat), int(msg)
    return None


def _menu_from_chat_id(settings: Settings) -> int | str:
    if settings.menu_chat_id:
        return settings.menu_chat_id
    return settings.menu_chat_ref


async def send_menus_to_guest(
    bot: Bot,
    db: Database,
    settings: Settings,
    chat_id: int,
) -> None:
    if is_breakfast_hours(settings):
        await bot.send_message(chat_id=chat_id, text=SENDING_BREAKFAST_MENU)
        await send_permanent_menu(bot, settings, chat_id, breakfast=True)
        return

    await bot.send_message(chat_id=chat_id, text=SENDING_MENUS)

    saved = await get_saved_menu(db)
    daily_sent = False

    if saved:
        from_chat_id, message_id = saved
        for copy_from in (from_chat_id, _menu_from_chat_id(settings)):
            try:
                await bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=copy_from,
                    message_id=message_id,
                )
                daily_sent = True
                break
            except Exception as exc:
                logger.warning(
                    "copy_message failed from %s msg %s: %s",
                    copy_from,
                    message_id,
                    exc,
                )

        if not daily_sent and saved:
            from_chat_id, message_id = saved
            for forward_from in (from_chat_id, _menu_from_chat_id(settings)):
                try:
                    await bot.forward_message(
                        chat_id=chat_id,
                        from_chat_id=forward_from,
                        message_id=message_id,
                    )
                    daily_sent = True
                    break
                except Exception as exc:
                    logger.warning(
                        "forward_message failed from %s msg %s: %s",
                        forward_from,
                        message_id,
                        exc,
                    )

    if not daily_sent:
        logger.warning("Daily menu not sent to guest chat %s", chat_id)

    await send_permanent_menu(bot, settings, chat_id)


async def send_permanent_menu(
    bot: Bot,
    settings: Settings,
    chat_id: int,
    *,
    breakfast: bool = False,
) -> None:
    from aiogram.types import FSInputFile

    caption = "🥐 Завтраки под ножа" if breakfast else "📋 Постоянное меню"

    if settings.permanent_menu_file_id:
        await bot.send_photo(
            chat_id=chat_id,
            photo=settings.permanent_menu_file_id,
            caption=caption,
        )
        return

    if settings.permanent_menu_path.exists():
        photo = FSInputFile(settings.permanent_menu_path)
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
        )
        return

    await bot.send_message(
        chat_id=chat_id,
        text="Постоянное меню временно недоступно.",
    )
