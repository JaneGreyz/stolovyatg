from aiogram import Router
from aiogram.types import Message

from bot.config import Settings
from bot.database.db import Database
from bot.filters.menu_chat import MenuChatFilter
from bot.services.menu import save_menu_message


def create_menu_router(settings: Settings) -> Router:
    router = Router(name="menu")
    menu_filter = MenuChatFilter(settings)

    async def _save_if_menu(message: Message, db: Database) -> None:
        text = (message.text or message.caption or "").lower()
        tags = [
            settings.menu_hashtag.lower(),
            settings.menu_hashtag.lower().lstrip("#"),
            f"#{settings.menu_hashtag.lower().lstrip('#')}",
            f"/{settings.menu_hashtag.lower().lstrip('#')}",
        ]
        if not any(tag in text for tag in tags):
            return
        await save_menu_message(db, message.message_id)

    @router.message(menu_filter)
    async def capture_menu_message(message: Message, db: Database) -> None:
        await _save_if_menu(message, db)

    @router.channel_post(menu_filter)
    async def capture_menu_channel_post(message: Message, db: Database) -> None:
        await _save_if_menu(message, db)

    return router
