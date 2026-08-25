from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.database.models import Address
from bot.texts import (
    BUTTON_BACK,
    BUTTON_CANCEL,
    BUTTON_CONTACT_MANAGER,
    BUTTON_MAKE_ORDER,
    BUTTON_QA,
    BUTTON_START,
    BUTTON_STATUS_ACCEPTED,
    BUTTON_STATUS_AWAITING_PAYMENT,
    BUTTON_STATUS_CANCELLED,
    BUTTON_STATUS_COMPLETED,
    BUTTON_STATUS_IN_DELIVERY,
    STATUS_FILTER_LABELS,
)


def guest_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_START)],
            [KeyboardButton(text=BUTTON_MAKE_ORDER)],
            [KeyboardButton(text=BUTTON_CONTACT_MANAGER)],
        ],
        resize_keyboard=True,
    )


def guest_order_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура во время оформления заказа (после выбора адреса)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_QA)],
            [KeyboardButton(text=BUTTON_CONTACT_MANAGER)],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_CANCEL, callback_data="order:cancel")]
        ]
    )


def addresses_keyboard(addresses: list[Address]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=addr.full_name, callback_data=f"addr:{addr.id}")]
        for addr in addresses
    ]
    buttons.append(
        [InlineKeyboardButton(text=BUTTON_CANCEL, callback_data="order:cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_status_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_STATUS_ACCEPTED,
                    callback_data=f"status:{order_id}:accepted",
                ),
                InlineKeyboardButton(
                    text=BUTTON_STATUS_AWAITING_PAYMENT,
                    callback_data=f"status:{order_id}:awaiting_payment",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BUTTON_STATUS_IN_DELIVERY,
                    callback_data=f"status:{order_id}:in_delivery",
                ),
                InlineKeyboardButton(
                    text=BUTTON_STATUS_COMPLETED,
                    callback_data=f"status:{order_id}:completed",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BUTTON_STATUS_CANCELLED,
                    callback_data=f"status:{order_id}:cancelled",
                ),
            ],
        ]
    )


def admin_orders_filter_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for status_key, label in STATUS_FILTER_LABELS.items():
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin:filter:{status_key}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_addresses_keyboard(addresses: list[Address]) -> InlineKeyboardMarkup:
    buttons = []
    for addr in addresses:
        status_icon = "✅" if addr.is_active else "❌"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} {addr.short_name}",
                    callback_data=f"admin:addr:{addr.id}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text=BUTTON_BACK, callback_data="admin:back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
