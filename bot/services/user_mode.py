from __future__ import annotations

from bot.config import Settings
from bot.database.db import Database

MODE_GUEST = "guest"
MODE_ADMIN = "admin"

MODE_SETTING_PREFIX = "bot_mode:"


def is_admin_user(settings: Settings, user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.admin_ids


def is_responsible_staff(settings: Settings, user_id: int | None) -> bool:
    return (
        user_id is not None
        and settings.responsible_staff_id is not None
        and user_id == settings.responsible_staff_id
    )


def has_manager_access(settings: Settings, user_id: int | None) -> bool:
    if user_id is None:
        return False
    if is_responsible_staff(settings, user_id):
        return True
    return is_admin_user(settings, user_id)


def can_switch_mode(settings: Settings, user_id: int | None) -> bool:
    """Переключение гость/админ — только для ответственного."""
    return is_responsible_staff(settings, user_id)


async def get_bot_mode(
    db: Database,
    settings: Settings,
    user_id: int,
) -> str:
    if not is_responsible_staff(settings, user_id):
        return MODE_GUEST

    raw = await db.get_setting(f"{MODE_SETTING_PREFIX}{user_id}")
    if raw in (MODE_GUEST, MODE_ADMIN):
        return raw
    return MODE_GUEST


async def set_bot_mode(db: Database, user_id: int, mode: str) -> None:
    if mode not in (MODE_GUEST, MODE_ADMIN):
        raise ValueError(f"Unknown bot mode: {mode}")
    await db.set_setting(f"{MODE_SETTING_PREFIX}{user_id}", mode)
