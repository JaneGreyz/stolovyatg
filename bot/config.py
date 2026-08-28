from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    bot_token: str
    staff_chat_id: int
    menu_chat_id: int
    menu_chat_ref: str | int
    menu_hashtag: str
    admin_ids: tuple[int, ...]
    responsible_staff_id: int | None
    database_path: Path
    timezone: str
    work_start: time
    full_menu_start: time
    work_end: time
    work_weekdays_only: bool
    qa_channel_url: str
    reminder_minutes: int
    reminder_check_interval: int
    min_order_amount: int
    permanent_menu_path: Path
    menu_message_id: int | None
    topic_cleanup_interval_days: int
    topic_cleanup_age_days: int
    topic_cleanup_check_interval: int
    backup_dir: Path
    backup_keep_count: int


def _parse_time(value: str) -> time:
    hours, minutes = value.strip().split(":")
    return time(int(hours), int(minutes))


def _parse_admin_ids(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def _parse_menu_chat(raw: str) -> tuple[int | None, str | int]:
    raw = raw.strip()
    if raw.startswith("@"):
        return None, raw
    chat_id = int(raw)
    return chat_id, chat_id


def load_settings() -> Settings:
    database_path = Path(os.getenv("DATABASE_PATH", "data/bot.db"))
    if not database_path.is_absolute():
        database_path = BASE_DIR / database_path

    menu_chat_id_raw, menu_chat_ref = _parse_menu_chat(
        os.environ.get("MENU_CHAT_ID", "@s_mestoest")
    )

    responsible_raw = os.getenv("RESPONSIBLE_STAFF_ID", "").strip()
    responsible_staff_id = int(responsible_raw) if responsible_raw else None

    permanent_menu_path = Path(
        os.getenv("PERMANENT_MENU_PATH", "bot/assets/permanent_menu.png")
    )
    if not permanent_menu_path.is_absolute():
        permanent_menu_path = BASE_DIR / permanent_menu_path

    menu_msg_raw = os.getenv("MENU_MESSAGE_ID", "").strip()
    menu_message_id = int(menu_msg_raw) if menu_msg_raw else None

    backup_dir = Path(os.getenv("BACKUP_DIR", "data/backups"))
    if not backup_dir.is_absolute():
        backup_dir = BASE_DIR / backup_dir

    return Settings(
        bot_token=os.environ["BOT_TOKEN"],
        staff_chat_id=int(os.environ["STAFF_CHAT_ID"]),
        menu_chat_id=menu_chat_id_raw or 0,
        menu_chat_ref=menu_chat_ref,
        menu_hashtag=os.getenv("MENU_HASHTAG", "#меню"),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        responsible_staff_id=responsible_staff_id,
        database_path=database_path,
        timezone=os.getenv("TIMEZONE", "Europe/Moscow"),
        work_start=_parse_time(os.getenv("WORK_START", "08:45")),
        full_menu_start=_parse_time(os.getenv("FULL_MENU_START", "10:00")),
        work_end=_parse_time(os.getenv("WORK_END", "16:45")),
        work_weekdays_only=os.getenv("WORK_WEEKDAYS_ONLY", "1") == "1",
        qa_channel_url=os.getenv("QA_CHANNEL_URL", "https://t.me/s_mestoest"),
        reminder_minutes=int(os.getenv("REMINDER_MINUTES", "5")),
        reminder_check_interval=int(os.getenv("REMINDER_CHECK_INTERVAL", "60")),
        min_order_amount=int(os.getenv("MIN_ORDER_AMOUNT", "500")),
        permanent_menu_path=permanent_menu_path,
        menu_message_id=menu_message_id,
        topic_cleanup_interval_days=int(os.getenv("TOPIC_CLEANUP_INTERVAL_DAYS", "7")),
        topic_cleanup_age_days=int(os.getenv("TOPIC_CLEANUP_AGE_DAYS", "7")),
        topic_cleanup_check_interval=int(os.getenv("TOPIC_CLEANUP_CHECK_INTERVAL", "3600")),
        backup_dir=backup_dir,
        backup_keep_count=int(os.getenv("BACKUP_KEEP_COUNT", "8")),
    )


async def resolve_settings(bot) -> Settings:
    import logging
    from dataclasses import replace

    from aiogram import Bot

    logger = logging.getLogger(__name__)
    base = load_settings()
    if base.menu_chat_id:
        return base

    assert isinstance(bot, Bot)
    try:
        chat = await bot.get_chat(str(base.menu_chat_ref))
        return replace(base, menu_chat_id=chat.id)
    except Exception as exc:
        logger.warning(
            "Could not resolve menu chat %s: %s. Bot will start anyway.",
            base.menu_chat_ref,
            exc,
        )
        return base


def get_settings() -> Settings:
    return load_settings()
