from aiogram import F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.database.db import Database
from bot.services.menu import save_menu_message


def _is_menu_chat(message: Message, settings: Settings) -> bool:
    if settings.menu_chat_id and message.chat.id == settings.menu_chat_id:
        return True
    if not settings.menu_chat_id:
        ref = str(settings.menu_chat_ref).lstrip("@").lower()
        username = (message.chat.username or "").lower()
        return username == ref
    return False


def create_menu_router(settings: Settings) -> Router:
    router = Router(name="menu")
    menu_chat_filter = F.func(lambda message: _is_menu_chat(message, settings))

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

    @router.message(menu_chat_filter)
    async def capture_menu_message(message: Message, db: Database) -> None:
        await _save_if_menu(message, db)

    @router.channel_post(menu_chat_filter)
    async def capture_menu_channel_post(message: Message, db: Database) -> None:
        await _save_if_menu(message, db)

    return router
