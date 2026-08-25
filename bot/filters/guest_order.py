from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.database.db import Database
from bot.states.order import OrderStates
from bot.texts import (
    BUTTON_CONTACT_MANAGER,
    BUTTON_LEAVE_REVIEW,
    BUTTON_MAKE_ORDER,
    BUTTON_QA,
    BUTTON_START,
)

MENU_BUTTONS = frozenset(
    {
        BUTTON_START,
        BUTTON_MAKE_ORDER,
        BUTTON_CONTACT_MANAGER,
        BUTTON_QA,
        BUTTON_LEAVE_REVIEW,
    }
)

IN_PROGRESS_STATES = frozenset(
    {
        OrderStates.choosing_address.state,
        OrderStates.address_clarification.state,
        OrderStates.phone.state,
    }
)


class NotMenuButtonFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.text and message.text in MENU_BUTTONS:
            return False
        return True


class PendingOrderFilter(BaseFilter):
    """Guest has an active order waiting for the first order message (no topic yet)."""

    async def __call__(
        self,
        message: Message,
        db: Database,
        state: FSMContext,
    ) -> bool:
        if not message.from_user:
            return False
        current = await state.get_state()
        if current in IN_PROGRESS_STATES:
            return False
        order = await db.get_pending_order_for_guest(message.from_user.id)
        return order is not None


class ActiveOrderWithTopicFilter(BaseFilter):
    """Guest has an active order with a staff topic — forward follow-up messages."""

    async def __call__(self, message: Message, db: Database) -> bool:
        if not message.from_user:
            return False
        order = await db.get_active_order_for_guest(message.from_user.id)
        return order is not None and order.topic_id is not None
