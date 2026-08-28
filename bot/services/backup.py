from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from bot.config import Settings

logger = logging.getLogger(__name__)


def create_database_backup(settings: Settings, label: str = "auto") -> Path | None:
    source = settings.database_path
    if not source.exists():
        logger.warning("Database file not found for backup: %s", source)
        return None

    backup_dir = settings.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backup_dir / f"bot_{label}_{timestamp}.db"
    shutil.copy2(source, destination)
    logger.info("Database backup created: %s", destination)

    _prune_old_backups(backup_dir, settings.backup_keep_count)
    return destination


def _prune_old_backups(backup_dir: Path, keep_count: int) -> None:
    backups = sorted(
        backup_dir.glob("bot_*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[keep_count:]:
        try:
            old_backup.unlink()
            logger.info("Removed old backup: %s", old_backup)
        except OSError:
            logger.exception("Failed to remove old backup %s", old_backup)


def get_latest_backup_path(settings: Settings) -> Path | None:
    backups = sorted(
        settings.backup_dir.glob("bot_*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


async def send_backup_to_chat(
    bot: Bot,
    settings: Settings,
    chat_id: int,
    *,
    create_if_missing: bool = True,
) -> Path | None:
    path = get_latest_backup_path(settings)
    if path is None and create_if_missing:
        path = create_database_backup(settings, label="manual")
    if path is None:
        return None

    await bot.send_document(
        chat_id=chat_id,
        document=FSInputFile(path),
        caption=f"💾 Бэкап базы: {path.name}",
    )
    return path


async def notify_responsible_about_backup(
    bot: Bot,
    settings: Settings,
    backup_path: Path,
) -> None:
    if not settings.responsible_staff_id:
        return
    try:
        await bot.send_document(
            chat_id=settings.responsible_staff_id,
            document=FSInputFile(backup_path),
            caption=f"💾 Автоматический бэкап базы\n{backup_path.name}",
        )
    except Exception:
        logger.exception("Failed to send backup to responsible staff")

