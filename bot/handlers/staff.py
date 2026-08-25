from aiogram import Bot, F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.database.db import Database
from bot.services.topics import update_order_card


def create_staff_router(settings: Settings) -> Router:
    router = Router(name="staff")
    staff_chat = settings.staff_chat_id

    @router.message(F.chat.id == staff_chat, F.message_thread_id)
    async def handle_staff_topic_message(
        message: Message,
        bot: Bot,
        db: Database,
    ) -> None:
        if message.from_user and message.from_user.is_bot:
            return

        order = await db.get_order_by_topic(message.message_thread_id)
        if not order:
            return

        if message.message_id == order.staff_message_id:
            return

        # Менеджер указывает сумму заказа числом в теме (для среднего чека)
        if message.text and message.text.strip().isdigit():
            amount = int(message.text.strip())
            if 50 <= amount <= 100000:
                await db.update_order_amount(order.id, amount)
                order = await db.get_order(order.id)
                if order:
                    await update_order_card(bot, settings, order)
                    await message.reply(f"✅ Сумма заказа сохранена: {amount} ₽")
                return

        try:
            await message.copy_to(chat_id=order.guest_id)
        except Exception:
            await message.forward(chat_id=order.guest_id)

    return router
