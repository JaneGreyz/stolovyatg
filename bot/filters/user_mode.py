from __future__ import annotations

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import Settings
from bot.database.db import Database
from bot.services.user_mode import (
    MODE_ADMIN,
    MODE_GUEST,
    get_bot_mode,
    is_responsible_staff,
)


class AdminBotModeFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, **data: Any) -> bool:
        settings: Settings | None = data.get("settings")
        db: Database | None = data.get("db")
        if settings is None or db is None:
            return False

        user_id = _user_id(event)
        if not is_responsible_staff(settings, user_id):
            return False

        mode = await get_bot_mode(db, settings, user_id)
        return mode == MODE_ADMIN


class GuestBotModeFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, **data: Any) -> bool:
        settings: Settings | None = data.get("settings")
        db: Database | None = data.get("db")
        if settings is None or db is None:
            return False

        user_id = _user_id(event)
        if user_id is None:
            return True
        if not is_responsible_staff(settings, user_id):
            return True

        mode = await get_bot_mode(db, settings, user_id)
        return mode == MODE_GUEST


class ResponsibleOnlyFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, **data: Any) -> bool:
        settings: Settings | None = data.get("settings")
        if settings is None:
            return False
        return is_responsible_staff(settings, _user_id(event))


def _user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message):
        return event.from_user.id if event.from_user else None
    if isinstance(event, CallbackQuery):
        return event.from_user.id if event.from_user else None
    return None
