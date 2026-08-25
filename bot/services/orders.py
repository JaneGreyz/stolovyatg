from aiogram import Bot
from aiogram.types import FSInputFile, Message

from bot.config import Settings
from bot.database.db import Database
from bot.database.models import Order
from bot.services.topics import create_order_topic, notify_responsible_staff, update_order_card
from bot.texts import GUEST_STATUS_NOTIFICATIONS, STATUS_LABELS


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

    return order
