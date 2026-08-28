from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import Settings


class ResponsibleStaffFilter(BaseFilter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _matches(self, user_id: int | None) -> bool:
        if user_id is None or not self.settings.responsible_staff_id:
            return False
        return user_id == self.settings.responsible_staff_id

    async def __call__(self, event: TelegramObject) -> bool:
        if isinstance(event, Message):
            return self._matches(event.from_user.id if event.from_user else None)
        if isinstance(event, CallbackQuery):
            return self._matches(event.from_user.id if event.from_user else None)
        return False
