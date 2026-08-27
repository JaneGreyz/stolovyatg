from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.database.models import ACTIVE_STATUSES, Address, Order
from bot.texts import (
    BUTTON_BACK,
    BUTTON_CANCEL,
    BUTTON_CANCEL_ORDER,
    BUTTON_CONTACT_MANAGER,
    BUTTON_LEAVE_REVIEW,
    BUTTON_MAKE_ORDER,
    BUTTON_QA,
    BUTTON_START,
    BUTTON_STAFF_CANCEL_ORDER,
    BUTTON_STAFF_COMPLETE_ORDER,
    STATUS_FILTER_LABELS,
)


def guest_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_START)],
            [KeyboardButton(text=BUTTON_MAKE_ORDER)],
            [KeyboardButton(text=BUTTON_CANCEL_ORDER)],
            [KeyboardButton(text=BUTTON_CONTACT_MANAGER)],
            [KeyboardButton(text=BUTTON_LEAVE_REVIEW)],
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


def cancel_active_order_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_CANCEL,
                    callback_data="guest:cancel_active",
                )
            ]
        ]
    )


def staff_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Кнопки менеджера на карточке заказа в группе (не для гостя)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_STAFF_COMPLETE_ORDER,
                    callback_data=f"staff:complete:{order_id}",
                ),
                InlineKeyboardButton(
                    text=BUTTON_STAFF_CANCEL_ORDER,
                    callback_data=f"staff:cancel:{order_id}",
                ),
            ],
        ]
    )


def staff_order_card_markup(order: Order) -> InlineKeyboardMarkup | None:
    if order.status in ACTIVE_STATUSES:
        return staff_order_keyboard(order.id)
    return None


def review_rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text=str(i), callback_data=f"review:{order_id}:{i}")
            for i in range(1, 6)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def review_skip_keyboard() -> InlineKeyboardMarkup:
    from bot.texts import REVIEW_SKIP

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=REVIEW_SKIP, callback_data="review:skip")]
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
