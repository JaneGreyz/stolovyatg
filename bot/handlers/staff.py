import logging

from aiogram import Bot, F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.database.db import Database
from bot.services.topics import update_order_card
from bot.utils import parse_amount

logger = logging.getLogger(__name__)


def create_staff_router(settings: Settings) -> Router:
    router = Router(name="staff")
    staff_chat = settings.staff_chat_id

    @router.message(F.chat.id == staff_chat, F.message_thread_id.as_("topic_id"))
    async def handle_staff_topic_message(
        message: Message,
        bot: Bot,
        db: Database,
        topic_id: int,
    ) -> None:
        if message.from_user and message.from_user.is_bot:
            return

        order = await db.get_order_by_topic(topic_id)
        if not order:
            return

        if message.message_id == order.staff_message_id:
            return

        amount = parse_amount(message.text or "")
        if amount is not None and 1 <= amount <= 100000:
            await db.update_order_amount(order.id, amount)
            order = await db.get_order(order.id)
            if order:
                try:
                    await update_order_card(bot, settings, order)
                except Exception:
                    logger.exception("Failed to update card for order #%s", order.id)
                await message.reply(f"✅ Сумма заказа сохранена: {amount} ₽")
            return

        try:
            await message.copy_to(chat_id=order.guest_id)
        except Exception:
            await message.forward(chat_id=order.guest_id)

    return router
