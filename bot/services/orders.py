from aiogram import Bot

from bot.config import Settings
from bot.database.db import Database
from bot.database.models import Order
from bot.keyboards.inline import review_rating_keyboard
from bot.services.topics import create_order_topic, notify_responsible_staff, update_order_card
from bot.texts import GUEST_STATUS_NOTIFICATIONS, REVIEW_REQUEST, STATUS_LABELS


async def finalize_order(
    bot: Bot,
    db: Database,
    settings: Settings,
    order: Order,
    order_text: str,
) -> Order:
    await db.update_order_text(order.id, order_text)
    order = await db.get_order(order.id)
    if order is None:
        raise RuntimeError("Order not found")

    if not order.topic_id:
        order = await create_order_topic(bot, db, settings, order)
        await notify_responsible_staff(bot, settings, order)

    return order


async def change_order_status(
    bot: Bot,
    db: Database,
    settings: Settings,
    order: Order,
    new_status: str,
) -> Order:
    await db.update_order_status(order.id, new_status)
    order = await db.get_order(order.id)
    if order is None:
        raise RuntimeError("Order not found")

    await update_order_card(bot, settings, order)

    status_emoji = STATUS_LABELS.get(new_status, new_status)
    new_topic_name = f"#{order.id} | {order.address_short} | {status_emoji}"
    if order.topic_id:
        try:
            await bot.edit_forum_topic(
                chat_id=settings.staff_chat_id,
                message_thread_id=order.topic_id,
                name=new_topic_name[:128],
            )
        except Exception:
            pass

    notification = GUEST_STATUS_NOTIFICATIONS.get(new_status)
    if notification:
        await bot.send_message(
            chat_id=order.guest_id,
            text=notification.format(order_id=order.id),
        )

    if new_status == "completed" and not await db.has_review(order.id):
        await bot.send_message(
            chat_id=order.guest_id,
            text=REVIEW_REQUEST.format(order_id=order.id),
            reply_markup=review_rating_keyboard(order.id),
        )

    return order


async def send_review_to_staff(
    bot: Bot,
    settings: Settings,
    order: Order,
    rating: int,
    comment: str,
) -> None:
    stars = "⭐" * rating
    text = (
        f"📝 Отзыв по заказу #{order.id}\n"
        f"Оценка: {stars} ({rating}/5)\n"
        f"👤 {order.guest_name}"
    )
    if comment:
        text += f"\n💬 {comment}"

    if order.topic_id:
        await bot.send_message(
            chat_id=settings.staff_chat_id,
            message_thread_id=order.topic_id,
            text=text,
        )
    elif settings.responsible_staff_id:
        await bot.send_message(chat_id=settings.responsible_staff_id, text=text)
