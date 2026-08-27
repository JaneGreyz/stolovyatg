from __future__ import annotations

from html import escape
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

logger = logging.getLogger(__name__)

from bot.config import Settings
from bot.database.db import Database
from bot.database.models import Order
from bot.keyboards.inline import staff_order_card_markup, staff_order_keyboard
from bot.services.working_hours import is_breakfast_hours
from bot.texts import STAFF_NEW_ORDER_NOTIFICATION, STAFF_ORDER_CARD, STATUS_LABELS


def format_guest_name(message: Message) -> str:
    user = message.from_user
    if not user:
        return "Гость"
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(part for part in parts if part).strip()
    return name or (user.username or "Гость")


def build_order_card_text(order: Order) -> str:
    username_line = ""
    if order.guest_username:
        username_line = f"🔗 <b>Username:</b> @{escape(order.guest_username)}\n"

    order_text = escape(order.order_text or "— (ещё не указан)")
    amount_line = (
        f"{order.order_amount} ₽"
        if order.order_amount
        else "— (укажите числом в теме)"
    )
    amount_hint = (
        ""
        if order.order_amount
        else "\n\n<i>💰 Чтобы указать сумму — напишите число в этой теме.</i>"
    )
    status_line = ""
    if order.status not in ("new",):
        label = STATUS_LABELS.get(order.status, order.status)
        status_line = f"\n📌 <b>Статус:</b> {label}\n"

    return STAFF_ORDER_CARD.format(
        order_id=order.id,
        address=escape(order.address),
        clarification=escape(order.address_clarification),
        phone=escape(order.phone),
        guest_name=escape(order.guest_name),
        guest_id=order.guest_id,
        username_line=username_line,
        amount_line=amount_line,
        order_text=order_text,
        amount_hint=amount_hint,
        status_line=status_line,
    )


async def _send_order_card(
    bot: Bot,
    settings: Settings,
    order: Order,
    topic_id: int,
) -> int | None:
    card_text = build_order_card_text(order)
    markups = (staff_order_keyboard(order.id), None)

    for markup in markups:
        try:
            card_message = await bot.send_message(
                chat_id=settings.staff_chat_id,
                message_thread_id=topic_id,
                text=card_text,
                parse_mode="HTML",
                reply_markup=markup,
            )
            return card_message.message_id
        except TelegramBadRequest as exc:
            logger.warning(
                "Order card send failed for #%s (markup=%s): %s",
                order.id,
                markup is not None,
                exc,
            )

    try:
        plain = (
            f"🆕 Заказ #{order.id}\n"
            f"📍 {order.address}\n"
            f"👤 {order.guest_name}\n"
            f"📞 {order.phone}\n\n"
            f"📝 {order.order_text or '—'}"
        )
        card_message = await bot.send_message(
            chat_id=settings.staff_chat_id,
            message_thread_id=topic_id,
            text=plain,
            reply_markup=staff_order_keyboard(order.id),
        )
        return card_message.message_id
    except TelegramBadRequest as exc:
        logger.error("Plain order card send failed for #%s: %s", order.id, exc)
        return None


async def create_order_topic(
    bot: Bot,
    db: Database,
    settings: Settings,
    order: Order,
) -> Order:
    topic_name = f"#{order.id} | {order.address_short}"
    if is_breakfast_hours(settings):
        topic_name = f"#{order.id} | {order.address_short} | 🥐 завтрак"

    forum_topic = await bot.create_forum_topic(
        chat_id=settings.staff_chat_id,
        name=topic_name[:128],
    )
    topic_id = forum_topic.message_thread_id

    await db.update_order_topic(order.id, topic_id)

    staff_message_id = await _send_order_card(bot, settings, order, topic_id)
    if staff_message_id:
        await db.set_order_staff_message_id(order.id, staff_message_id)

    updated = await db.get_order(order.id)
    if updated is None:
        raise RuntimeError("Order not found after topic creation")
    if updated.topic_id is None:
        raise RuntimeError("Topic id was not saved")
    return updated


async def notify_responsible_staff(
    bot: Bot,
    settings: Settings,
    order: Order,
) -> None:
    if not settings.responsible_staff_id:
        return

    text = STAFF_NEW_ORDER_NOTIFICATION.format(
        order_id=order.id,
        address_short=order.address_short,
        guest_name=order.guest_name,
        phone=order.phone,
    )
    await bot.send_message(
        chat_id=settings.responsible_staff_id,
        text=text,
    )


async def update_order_card(
    bot: Bot,
    settings: Settings,
    order: Order,
) -> None:
    if not order.topic_id or not order.staff_message_id:
        return

    card_text = build_order_card_text(order)
    reply_markup = staff_order_card_markup(order)

    try:
        await bot.edit_message_text(
            chat_id=settings.staff_chat_id,
            message_id=order.staff_message_id,
            text=card_text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as exc:
        err = str(exc).lower()
        if "message is not modified" not in err:
            logger.warning("Could not edit order card #%s: %s", order.id, exc)
