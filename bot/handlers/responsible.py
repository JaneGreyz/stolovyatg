from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.database.db import Database
from bot.filters.responsible import ResponsibleStaffFilter
from bot.keyboards.manager import manager_main_keyboard, report_calendar_keyboard
from bot.services.backup import send_backup_to_chat
from bot.services.monthly_report import send_month_stats_report
from bot.services.working_hours import get_tz
from bot.texts import (
    ADMIN_STATS_AVG,
    ADMIN_STATS_BY_ADDRESS,
    ADMIN_STATS_BY_STATUS,
    ADMIN_STATS_HEADER,
    ADMIN_STATS_TOTAL,
    BACKUP_NOT_FOUND,
    BACKUP_SENT,
    BUTTON_MANAGER_BACKUP,
    BUTTON_MANAGER_REPORT,
    BUTTON_MANAGER_TODAY,
    MANAGER_CALENDAR_PROMPT,
    MANAGER_WELCOME,
    STATUS_LABELS,
)

logger = logging.getLogger(__name__)


def create_responsible_router(settings: Settings) -> Router:
    router = Router(name="responsible")
    staff_filter = ResponsibleStaffFilter(settings)

    async def show_panel(message: Message) -> None:
        await message.answer(MANAGER_WELCOME, reply_markup=manager_main_keyboard(), parse_mode="HTML")

    @router.message(CommandStart(), staff_filter)
    async def cmd_start(message: Message) -> None:
        await show_panel(message)

    @router.message(Command("panel"), staff_filter)
    async def cmd_panel(message: Message) -> None:
        await show_panel(message)

    @router.message(F.text == BUTTON_MANAGER_REPORT, staff_filter)
    async def btn_report(message: Message) -> None:
        year = datetime.now(get_tz(settings)).year
        await message.answer(
            MANAGER_CALENDAR_PROMPT,
            reply_markup=report_calendar_keyboard(year),
            parse_mode="HTML",
        )

    @router.message(F.text == BUTTON_MANAGER_TODAY, staff_filter)
    async def btn_today(message: Message, db: Database) -> None:
        stats = await db.get_today_stats()
        today = datetime.now(get_tz(settings)).strftime("%d.%m.%Y")
        lines = [
            ADMIN_STATS_HEADER.format(date=today),
            ADMIN_STATS_TOTAL.format(total=stats["total"]),
        ]
        if stats.get("avg_amount"):
            lines.append(
                ADMIN_STATS_AVG.format(
                    avg=int(stats["avg_amount"]),
                    count=stats["avg_count"],
                )
            )
        lines.append(ADMIN_STATS_BY_STATUS)
        for status, count in stats["by_status"].items():
            label = STATUS_LABELS.get(status, status)
            lines.append(f"  • {label}: {count}")
        if stats["by_address"]:
            lines.append(ADMIN_STATS_BY_ADDRESS)
            for address, count in stats["by_address"].items():
                lines.append(f"  • {address}: {count}")
        await message.answer("\n".join(lines))

    @router.message(F.text == BUTTON_MANAGER_BACKUP, staff_filter)
    async def btn_backup(message: Message, bot: Bot) -> None:
        path = await send_backup_to_chat(bot, settings, message.chat.id)
        if path:
            await message.answer(BACKUP_SENT.format(name=path.name))
        else:
            await message.answer(BACKUP_NOT_FOUND)

    @router.callback_query(F.data.startswith("ryear:"), staff_filter)
    async def change_report_year(callback: CallbackQuery) -> None:
        if not callback.data or not callback.message:
            return
        raw = callback.data.split(":", 1)[1]
        if raw == "noop":
            await callback.answer()
            return
        year = int(raw)
        await callback.message.edit_reply_markup(reply_markup=report_calendar_keyboard(year))
        await callback.answer()

    @router.callback_query(F.data.startswith("report:"), staff_filter)
    async def pick_report_month(
        callback: CallbackQuery,
        bot: Bot,
        db: Database,
    ) -> None:
        if not callback.data or not callback.message:
            return
        year_month = callback.data.split(":", 1)[1]
        await callback.answer("Формирую отчёт…")
        await send_month_stats_report(
            bot,
            db,
            settings,
            year_month,
            chat_ids=[callback.message.chat.id],
        )

    return router
