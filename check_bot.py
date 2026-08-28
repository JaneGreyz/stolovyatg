#!/usr/bin/env python3
"""Проверка: бот видит Telegram API и может отвечать."""

import asyncio
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_settings


async def check() -> None:
    settings = load_settings()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        me = await bot.get_me()
        wh = await bot.get_webhook_info()
        print(f"OK: bot @{me.username} (id={me.id})")
        print(f"Webhook URL: {wh.url or '(empty — polling ok)'}")
        if wh.url:
            print("WARNING: webhook is set! Polling will not receive messages.")
            print("Run: delete webhook before starting bot.")
    except Exception as exc:
        print(f"FAIL: cannot reach Telegram API — {exc}")
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(check())
