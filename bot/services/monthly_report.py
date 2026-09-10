from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import datetime

from aiogram import Bot

from bot.config import Settings
from bot.database.db import Database
from bot.services.analytics import build_month_stats_messages
from bot.services.working_hours import get_tz
from bot.texts import ADMIN_MONTH_AUTO_HEADER

logger = logging.getLogger(__name__)

MONTHLY_REPORT_SENT_KEY = "monthly_report_sent"


def responsible_recipient_id(settings: Settings) -> int | None:
    return settings.responsible_staff_id


async def send_month_stats_report(
    bot: Bot,
    db: Database,
    settings: Settings,
    year_month: str,
    *,
    chat_ids: list[int] | None = None,
    auto: bool = False,
) -> None:
    stats = await db.get_month_stats(year_month)
    messages = build_month_stats_messages(stats)
    if auto and messages:
        messages[0] = ADMIN_MONTH_AUTO_HEADER + messages[0]

    if chat_ids:
        targets = chat_ids
    elif auto:
        rid = responsible_recipient_id(settings)
        targets = [rid] if rid else []
    else:
        targets = chat_ids or []

    if not targets:
        logger.warning("No recipients for monthly stats report")
        return

    for chat_id in targets:
        try:
            for chunk in messages:
                await bot.send_message(chat_id, chunk, parse_mode="HTML")
            logger.info("Monthly stats sent to %s for %s", chat_id, year_month)
        except Exception:
            logger.exception("Failed to send monthly stats to %s", chat_id)


async def maybe_send_monthly_report(
    bot: Bot,
    db: Database,
    settings: Settings,
) -> None:
    tz = get_tz(settings)
    now = datetime.now(tz)
    last_day = calendar.monthrange(now.year, now.month)[1]
    if now.day != last_day:
        return

    year_month = now.strftime("%Y-%m")
    sent = await db.get_setting(MONTHLY_REPORT_SENT_KEY)
    if sent == year_month:
        return

    await send_month_stats_report(bot, db, settings, year_month, auto=True)
    await db.set_setting(MONTHLY_REPORT_SENT_KEY, year_month)


async def monthly_report_loop(
    bot: Bot,
    db: Database,
    settings: Settings,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await maybe_send_monthly_report(bot, db, settings)
        except Exception:
            logger.exception("Monthly report loop error")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.topic_cleanup_check_interval,
            )
        except asyncio.TimeoutError:
            continue
