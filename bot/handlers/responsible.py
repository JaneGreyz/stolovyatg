from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.database.db import Database
from bot.filters.responsible import ManagerAccessFilter
from bot.keyboards.manager import (
    manager_main_keyboard,
    parse_calendar_nav,
    report_day_calendar_keyboard,
)
from bot.services.backup import send_backup_to_chat
from bot.services.monthly_report import send_month_stats_report
from bot.services.user_mode import (
    MODE_ADMIN,
    MODE_GUEST,
    can_switch_mode,
    get_bot_mode,
    has_manager_access,
    is_admin_user,
    is_responsible_staff,
    set_bot_mode,
)
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
    BUTTON_SWITCH_TO_GUEST,
    MANAGER_CALENDAR_PROMPT,
    MANAGER_NO_ACCESS,
    MANAGER_WELCOME,
    MODE_SWITCHED_TO_GUEST,
    STATUS_LABELS,
)

logger = logging.getLogger(__name__)

MANAGER_BUTTONS = (
    BUTTON_MANAGER_REPORT,
    BUTTON_MANAGER_TODAY,
    BUTTON_MANAGER_BACKUP,
)


def _format_period_stats(stats: dict, title: str) -> str:
    lines = [
        ADMIN_STATS_HEADER.format(date=title),
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
    return "\n".join(lines)


async def show_manager_panel(message: Message, settings: Settings) -> None:
    show_guest_switch = (
        message.from_user is not None
        and can_switch_mode(settings, message.from_user.id)
    )
    await message.answer(
        MANAGER_WELCOME,
        reply_markup=manager_main_keyboard(show_guest_switch=show_guest_switch),
        parse_mode="HTML",
    )


async def route_start(
    message: Message,
    state,
    settings: Settings,
    db: Database,
) -> bool:
    """True если /start обработан здесь."""
    if not message.from_user:
        return False

    user_id = message.from_user.id

    if is_responsible_staff(settings, user_id) and not is_admin_user(
        settings, user_id
    ):
        await show_manager_panel(message, settings)
        return True

    if has_manager_access(settings, user_id):
        mode = await get_bot_mode(db, settings, user_id)
        if mode == MODE_ADMIN:
            await show_manager_panel(message, settings)
            return True

    return False


def create_responsible_router(settings: Settings) -> Router:
    router = Router(name="responsible")
    access_filter = ManagerAccessFilter(settings)

    @router.message(Command("panel"), access_filter)
    async def cmd_panel(message: Message, db: Database, state) -> None:
        if message.from_user and can_switch_mode(settings, message.from_user.id):
            await set_bot_mode(db, message.from_user.id, MODE_ADMIN)
            await state.clear()
        await show_manager_panel(message, settings)

    @router.message(F.text == BUTTON_SWITCH_TO_GUEST, access_filter)
    async def switch_to_guest_mode(message: Message, db: Database, state) -> None:
        from bot.handlers.guest import show_welcome

        if not message.from_user or not can_switch_mode(settings, message.from_user.id):
            return
        await set_bot_mode(db, message.from_user.id, MODE_GUEST)
        await message.answer(MODE_SWITCHED_TO_GUEST, parse_mode="HTML")
        await show_welcome(message, state, settings, db)

    @router.message(F.text.in_(MANAGER_BUTTONS), access_filter)
    async def manager_buttons(message: Message, bot: Bot, db: Database) -> None:
        if not message.from_user:
            return
        if can_switch_mode(settings, message.from_user.id):
            mode = await get_bot_mode(db, settings, message.from_user.id)
            if mode != MODE_ADMIN:
                return

        text = (message.text or "").strip()
        if text == BUTTON_MANAGER_REPORT:
            now = datetime.now(get_tz(settings))
            await message.answer(
                MANAGER_CALENDAR_PROMPT,
                reply_markup=report_day_calendar_keyboard(
                    now.year,
                    now.month,
                    today=now.date(),
                ),
                parse_mode="HTML",
            )
            return

        if text == BUTTON_MANAGER_TODAY:
            stats = await db.get_today_stats()
            today = datetime.now(get_tz(settings)).strftime("%d.%m.%Y")
            await message.answer(_format_period_stats(stats, today))
            return

        if text == BUTTON_MANAGER_BACKUP:
            path = await send_backup_to_chat(bot, settings, message.chat.id)
            if path:
                await message.answer(BACKUP_SENT.format(name=path.name))
            else:
                await message.answer(BACKUP_NOT_FOUND)

    @router.message(F.text.in_(MANAGER_BUTTONS))
    async def manager_buttons_denied(message: Message) -> None:
        await message.answer(MANAGER_NO_ACCESS)

    @router.callback_query(F.data.startswith("rcal:"), access_filter)
    async def calendar_callback(
        callback: CallbackQuery,
        bot: Bot,
        db: Database,
    ) -> None:
        if not callback.data or not callback.message:
            await callback.answer()
            return
        if callback.from_user and can_switch_mode(settings, callback.from_user.id):
            mode = await get_bot_mode(db, settings, callback.from_user.id)
            if mode != MODE_ADMIN:
                await callback.answer("Переключитесь в режим администратора", show_alert=True)
                return

        parts = callback.data.split(":")
        action = parts[1]

        if action == "noop":
            await callback.answer()
            return

        if action == "nav":
            year, month = parse_calendar_nav(parts[2], parts[3])
            now = datetime.now(get_tz(settings))
            await callback.message.edit_reply_markup(
                reply_markup=report_day_calendar_keyboard(
                    year,
                    month,
                    today=now.date(),
                )
            )
            await callback.answer()
            return

        if action == "day":
            date_raw = parts[2]
            await callback.answer("Формирую отчёт…")
            stats = await db.get_date_stats(date_raw)
            title = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%d.%m.%Y")
            await callback.message.answer(_format_period_stats(stats, title))
            return

        if action == "month":
            year_month = parts[2]
            await callback.answer("Формирую отчёт…")
            await send_month_stats_report(
                bot,
                db,
                settings,
                year_month,
                chat_ids=[callback.message.chat.id],
            )
            return

        await callback.answer()

    @router.callback_query(F.data.startswith("report:"), access_filter)
    async def legacy_month_report(
        callback: CallbackQuery,
        bot: Bot,
        db: Database,
    ) -> None:
        if not callback.data or not callback.message:
            await callback.answer()
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

    @router.callback_query(F.data.startswith("ryear:"), access_filter)
    async def legacy_change_year(callback: CallbackQuery) -> None:
        if not callback.data or not callback.message:
            await callback.answer()
            return
        raw = callback.data.split(":", 1)[1]
        if raw == "noop":
            await callback.answer()
            return
        year = int(raw)
        now = datetime.now(get_tz(settings))
        await callback.message.edit_reply_markup(
            reply_markup=report_day_calendar_keyboard(
                year,
                now.month,
                today=now.date(),
            )
        )
        await callback.answer()

    return router
