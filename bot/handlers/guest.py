from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from datetime import datetime

from bot.config import Settings
from bot.database.db import Database
from bot.database.models import Order
from bot.filters.guest_order import (
    ActiveOrderWithTopicFilter,
    NotMenuButtonFilter,
    PendingOrderFilter,
)
from bot.keyboards.inline import (
    addresses_keyboard,
    cancel_active_order_keyboard,
    cancel_keyboard,
    guest_main_keyboard,
    guest_order_keyboard,
    review_rating_keyboard,
    review_skip_keyboard,
)
from bot.services.menu import send_menus_to_guest
from bot.services.orders import finalize_order, send_review_to_staff
from bot.services.working_hours import format_work_hours, get_tz, is_working_hours
from bot.states.order import OrderStates, ReviewStates
from bot.texts import (
    BUTTON_CONTACT_MANAGER,
    BUTTON_LEAVE_REVIEW,
    BUTTON_MAKE_ORDER,
    BUTTON_QA,
    BUTTON_START,
    CHOOSE_ADDRESS,
    CONTACT_MANAGER,
    CONTACT_MANAGER_NO_ORDER,
    ENTER_ADDRESS_CLARIFICATION,
    ENTER_ORDER_TEXT,
    ENTER_PHONE,
    INVALID_PHONE,
    ORDER_ACCEPTED,
    ORDER_CANCELLED_ACTIVE,
    ORDER_CANCELLED_BY_GUEST,
    ORDER_IN_PROGRESS,
    OUTSIDE_WORKING_HOURS,
    OUTSIDE_WORKING_HOURS_WEEKEND,
    QA_MESSAGE,
    REVIEW_NO_ORDERS,
    REVIEW_REQUEST,
    REVIEW_SAVED,
    REVIEW_THANKS,
    WELCOME,
)
from bot.utils import is_valid_phone, normalize_phone

logger = logging.getLogger(__name__)
router = Router(name="guest")

MENU_BUTTONS = (
    BUTTON_START,
    BUTTON_MAKE_ORDER,
    BUTTON_CONTACT_MANAGER,
    BUTTON_QA,
    BUTTON_LEAVE_REVIEW,
)


def _welcome_extra(settings: Settings) -> str:
    if is_working_hours(settings):
        return ""
    schedule = format_work_hours(settings)
    tz = get_tz(settings)
    if settings.work_weekdays_only and datetime.now(tz).weekday() >= 5:
        return f"\n\n⏰ {OUTSIDE_WORKING_HOURS_WEEKEND.format(schedule=schedule)}"
    return f"\n\n⏰ {OUTSIDE_WORKING_HOURS.format(schedule=schedule)}"


async def show_welcome(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    logger.info("Start from user %s", message.from_user.id if message.from_user else "?")
    await message.answer(
        WELCOME + _welcome_extra(settings),
        reply_markup=guest_main_keyboard(),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings: Settings) -> None:
    await show_welcome(message, state, settings)


@router.message(F.text == BUTTON_START)
async def btn_start(message: Message, state: FSMContext, settings: Settings) -> None:
    await show_welcome(message, state, settings)


@router.message(F.text == BUTTON_MAKE_ORDER)
async def start_order(
    message: Message,
    state: FSMContext,
    db: Database,
) -> None:
    if not message.from_user:
        return

    active = await db.get_active_order_for_guest(message.from_user.id)
    if active:
        if active.topic_id:
            await message.answer(
                ORDER_IN_PROGRESS.format(order_id=active.id),
                reply_markup=cancel_active_order_keyboard(),
            )
            return
        await db.update_order_status(active.id, "cancelled")

    addresses = await db.get_active_addresses()
    if not addresses:
        await message.answer(
            "К сожалению, доставка временно недоступна.",
            reply_markup=guest_main_keyboard(),
        )
        return

    await state.set_state(OrderStates.choosing_address)
    await message.answer(
        CHOOSE_ADDRESS,
        reply_markup=addresses_keyboard(addresses),
    )


@router.callback_query(F.data.startswith("addr:"))
async def choose_address(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    if not callback.data or not callback.message:
        return

    address_id = int(callback.data.split(":")[1])
    address = await db.get_address_by_id(address_id)
    if not address or not address.is_active:
        await callback.answer("Адрес недоступен", show_alert=True)
        return

    await state.update_data(
        address_id=address.id,
        address=address.full_name,
        address_short=address.short_name,
    )
    await state.set_state(OrderStates.address_clarification)
    await callback.message.edit_text(
        f"📍 {address.full_name}\n\n{ENTER_ADDRESS_CLARIFICATION}",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(F.text == BUTTON_QA)
async def show_qa(message: Message, settings: Settings) -> None:
    channel = settings.qa_channel_url
    if not channel.startswith("http"):
        channel = f"https://t.me/{channel.lstrip('@')}"
    await message.answer(
        QA_MESSAGE.format(channel=channel),
        disable_web_page_preview=True,
    )


@router.message(F.text == BUTTON_LEAVE_REVIEW)
async def leave_review_button(
    message: Message,
    db: Database,
) -> None:
    if not message.from_user:
        return

    order = await db.get_last_completed_order_without_review(message.from_user.id)
    if not order:
        await message.answer(REVIEW_NO_ORDERS, reply_markup=guest_main_keyboard())
        return

    await message.answer(
        REVIEW_REQUEST.format(order_id=order.id),
        reply_markup=review_rating_keyboard(order.id),
    )


@router.callback_query(F.data.startswith("review:"))
async def process_review_rating(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not callback.data or not callback.from_user:
        return

    if callback.data == "review:skip":
        data = await state.get_data()
        order_id = data.get("review_order_id")
        rating = data.get("review_rating")
        if order_id and rating and callback.from_user:
            await db.save_review(order_id, callback.from_user.id, rating)
            order = await db.get_order(order_id)
            if order:
                await send_review_to_staff(callback.bot, settings, order, rating, "")
        await state.clear()
        if callback.message:
            await callback.message.edit_text(REVIEW_SAVED)
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Ошибка", show_alert=True)
        return

    order_id = int(parts[1])
    rating = int(parts[2])
    order = await db.get_order(order_id)
    if not order or order.guest_id != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await state.set_state(ReviewStates.waiting_comment)
    await state.update_data(review_order_id=order_id, review_rating=rating)

    await callback.message.edit_text(REVIEW_THANKS, reply_markup=review_skip_keyboard())
    await callback.answer()


@router.message(ReviewStates.waiting_comment, F.text)
async def process_review_comment(
    message: Message,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not message.from_user or not message.text:
        return

    data = await state.get_data()
    order_id = data.get("review_order_id")
    rating = data.get("review_rating")
    if not order_id or not rating:
        await state.clear()
        return

    comment = message.text.strip()
    await db.save_review(order_id, message.from_user.id, rating, comment)

    order = await db.get_order(order_id)
    if order:
        await send_review_to_staff(message.bot, settings, order, rating, comment)

    await state.clear()
    await message.answer(REVIEW_SAVED, reply_markup=guest_main_keyboard())


@router.message(OrderStates.address_clarification, F.text)
async def process_clarification(message: Message, state: FSMContext) -> None:
    if message.text in MENU_BUTTONS:
        return
    await state.update_data(address_clarification=message.text.strip())
    await state.set_state(OrderStates.phone)
    await message.answer(
        ENTER_PHONE,
        reply_markup=guest_order_keyboard(),
    )


@router.message(OrderStates.phone, F.text)
async def process_phone(
    message: Message,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not message.from_user or not message.text:
        return

    if message.text in MENU_BUTTONS:
        return

    if not is_valid_phone(message.text):
        await message.answer(INVALID_PHONE, reply_markup=guest_order_keyboard())
        return

    phone = normalize_phone(message.text)
    data = await state.get_data()

    order = await db.create_order(
        guest_id=message.from_user.id,
        guest_username=message.from_user.username,
        guest_name=message.from_user.full_name or message.from_user.first_name or "Гость",
        address=data["address"],
        address_short=data["address_short"],
        address_clarification=data.get("address_clarification", ""),
        phone=phone,
    )

    await state.update_data(order_id=order.id)
    await state.set_state(OrderStates.order_text)

    await send_menus_to_guest(message.bot, db, settings, message.chat.id)
    await message.answer(
        ENTER_ORDER_TEXT,
        reply_markup=guest_order_keyboard(),
    )


async def _resolve_pending_order(
    message: Message,
    state: FSMContext,
    db: Database,
) -> Order | None:
    if not message.from_user:
        return None

    data = await state.get_data()
    order_id = data.get("order_id")
    if order_id:
        order = await db.get_order(order_id)
        if order and order.topic_id is None:
            return order

    order = await db.get_pending_order_for_guest(message.from_user.id)
    if order:
        await state.update_data(order_id=order.id)
        await state.set_state(OrderStates.order_text)
    return order


@router.message(
    F.chat.type == "private",
    NotMenuButtonFilter(),
    or_f(StateFilter(OrderStates.order_text), PendingOrderFilter()),
)
async def process_order_message(
    message: Message,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not message.from_user:
        return

    order = await _resolve_pending_order(message, state, db)
    if not order:
        await state.clear()
        await message.answer(
            "Ошибка оформления. Начните заново.",
            reply_markup=guest_main_keyboard(),
        )
        return

    order_text = (message.text or message.caption or "").strip()
    if not order_text:
        await message.answer(
            ENTER_ORDER_TEXT,
            reply_markup=guest_order_keyboard(),
        )
        return

    try:
        order = await finalize_order(message.bot, db, settings, order, order_text)
    except Exception:
        logger.exception("Failed to finalize order %s", order.id)
        await message.answer(
            "Не удалось передать заказ менеджеру. "
            "Попробуйте ещё раз или нажмите «Связаться с менеджером».",
            reply_markup=guest_order_keyboard(),
        )
        return

    if order.topic_id:
        try:
            await message.copy_to(
                chat_id=settings.staff_chat_id,
                message_thread_id=order.topic_id,
            )
        except Exception:
            await message.forward(
                chat_id=settings.staff_chat_id,
                message_thread_id=order.topic_id,
            )
    else:
        logger.error("Order %s finalized without topic_id", order.id)
        await message.answer(
            "Заказ сохранён, но не удалось создать тему для менеджера. "
            "Нажмите «Связаться с менеджером».",
            reply_markup=guest_order_keyboard(),
        )
        return

    await state.clear()
    await message.answer(
        ORDER_ACCEPTED.format(order_id=order.id),
        reply_markup=guest_main_keyboard(),
    )


@router.callback_query(F.data == "guest:cancel_active")
async def cancel_active_order(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not callback.from_user:
        return

    order = await db.get_active_order_for_guest(callback.from_user.id)
    if not order:
        if callback.message:
            await callback.message.edit_text("Активных заказов нет.")
        await callback.answer()
        return

    await db.update_order_status(order.id, "cancelled")
    await state.clear()

    if order.topic_id:
        try:
            await callback.bot.send_message(
                chat_id=settings.staff_chat_id,
                message_thread_id=order.topic_id,
                text=f"❌ Гость отменил заказ #{order.id}",
            )
        except Exception:
            logger.exception("Failed to notify staff about cancelled order #%s", order.id)

    if callback.message:
        await callback.message.edit_text(
            ORDER_CANCELLED_ACTIVE.format(order_id=order.id)
        )
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="Нажмите «Сделать заказ», чтобы оформить новый.",
            reply_markup=guest_main_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "order:cancel")
async def cancel_order(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    if order_id:
        await db.update_order_status(order_id, "cancelled")

    await state.clear()
    if callback.message:
        await callback.message.edit_text(ORDER_CANCELLED_BY_GUEST)
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="Вы на главном экране.",
            reply_markup=guest_main_keyboard(),
        )
    await callback.answer()


@router.message(F.text == BUTTON_CONTACT_MANAGER)
async def contact_manager(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if not message.from_user:
        return

    order = await db.get_active_order_for_guest(message.from_user.id)
    if order and order.topic_id:
        header = f"📞 Гость просит связаться (заказ #{order.id}):"
        await message.bot.send_message(
            chat_id=settings.staff_chat_id,
            message_thread_id=order.topic_id,
            text=header,
        )
        await message.answer(CONTACT_MANAGER, reply_markup=guest_main_keyboard())
        return

    if settings.responsible_staff_id:
        await message.bot.send_message(
            chat_id=settings.responsible_staff_id,
            text=(
                f"📞 Гость просит связаться\n"
                f"👤 {message.from_user.full_name or message.from_user.first_name}\n"
                f"🆔 {message.from_user.id}"
                + (f"\n🔗 @{message.from_user.username}" if message.from_user.username else "")
            ),
        )
    await message.answer(CONTACT_MANAGER_NO_ORDER, reply_markup=guest_main_keyboard())


@router.message(
    F.chat.type == "private",
    StateFilter(None),
    NotMenuButtonFilter(),
    ActiveOrderWithTopicFilter(),
)
async def forward_guest_message(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if not message.from_user:
        return

    order = await db.get_active_order_for_guest(message.from_user.id)
    if not order or not order.topic_id:
        return

    try:
        await message.copy_to(
            chat_id=settings.staff_chat_id,
            message_thread_id=order.topic_id,
        )
    except Exception:
        await message.forward(
            chat_id=settings.staff_chat_id,
            message_thread_id=order.topic_id,
        )
