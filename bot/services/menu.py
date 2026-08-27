from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto

from bot.config import Settings
from bot.database.db import Database
from bot.services.sheets_menu import download_menu_images, get_saved_sheet_menu
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


async def _resolve_sheet_menu(
    db: Database, settings: Settings
) -> tuple[str, int] | None:
    saved = await get_saved_sheet_menu(db)
    if saved:
        return saved
    if settings.daily_menu_sheet_id and settings.daily_menu_gid is not None:
        return settings.daily_menu_sheet_id, settings.daily_menu_gid
    return None


async def send_permanent_menu_from_sheets(
    bot: Bot,
    db: Database,
    settings: Settings,
    chat_id: int,
) -> bool:
    """Постоянное меню из Google Sheets (замена старой картинки)."""
    sheet = await _resolve_sheet_menu(db, settings)
    if not sheet:
        return False

    sheet_id, gid = sheet
    try:
        images = await download_menu_images(sheet_id, gid)
    except Exception:
        logger.exception("Failed to download permanent menu from Google Sheets")
        return False

    if not images:
        return False

    caption = PERMANENT_MENU_CAPTION

    if len(images) == 1:
        await bot.send_photo(
            chat_id=chat_id,
            photo=BufferedInputFile(images[0], filename="permanent_menu.png"),
            caption=caption,
            parse_mode="HTML",
        )
        return True

    media = [
        InputMediaPhoto(
            media=BufferedInputFile(image, filename=f"permanent_menu_{index}.png"),
            caption=caption if index == 0 else None,
            parse_mode="HTML" if index == 0 else None,
        )
        for index, image in enumerate(images)
    ]
    await bot.send_media_group(chat_id=chat_id, media=media)
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
            if not await send_permanent_menu_from_sheets(bot, db, settings, chat_id):
                logger.warning("Permanent menu (sheets) not sent to guest %s", chat_id)
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

        if not await send_permanent_menu_from_sheets(bot, db, settings, chat_id):
            logger.warning("Permanent menu (sheets) not sent to guest %s", chat_id)
    except Exception:
        logger.exception("Failed to send menus to guest %s", chat_id)
