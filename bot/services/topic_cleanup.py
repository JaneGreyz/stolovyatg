from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot.config import Settings
from bot.database.db import Database
from bot.services.backup import create_database_backup, notify_responsible_about_backup
from bot.services.working_hours import get_tz

logger = logging.getLogger(__name__)

LAST_CLEANUP_KEY = "last_topic_cleanup_at"


async def _cleanup_due(settings: Settings, db: Database) -> bool:
    raw = await db.get_setting(LAST_CLEANUP_KEY)
    if not raw:
        return True

    tz = get_tz(settings)
    try:
        last_run = datetime.fromisoformat(raw)
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=tz)
    except ValueError:
        return True

    return datetime.now(tz) - last_run >= timedelta(days=settings.topic_cleanup_interval_days)


async def run_topic_cleanup(
    bot: Bot,
    db: Database,
    settings: Settings,
    *,
    force: bool = False,
) -> dict[str, int]:
    if not force and not await _cleanup_due(settings, db):
        return {"skipped": 1, "deleted": 0, "failed": 0}

    backup_path = create_database_backup(settings, label="topics")
    if backup_path is None:
        logger.error("Topic cleanup aborted: backup failed")
        return {"skipped": 0, "deleted": 0, "failed": 0, "backup_failed": 1}

    await notify_responsible_about_backup(bot, settings, backup_path)

    orders = await db.get_orders_with_stale_topics(settings.topic_cleanup_age_days)
    deleted = 0
    failed = 0

    for order in orders:
        if not order.topic_id:
            continue
        try:
            await bot.delete_forum_topic(
                chat_id=settings.staff_chat_id,
                message_thread_id=order.topic_id,
            )
            await db.clear_order_topic(order.id)
            deleted += 1
            logger.info("Deleted forum topic for order #%s", order.id)
        except TelegramBadRequest as exc:
            err = str(exc).lower()
            if "not found" in err or "topic_id_invalid" in err:
                await db.clear_order_topic(order.id)
                deleted += 1
                logger.info("Topic already gone for order #%s", order.id)
            else:
                failed += 1
                logger.warning("Failed to delete topic for order #%s: %s", order.id, exc)
        except Exception:
            failed += 1
            logger.exception("Failed to delete topic for order #%s", order.id)

    tz = get_tz(settings)
    await db.set_setting(LAST_CLEANUP_KEY, datetime.now(tz).isoformat())
    logger.info(
        "Topic cleanup finished: deleted=%s failed=%s backup=%s",
        deleted,
        failed,
        backup_path,
    )
    return {
        "skipped": 0,
        "deleted": deleted,
        "failed": failed,
        "backup": str(backup_path),
    }


async def topic_cleanup_loop(
    bot: Bot,
    db: Database,
    settings: Settings,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await run_topic_cleanup(bot, db, settings)
        except Exception:
            logger.exception("Topic cleanup loop error")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.topic_cleanup_check_interval,
            )
        except asyncio.TimeoutError:
            continue
