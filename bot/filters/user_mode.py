from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import Settings
from bot.database.db import Database
from bot.services.user_mode import (
    MODE_ADMIN,
    MODE_GUEST,
    can_switch_mode,
    get_bot_mode,
    has_manager_access,
    is_admin_user,
    is_responsible_staff,
)


class AdminBotModeFilter(BaseFilter):
    async def __call__(
        self,
        event: TelegramObject,
        db: Database,
        settings: Settings,
    ) -> bool:
        user_id = _user_id(event)
        if user_id is None or not has_manager_access(settings, user_id):
            return False
        mode = await get_bot_mode(db, settings, user_id)
        return mode == MODE_ADMIN


class GuestBotModeFilter(BaseFilter):
    async def __call__(
        self,
        event: TelegramObject,
        db: Database,
        settings: Settings,
    ) -> bool:
        user_id = _user_id(event)
        if user_id is None:
            return True
        if is_responsible_staff(settings, user_id) and not is_admin_user(
            settings, user_id
        ):
            return False
        if can_switch_mode(settings, user_id):
            mode = await get_bot_mode(db, settings, user_id)
            return mode == MODE_GUEST
        return True


class AdminCapableFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        return can_switch_mode(settings, _user_id(event))


class ResponsibleNonAdminFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        user_id = _user_id(event)
        if user_id is None:
            return False
        return is_responsible_staff(settings, user_id) and not is_admin_user(
            settings, user_id
        )


def _user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message):
        return event.from_user.id if event.from_user else None
    if isinstance(event, CallbackQuery):
        return event.from_user.id if event.from_user else None
    return None
