from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from datetime import datetime

from bot.config import Settings
from bot.database.db import Database
from bot.keyboards.inline import admin_addresses_keyboard, admin_orders_filter_keyboard
from bot.services.menu import save_channel_menu_message
from bot.services.menu_source import extract_forwarded_post
from bot.services.orders import cancel_guest_active_order
from bot.services.sheets_menu import parse_sheet_url, save_sheet_menu
from bot.utils import parse_telegram_post_link
from bot.texts import (
    ADMIN_ADDRESSES_HEADER,
    ADMIN_NO_ACCESS,
    ADMIN_NO_ORDERS,
    ADMIN_ORDERS_HEADER,
    ADMIN_PANEL,
    ADMIN_STATS_AVG,
    ADMIN_STATS_BY_ADDRESS,
    ADMIN_STATS_BY_STATUS,
    ADMIN_STATS_HEADER,
    ADMIN_STATS_TOTAL,
    STATUS_FILTER_LABELS,
    STATUS_LABELS,
)

logger = logging.getLogger(__name__)


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
        ]

        if stats.get("avg_amount"):
            lines.append(
                ADMIN_STATS_AVG.format(
                    avg=int(stats["avg_amount"]),
                    count=stats["avg_count"],
                )
            )

        lines.append(ADMIN_STATS_BY_STATUS)

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

    @router.message(Command("cancelorder"))
    async def cmd_cancelorder(message: Message, db: Database, settings: Settings) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            await message.answer(ADMIN_NO_ACCESS)
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip().isdigit():
            order = await db.get_order(int(parts[1].strip()))
            if not order:
                await message.answer("Заказ не найден.")
                return
            await db.update_order_status(order.id, "cancelled")
            await message.answer(f"✅ Заказ #{order.id} отменён.")
            return

        order = await cancel_guest_active_order(
            message.bot,
            db,
            settings,
            message.from_user.id,
        )
        if not order:
            await message.answer("Активных заказов нет.")
            return
        await message.answer(f"✅ Ваш активный заказ #{order.id} отменён.")

    @router.message(Command("setmenu"))
    async def cmd_setmenu(message: Message, db: Database) -> None:
        if not message.from_user:
            return

        if not is_admin(message.from_user.id):
            await message.answer(
                f"{ADMIN_NO_ACCESS}\n\n"
                f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n"
                "Добавьте его в ADMIN_IDS на сервере.",
                parse_mode="HTML",
            )
            return

        try:
            parts = (message.text or "").split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else ""

            if arg and "docs.google.com/spreadsheets" in arg:
                try:
                    sheet_id, gid = parse_sheet_url(arg)
                except ValueError as exc:
                    await message.answer(str(exc))
                    return
                if gid is None:
                    await message.answer(
                        "В ссылке не указана вкладка (gid). "
                        "Откройте нужный лист и скопируйте ссылку из адресной строки."
                    )
                    return
                await save_sheet_menu(db, sheet_id, gid)
                await message.answer("✅ Постоянное меню (Google Sheets) сохранено.")
                return

            if arg and "t.me/" in arg:
                parsed = parse_telegram_post_link(arg)
                if not parsed:
                    await message.answer(
                        "Не удалось разобрать ссылку.\n"
                        "Пример: /setmenu https://t.me/s_mestoest/123"
                    )
                    return
                chat_id, msg_id = parsed
                await save_channel_menu_message(db, msg_id, chat_id)
                await message.answer(
                    f"✅ Меню дня сохранено.\nПост: {msg_id}"
                )
                return

            if message.reply_to_message:
                source = extract_forwarded_post(message.reply_to_message)
                if not source:
                    await message.answer(
                        "Не вижу, откуда переслан пост.\n\n"
                        "Самый простой способ:\n"
                        "1. Откройте пост с меню в канале\n"
                        "2. Скопируйте ссылку на пост\n"
                        "3. Отправьте боту:\n"
                        "/setmenu https://t.me/s_mestoest/123"
                    )
                    return
                chat_id, msg_id = source
                await save_channel_menu_message(db, msg_id, chat_id)
                await message.answer(
                    f"✅ Меню дня сохранено.\nПост: {msg_id}"
                )
                return

            await message.answer(
                "Как сохранить меню дня:\n\n"
                "<b>Способ 1 (проще всего)</b>\n"
                "Скопируйте ссылку на пост в канале и отправьте:\n"
                "<code>/setmenu https://t.me/s_mestoest/123</code>\n\n"
                "<b>Способ 2</b>\n"
                "Перешлите пост боту и ответьте на него: /setmenu\n\n"
                "<b>Постоянное меню (Google Sheets)</b>\n"
                "<code>/setmenu https://docs.google.com/spreadsheets/d/.../edit?gid=...</code>",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("setmenu failed for user %s", message.from_user.id)
            await message.answer(
                "Ошибка при сохранении. Попробуйте ссылку на пост:\n"
                "/setmenu https://t.me/s_mestoest/123"
            )

    @router.callback_query(F.data == "admin:back")
    async def admin_back(callback: CallbackQuery) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            await callback.answer(ADMIN_NO_ACCESS, show_alert=True)
            return
        if callback.message:
            await callback.message.edit_text(ADMIN_PANEL, parse_mode="HTML")
        await callback.answer()

    return router
