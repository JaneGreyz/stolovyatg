from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import FSInputFile

from bot.config import Settings
from bot.database.db import Database
from bot.services.working_hours import is_breakfast_hours, is_full_menu_hours
from bot.texts import (
    DAILY_LUNCH_MENU_INTRO,
    PERMANENT_MENU_CAPTION,
    SENDING_BREAKFAST_MENU,
    SENDING_MENUS,
)
from bot.utils import parse_saved_chat_id

logger = logging.getLogger(__name__)

CHANNEL_MENU_MESSAGE_ID_KEY = "channel_menu_message_id"
CHANNEL_MENU_CHAT_ID_KEY = "channel_menu_chat_id"


async def save_channel_menu_message(
    db: Database, message_id: int, chat_id: int | str
) -> None:
    await db.set_setting(CHANNEL_MENU_MESSAGE_ID_KEY, str(message_id))
    await db.set_setting(CHANNEL_MENU_CHAT_ID_KEY, str(chat_id))
    logger.info("Channel daily menu saved: chat=%s message=%s", chat_id, message_id)


async def get_saved_channel_menu(db: Database) -> tuple[int | str, int] | None:
    msg = await db.get_setting(CHANNEL_MENU_MESSAGE_ID_KEY)
    chat = await db.get_setting(CHANNEL_MENU_CHAT_ID_KEY)
    if msg and chat:
        return parse_saved_chat_id(chat), int(msg)
    return None


async def sync_channel_menu_from_env(db: Database, settings: Settings) -> bool:
    """Восстановить меню дня из env после перезапуска (когда база пустая)."""
    if await get_saved_channel_menu(db):
        return False

    if settings.menu_message_id is None:
        return False

    chat_id = settings.menu_chat_id or settings.menu_chat_ref
    await save_channel_menu_message(db, settings.menu_message_id, chat_id)
    logger.info(
        "Channel daily menu restored from env: chat=%s message=%s",
        chat_id,
        settings.menu_message_id,
    )
    return True


def _channel_chat_candidates(
    settings: Settings,
    saved_chat_id: int | str | None = None,
) -> list[int | str]:
    candidates: list[int | str] = []
    seen: set[str] = set()
    for chat_id in (saved_chat_id, settings.menu_chat_id, settings.menu_chat_ref):
        if not chat_id:
            continue
        key = str(chat_id).lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(chat_id)
    return candidates


async def send_permanent_menu(
    bot: Bot,
    settings: Settings,
    chat_id: int,
) -> bool:
    """Постоянное меню — картинка из bot/assets/permanent_menu.png."""
    path = settings.permanent_menu_path
    if not path.is_file():
        logger.error("Permanent menu image not found: %s", path)
        return False

    await bot.send_photo(
        chat_id=chat_id,
        photo=FSInputFile(path),
        caption=PERMANENT_MENU_CAPTION,
        parse_mode="HTML",
    )
    return True


async def send_channel_daily_menu(
    bot: Bot,
    db: Database,
    settings: Settings,
    chat_id: int,
) -> bool:
    """Свежее меню дня — копия поста из канала/сообщества."""
    await sync_channel_menu_from_env(db, settings)

    saved = await get_saved_channel_menu(db)
    if not saved:
        logger.warning("Channel daily menu is not saved — use /setmenu or MENU_MESSAGE_ID")
        return False

    saved_chat_id, message_id = saved
    await bot.send_message(
        chat_id=chat_id,
        text=DAILY_LUNCH_MENU_INTRO,
        parse_mode="HTML",
    )
    for copy_from in _channel_chat_candidates(settings, saved_chat_id):
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=copy_from,
                message_id=message_id,
            )
            return True
        except Exception as exc:
            logger.warning(
                "copy_message failed from %s msg %s: %s",
                copy_from,
                message_id,
                exc,
            )

    for forward_from in _channel_chat_candidates(settings, saved_chat_id):
        try:
            await bot.forward_message(
                chat_id=chat_id,
                from_chat_id=forward_from,
                message_id=message_id,
            )
            return True
        except Exception as exc:
            logger.warning(
                "forward_message failed from %s msg %s: %s",
                forward_from,
                message_id,
                exc,
            )
    return False


async def send_menus_to_guest(
    bot: Bot,
    db: Database,
    settings: Settings,
    chat_id: int,
) -> None:
    try:
        if is_breakfast_hours(settings):
            await bot.send_message(
                chat_id=chat_id,
                text=SENDING_BREAKFAST_MENU,
                parse_mode="HTML",
            )
            if not await send_permanent_menu(bot, settings, chat_id):
                logger.warning("Permanent menu not sent to guest %s", chat_id)
            return

        if not is_full_menu_hours(settings):
            return

        await bot.send_message(
            chat_id=chat_id,
            text=SENDING_MENUS,
            parse_mode="HTML",
        )

        if not await send_channel_daily_menu(bot, db, settings, chat_id):
            logger.warning("Channel daily menu not sent to guest %s", chat_id)

        if not await send_permanent_menu(bot, settings, chat_id):
            logger.warning("Permanent menu not sent to guest %s", chat_id)
    except Exception:
        logger.exception("Failed to send menus to guest %s", chat_id)
