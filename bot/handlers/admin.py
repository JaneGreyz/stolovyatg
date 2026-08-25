from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from datetime import datetime

from bot.config import Settings
from bot.database.db import Database
from bot.keyboards.inline import admin_addresses_keyboard, admin_orders_filter_keyboard
from bot.services.menu import save_menu_message
from bot.texts import (
    ADMIN_ADDRESSES_HEADER,
    ADMIN_NO_ACCESS,
    ADMIN_NO_ORDERS,
    ADMIN_ORDERS_HEADER,
    ADMIN_PANEL,
    ADMIN_STATS_BY_ADDRESS,
    ADMIN_STATS_BY_STATUS,
    ADMIN_STATS_HEADER,
    ADMIN_STATS_TOTAL,
    STATUS_FILTER_LABELS,
    STATUS_LABELS,
)


def create_admin_router(settings: Settings) -> Router:
    router = Router(name="admin")
    admin_ids = settings.admin_ids

    def is_admin(user_id: int | None) -> bool:
        return user_id is not None and user_id in admin_ids

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            await message.answer(ADMIN_NO_ACCESS)
            return
        await message.answer(ADMIN_PANEL, parse_mode="HTML")

    @router.message(Command("stats"))
    async def cmd_stats(message: Message, db: Database) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            await message.answer(ADMIN_NO_ACCESS)
            return

        stats = await db.get_today_stats()
        today = datetime.now().strftime("%d.%m.%Y")

        lines = [
            ADMIN_STATS_HEADER.format(date=today),
            ADMIN_STATS_TOTAL.format(total=stats["total"]),
            ADMIN_STATS_BY_STATUS,
        ]

        for status, count in stats["by_status"].items():
            label = STATUS_LABELS.get(status, status)
            lines.append(f"  • {label}: {count}")

        if stats["by_address"]:
            lines.append(ADMIN_STATS_BY_ADDRESS)
            for address, count in stats["by_address"].items():
                lines.append(f"  • {address}: {count}")

        await message.answer("\n".join(lines), parse_mode="HTML")

    @router.message(Command("orders"))
    async def cmd_orders(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            await message.answer(ADMIN_NO_ACCESS)
            return

        await message.answer(
            "Выберите статус для фильтрации:",
            reply_markup=admin_orders_filter_keyboard(),
        )

    @router.callback_query(F.data.startswith("admin:filter:"))
    async def filter_orders(callback: CallbackQuery, db: Database) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            await callback.answer(ADMIN_NO_ACCESS, show_alert=True)
            return

        if not callback.data or not callback.message:
            return

        status_key = callback.data.split(":")[2]
        status = None if status_key == "all" else status_key
        orders = await db.get_orders_by_status(status=status, limit=30)

        if not orders:
            await callback.message.edit_text(ADMIN_NO_ORDERS)
            await callback.answer()
            return

        status_label = STATUS_FILTER_LABELS.get(status_key, status_key)
        lines = [ADMIN_ORDERS_HEADER.format(status=status_label)]

        for order in orders:
            label = STATUS_LABELS.get(order.status, order.status)
            lines.append(
                f"#{order.id} | {order.address_short} | {label}\n"
                f"  👤 {order.guest_name} | 📞 {order.phone}"
            )

        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:4000] + "\n..."

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    @router.message(Command("addresses"))
    async def cmd_addresses(message: Message, db: Database) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            await message.answer(ADMIN_NO_ACCESS)
            return

        addresses = await db.get_all_addresses()
        await message.answer(
            ADMIN_ADDRESSES_HEADER + "Нажмите адрес, чтобы включить/выключить:",
            reply_markup=admin_addresses_keyboard(addresses),
            parse_mode="HTML",
        )

    @router.callback_query(F.data.startswith("admin:addr:"))
    async def toggle_address(callback: CallbackQuery, db: Database) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            await callback.answer(ADMIN_NO_ACCESS, show_alert=True)
            return

        if not callback.data or not callback.message:
            return

        address_id = int(callback.data.split(":")[2])
        result = await db.toggle_address(address_id)
        if result is None:
            await callback.answer("Адрес не найден", show_alert=True)
            return

        status_text = "включён" if result else "выключен"
        await callback.answer(f"Адрес {status_text}")

        addresses = await db.get_all_addresses()
        await callback.message.edit_reply_markup(
            reply_markup=admin_addresses_keyboard(addresses),
        )

    @router.message(Command("setmenu"))
    async def cmd_setmenu(message: Message, db: Database) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            await message.answer(ADMIN_NO_ACCESS)
            return

        if not message.reply_to_message:
            await message.answer(
                "Ответьте этой командой на сообщение с меню "
                "(перешлите его из чата меню)."
            )
            return

        replied = message.reply_to_message
        menu_message_id = replied.message_id

        if replied.forward_from_chat and replied.forward_from_chat.id == settings.menu_chat_id:
            menu_message_id = replied.forward_from_message_id or replied.message_id
        elif hasattr(replied, "forward_origin") and replied.forward_origin:
            origin = replied.forward_origin
            if getattr(origin, "chat", None) and origin.chat.id == settings.menu_chat_id:
                menu_message_id = origin.message_id

        await save_menu_message(db, menu_message_id)
        await message.answer("✅ Актуальное меню сохранено.")

    @router.callback_query(F.data == "admin:back")
    async def admin_back(callback: CallbackQuery) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            await callback.answer(ADMIN_NO_ACCESS, show_alert=True)
            return
        if callback.message:
            await callback.message.edit_text(ADMIN_PANEL, parse_mode="HTML")
        await callback.answer()

    return router
