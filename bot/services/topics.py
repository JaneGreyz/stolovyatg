from aiogram import Bot
from aiogram.types import Message

from bot.config import Settings
from bot.database.db import Database
from bot.database.models import Order
from bot.keyboards.inline import order_status_keyboard
from bot.texts import STAFF_NEW_ORDER_NOTIFICATION, STAFF_ORDER_CARD


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
        username_line = f"🔗 <b>Username:</b> @{order.guest_username}\n"

    order_text = order.order_text or "— (ещё не указан)"
    amount_line = f"{order.order_amount} ₽" if order.order_amount else "— (укажите числом в теме)"

    return STAFF_ORDER_CARD.format(
        order_id=order.id,
        address=order.address,
        clarification=order.address_clarification,
        phone=order.phone,
        guest_name=order.guest_name,
        guest_id=order.guest_id,
        username_line=username_line,
        amount_line=amount_line,
        order_text=order_text,
    )


async def create_order_topic(
    bot: Bot,
    db: Database,
    settings: Settings,
    order: Order,
) -> Order:
    topic_name = f"#{order.id} | {order.address_short}"
    forum_topic = await bot.create_forum_topic(
        chat_id=settings.staff_chat_id,
        name=topic_name,
    )

    card_text = build_order_card_text(order)
    card_message = await bot.send_message(
        chat_id=settings.staff_chat_id,
        message_thread_id=forum_topic.message_thread_id,
        text=card_text,
        reply_markup=order_status_keyboard(order.id),
        parse_mode="HTML",
    )

    await db.update_order_topic(
        order_id=order.id,
        topic_id=forum_topic.message_thread_id,
        staff_message_id=card_message.message_id,
    )

    updated = await db.get_order(order.id)
    if updated is None:
        raise RuntimeError("Order not found after topic creation")
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

    await bot.edit_message_text(
        chat_id=settings.staff_chat_id,
        message_id=order.staff_message_id,
        message_thread_id=order.topic_id,
        text=build_order_card_text(order),
        reply_markup=order_status_keyboard(order.id),
        parse_mode="HTML",
    )
