import logging

from aiogram import Router
from aiogram.types import Message

from bot.config import Settings
from bot.database.db import Database
from bot.filters.menu_chat import MenuChatFilter
from bot.services.menu import save_menu_message

logger = logging.getLogger(__name__)


def _is_menu_post(message: Message, settings: Settings) -> bool:
    text = (message.text or message.caption or "").lower()
    tag = settings.menu_hashtag.lower().lstrip("#/ ")
    markers = (
        tag,
        f"#{tag}",
        f"/{tag}",
        "меню",
        "#меню",
        "/меню",
    )
    if any(marker in text for marker in markers):
        return True
    # Меню часто публикуется картинкой с хэштегом только в комментарии — сохраняем фото
    if message.photo and ("меню" in text or not text.strip()):
        return True
    return False


def create_menu_router(settings: Settings) -> Router:
    router = Router(name="menu")
    menu_filter = MenuChatFilter(settings)

    async def _capture(message: Message, db: Database) -> None:
        if not _is_menu_post(message, settings):
            return
        await save_menu_message(db, message.message_id, message.chat.id)
        logger.info("Captured menu post in chat %s", message.chat.id)

    @router.message(menu_filter)
    async def capture_menu_message(message: Message, db: Database) -> None:
        await _capture(message, db)

    @router.channel_post(menu_filter)
    async def capture_menu_channel_post(message: Message, db: Database) -> None:
        await _capture(message, db)

    @router.edited_channel_post(menu_filter)
    async def capture_menu_edited(message: Message, db: Database) -> None:
        await _capture(message, db)

    return router
