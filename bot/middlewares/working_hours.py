from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from typing import Any, Awaitable, Callable
from datetime import datetime

from bot.config import Settings
from bot.services.working_hours import format_work_hours, get_tz, is_working_hours
from bot.texts import (
    BUTTON_MAKE_ORDER,
    OUTSIDE_WORKING_HOURS,
    OUTSIDE_WORKING_HOURS_WEEKEND,
)


class WorkingHoursMiddleware(BaseMiddleware):
    """Block order-related actions outside working hours."""

    ORDER_CALLBACKS = ("order:", "addr:")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _outside_message(self) -> str:
        schedule = format_work_hours(self.settings)
        tz = get_tz(self.settings)
        now = datetime.now(tz)

        if self.settings.work_weekdays_only and now.weekday() >= 5:
            return OUTSIDE_WORKING_HOURS_WEEKEND.format(schedule=schedule)

        return OUTSIDE_WORKING_HOURS.format(schedule=schedule)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if is_working_hours(self.settings):
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            if event.data and (
                event.data.startswith(self.ORDER_CALLBACKS)
            ):
                await event.answer(self._outside_message(), show_alert=True)
                return None

        if isinstance(event, Message):
            if event.text == BUTTON_MAKE_ORDER:
                await event.answer(self._outside_message())
                return None

        return await handler(event, data)
