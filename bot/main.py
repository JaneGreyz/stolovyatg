import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_settings, resolve_settings
from bot.database.db import Database
from bot.handlers.admin import create_admin_router
from bot.handlers.guest import router as guest_router
from bot.handlers.menu import create_menu_router
from bot.handlers.staff import create_staff_router
from bot.middlewares.dependencies import DependencyMiddleware
from bot.middlewares.errors import ErrorHandlerMiddleware
from bot.middlewares.working_hours import WorkingHoursMiddleware
from bot.services.reminders import reminder_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=load_settings().bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        request_timeout=120,
    )
    settings = await resolve_settings(bot)
    logger.info("Menu chat resolved: %s", settings.menu_chat_id)

    dp = Dispatcher(storage=MemoryStorage())
    db = Database(settings.database_path)

    await db.connect()

    dp["db"] = db
    dp["settings"] = settings

    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    dp.message.middleware(DependencyMiddleware(db, settings))
    dp.callback_query.middleware(DependencyMiddleware(db, settings))
    dp.channel_post.middleware(DependencyMiddleware(db, settings))

    dp.message.middleware(WorkingHoursMiddleware(settings))
    dp.callback_query.middleware(WorkingHoursMiddleware(settings))

    dp.include_router(create_menu_router(settings))
    dp.include_router(create_staff_router(settings))
    dp.include_router(create_admin_router(settings))
    dp.include_router(guest_router)

    stop_event = asyncio.Event()
    reminder_task = asyncio.create_task(
        reminder_loop(bot, db, settings, stop_event)
    )

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared, starting polling")
        logger.info("Bot started (reminder every %ss)", settings.reminder_check_interval)
        await dp.start_polling(bot)
    finally:
        stop_event.set()
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
