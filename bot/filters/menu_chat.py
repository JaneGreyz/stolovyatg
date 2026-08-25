from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config import Settings


class MenuChatFilter(BaseFilter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(self, message: Message) -> bool:
        if self.settings.menu_chat_id and message.chat.id == self.settings.menu_chat_id:
            return True
        if not self.settings.menu_chat_id:
            ref = str(self.settings.menu_chat_ref).lstrip("@").lower()
            username = (message.chat.username or "").lower()
            return username == ref
        return False
