from __future__ import annotations

import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.texts import (
    BUTTON_MANAGER_BACKUP,
    BUTTON_MANAGER_REPORT,
    BUTTON_MANAGER_TODAY,
)

MONTH_TITLES = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)

WEEKDAY_HEADERS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def manager_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_MANAGER_REPORT)],
            [KeyboardButton(text=BUTTON_MANAGER_TODAY), KeyboardButton(text=BUTTON_MANAGER_BACKUP)],
        ],
        resize_keyboard=True,
    )


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def report_day_calendar_keyboard(
    year: int,
    month: int,
    *,
    today: date | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"rcal:nav:{year}-{month:02d}:prev",
            ),
            InlineKeyboardButton(
                text=f"{MONTH_TITLES[month]} {year}",
                callback_data="rcal:noop",
            ),
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"rcal:nav:{year}-{month:02d}:next",
            ),
        ],
        [
            InlineKeyboardButton(text=label, callback_data="rcal:noop")
            for label in WEEKDAY_HEADERS
        ],
    ]

    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text="·", callback_data="rcal:noop"))
                continue

            label = str(day)
            if today and today.year == year and today.month == month and today.day == day:
                label = f"•{day}"

            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"rcal:day:{year}-{month:02d}-{day:02d}",
                )
            )
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="📊 Весь месяц",
                callback_data=f"rcal:month:{year}-{month:02d}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_calendar_nav(raw: str, direction: str) -> tuple[int, int]:
    year, month = map(int, raw.split("-"))
    delta = -1 if direction == "prev" else 1
    return _shift_month(year, month, delta)
