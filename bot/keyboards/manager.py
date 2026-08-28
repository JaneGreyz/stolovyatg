from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.texts import (
    BUTTON_MANAGER_BACKUP,
    BUTTON_MANAGER_REPORT,
    BUTTON_MANAGER_TODAY,
)

MONTH_SHORT = (
    "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек",
)


def manager_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_MANAGER_REPORT)],
            [KeyboardButton(text=BUTTON_MANAGER_TODAY), KeyboardButton(text=BUTTON_MANAGER_BACKUP)],
        ],
        resize_keyboard=True,
    )


def report_calendar_keyboard(year: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="◀️", callback_data=f"ryear:{year - 1}"),
            InlineKeyboardButton(text=str(year), callback_data="ryear:noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"ryear:{year + 1}"),
        ]
    ]
    for index in range(0, 12, 3):
        row = [
            InlineKeyboardButton(
                text=MONTH_SHORT[month - 1],
                callback_data=f"report:{year}-{month:02d}",
            )
            for month in range(index + 1, index + 4)
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
