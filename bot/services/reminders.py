import asyncio
import logging

from aiogram import Bot

from bot.config import Settings
from bot.database.db import Database
from bot.services.working_hours import is_working_hours
from bot.texts import STAFF_ORDER_REMINDER_DM, STAFF_ORDER_REMINDER_TOPIC

logger = logging.getLogger(__name__)


async def check_and_send_reminders(
    bot: Bot,
    db: Database,
    settings: Settings,
) -> None:
    if not is_working_hours(settings):
        return

    orders = await db.get_orders_needing_reminder(settings.reminder_minutes)
    for order in orders:
        try:
            if order.topic_id:
                await bot.send_message(
                    chat_id=settings.staff_chat_id,
                    message_thread_id=order.topic_id,
                    text=STAFF_ORDER_REMINDER_TOPIC.format(
                        order_id=order.id,
                        minutes=settings.reminder_minutes,
                        address_short=order.address_short,
                        guest_name=order.guest_name,
                        phone=order.phone,
                    ),
                )

            if settings.responsible_staff_id:
                await bot.send_message(
                    chat_id=settings.responsible_staff_id,
                    text=STAFF_ORDER_REMINDER_DM.format(
                        order_id=order.id,
                        minutes=settings.reminder_minutes,
                        address_short=order.address_short,
                        guest_name=order.guest_name,
                        phone=order.phone,
                    ),
                )

            await db.mark_manager_reminder_sent(order.id)
            logger.info("Reminder sent for order #%s", order.id)
        except Exception:
            logger.exception("Failed to send reminder for order #%s", order.id)


async def reminder_loop(
    bot: Bot,
    db: Database,
    settings: Settings,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await check_and_send_reminders(bot, db, settings)
        except Exception:
            logger.exception("Reminder loop error")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.reminder_check_interval,
            )
        except asyncio.TimeoutError:
            continue
