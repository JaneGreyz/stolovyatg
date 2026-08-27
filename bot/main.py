import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from bot.config import load_settings, resolve_settings
from bot.database.db import Database
from bot.handlers.admin import create_admin_router
from bot.handlers.guest import router as guest_router
from bot.handlers.menu import create_menu_router
from bot.handlers.staff import create_staff_router
from bot.middlewares.dependencies import DependencyMiddleware
from bot.middlewares.errors import ErrorHandlerMiddleware
from bot.middlewares.working_hours import WorkingHoursMiddleware
from bot.services.menu import sync_channel_menu_from_env
from bot.services.reminders import reminder_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        request_timeout=120,
    )

    try:
        settings = await resolve_settings(bot)
    except Exception as exc:
        logger.warning("Menu chat resolve skipped: %s", exc)

    logger.info("Starting bot...")
    logger.info("Staff chat: %s", settings.staff_chat_id)
    logger.info("Menu chat id: %s", settings.menu_chat_id)
    if settings.daily_menu_sheet_id:
        logger.info(
            "Permanent menu sheet: %s gid=%s",
            settings.daily_menu_sheet_id,
            settings.daily_menu_gid,
        )

    dp = Dispatcher(storage=MemoryStorage())
    db = Database(settings.database_path)
    await db.connect()
    await sync_channel_menu_from_env(db, settings)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception("Update error: %s", event.exception)

    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    dp.message.middleware(DependencyMiddleware(db, settings))
    dp.callback_query.middleware(DependencyMiddleware(db, settings))
    dp.channel_post.middleware(DependencyMiddleware(db, settings))
    dp.message.middleware(WorkingHoursMiddleware(settings))
    dp.callback_query.middleware(WorkingHoursMiddleware(settings))

    dp.include_router(create_admin_router(settings))
    dp.include_router(guest_router)
    dp.include_router(create_menu_router(settings))
    dp.include_router(create_staff_router(settings))

    stop_event = asyncio.Event()
    reminder_task = asyncio.create_task(
        reminder_loop(bot, db, settings, stop_event)
    )

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared, polling started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except KeyError as exc:
        logger.error("Missing required environment variable: %s", exc)
        raise SystemExit(1) from exc
    except ValueError as exc:
        logger.error("Invalid environment variable format: %s", exc)
        raise SystemExit(1) from exc
    except Exception:
        logger.exception("Bot failed to start")
        raise
