from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.database.db import Database
from bot.keyboards.inline import order_status_keyboard
from bot.services.orders import change_order_status
from bot.services.topics import build_order_card_text
from bot.texts import STATUS_LABELS


def create_staff_router(settings: Settings) -> Router:
    router = Router(name="staff")
    staff_chat = settings.staff_chat_id

    @router.callback_query(
        F.data.startswith("status:"),
        F.message.chat.id == staff_chat,
    )
    async def handle_status_change(
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

        order_id = int(parts[1])
        new_status = parts[2]

        order = await db.get_order(order_id)
        if not order:
            await callback.answer("Заказ не найден", show_alert=True)
            return

        order = await change_order_status(bot, db, settings, order, new_status)
        status_label = STATUS_LABELS.get(new_status, new_status)
        await callback.answer(f"Статус: {status_label}")

        await callback.message.edit_text(
            build_order_card_text(order),
            reply_markup=order_status_keyboard(order.id),
            parse_mode="HTML",
        )

    @router.message(F.chat.id == staff_chat, F.message_thread_id)
    async def forward_staff_to_guest(
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

        try:
            await message.copy_to(chat_id=order.guest_id)
        except Exception:
            await message.forward(chat_id=order.guest_id)

    return router
