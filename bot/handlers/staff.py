import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.database.db import Database
from bot.database.models import ACTIVE_STATUSES, STATUS_IN_DELIVERY
from bot.keyboards.inline import staff_order_card_markup
from bot.services.orders import change_order_status
from bot.services.topics import build_order_card_text, update_order_card
from bot.texts import STATUS_LABELS
from bot.utils import parse_amount

logger = logging.getLogger(__name__)

STAFF_STATUS_ACTIONS = {
    "accepted": "accepted",
    "in_delivery": "in_delivery",
    "completed": "completed",
    "complete": "completed",
    "cancel": "cancelled",
}


def create_staff_router(settings: Settings) -> Router:
    router = Router(name="staff")
    staff_chat = settings.staff_chat_id

    @router.callback_query(
        F.data.startswith("staff:"),
        F.message.chat.id == staff_chat,
    )
    async def handle_staff_order_action(
        callback: CallbackQuery,
        bot: Bot,
        db: Database,
    ) -> None:
        if not callback.data or not callback.message:
            return

        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer("Ошибка", show_alert=True)
            return

        action = parts[1]
        order_id = int(parts[2])

        new_status = STAFF_STATUS_ACTIONS.get(action)
        if not new_status:
            await callback.answer("Неизвестное действие", show_alert=True)
            return

        order = await db.get_order(order_id)
        if not order:
            await callback.answer("Заказ не найден", show_alert=True)
            return

        if order.status in ("completed", "cancelled"):
            await callback.answer("Заказ уже закрыт", show_alert=True)
            return

        if order.status == new_status:
            await callback.answer(STATUS_LABELS.get(new_status, new_status))
            return

        if new_status == "completed" and order.status != STATUS_IN_DELIVERY:
            await callback.answer(
                "Сначала отметьте заказ «В доставке»",
                show_alert=True,
            )
            return

        order = await change_order_status(bot, db, settings, order, new_status)

        status_label = STATUS_LABELS.get(new_status, new_status)
        await callback.answer(status_label)

        try:
            await callback.message.edit_text(
                build_order_card_text(order),
                parse_mode="HTML",
                reply_markup=staff_order_card_markup(order),
            )
        except Exception:
            logger.exception("Failed to update card after status change #%s", order.id)

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

        if order.status not in ACTIVE_STATUSES:
            return

        try:
            await message.copy_to(chat_id=order.guest_id)
        except Exception:
            await message.forward(chat_id=order.guest_id)

    return router
