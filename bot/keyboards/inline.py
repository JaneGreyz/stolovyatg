from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.database.models import ACTIVE_STATUSES, STATUS_IN_DELIVERY, Address, Order
from bot.texts import (
    BUTTON_BACK,
    BUTTON_CANCEL,
    BUTTON_CANCEL_ORDER,
    BUTTON_CHANGE_ADDRESS,
    BUTTON_CONTACT_MANAGER,
    BUTTON_LEAVE_REVIEW,
    BUTTON_MAKE_ORDER,
    BUTTON_QA,
    BUTTON_START,
    BUTTON_USE_SAVED_PROFILE,
    BUTTON_STATUS_ACCEPTED,
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
            [KeyboardButton(text=BUTTON_CANCEL_ORDER)],
            [KeyboardButton(text=BUTTON_QA)],
            [KeyboardButton(text=BUTTON_CONTACT_MANAGER)],
        ],
        resize_keyboard=True,
    )


def saved_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_USE_SAVED_PROFILE,
                    callback_data="profile:use",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BUTTON_CHANGE_ADDRESS,
                    callback_data="profile:change",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BUTTON_CANCEL,
                    callback_data="order:cancel",
                )
            ],
        ]
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


def staff_order_keyboard(order: Order) -> InlineKeyboardMarkup:
    """Кнопки менеджера на карточке заказа в группе (не для гостя)."""
    rows = [
        [
            InlineKeyboardButton(
                text=BUTTON_STATUS_ACCEPTED,
                callback_data=f"staff:accepted:{order.id}",
            ),
            InlineKeyboardButton(
                text=BUTTON_STATUS_IN_DELIVERY,
                callback_data=f"staff:in_delivery:{order.id}",
            ),
        ],
    ]

    bottom_row = []
    if order.status == STATUS_IN_DELIVERY:
        bottom_row.append(
            InlineKeyboardButton(
                text=BUTTON_STATUS_COMPLETED,
                callback_data=f"staff:completed:{order.id}",
            )
        )
    bottom_row.append(
        InlineKeyboardButton(
            text=BUTTON_STATUS_CANCELLED,
            callback_data=f"staff:cancel:{order.id}",
        )
    )
    rows.append(bottom_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def staff_order_card_markup(order: Order) -> InlineKeyboardMarkup | None:
    if order.status in ACTIVE_STATUSES:
        return staff_order_keyboard(order)
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
