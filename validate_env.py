#!/usr/bin/env python3
"""Проверка переменных окружения и зависимостей перед запуском бота."""

from __future__ import annotations

import asyncio
import os
import sys


def check_imports() -> bool:
    ok = True
    for name, pip in (
        ("aiogram", "aiogram"),
        ("aiosqlite", "aiosqlite"),
        ("httpx", "httpx"),
        ("fitz", "pymupdf"),
    ):
        try:
            __import__(name)
            print(f"  OK  {pip}")
        except ImportError as exc:
            print(f"  FAIL {pip} — не установлен ({exc})")
            ok = False
    return ok


def check_env() -> bool:
    ok = True
    required = ("BOT_TOKEN", "STAFF_CHAT_ID")
    for key in required:
        value = os.getenv(key, "").strip()
        if not value:
            print(f"  FAIL {key} — пусто или не задано")
            ok = False
        else:
            masked = value[:8] + "..." if key == "BOT_TOKEN" else value
            print(f"  OK  {key}={masked}")

    int_fields = (
        "STAFF_CHAT_ID",
        "RESPONSIBLE_STAFF_ID",
        "DAILY_MENU_GID",
        "REMINDER_MINUTES",
        "REMINDER_CHECK_INTERVAL",
        "MIN_ORDER_AMOUNT",
    )
    for key in int_fields:
        raw = os.getenv(key, "").strip()
        if not raw:
            if key == "RESPONSIBLE_STAFF_ID":
                print(f"  OK  {key} — не задан (необязательно)")
            elif key in ("DAILY_MENU_GID",):
                print(f"  WARN {key} — не задан (меню из Sheets не будет работать)")
            continue
        try:
            int(raw)
            print(f"  OK  {key}={raw}")
        except ValueError:
            print(f"  FAIL {key}={raw!r} — должно быть числом")
            ok = False

    admin_raw = os.getenv("ADMIN_IDS", "").strip()
    if not admin_raw:
        print("  WARN ADMIN_IDS — пусто (админ-команды недоступны)")
    else:
        try:
            ids = [int(x.strip()) for x in admin_raw.split(",") if x.strip()]
            print(f"  OK  ADMIN_IDS={ids}")
        except ValueError:
            print(f"  FAIL ADMIN_IDS={admin_raw!r} — только числа через запятую")
            ok = False

    for key in ("WORK_START", "FULL_MENU_START", "WORK_END"):
        raw = os.getenv(key, "").strip()
        if not raw:
            print(f"  OK  {key} — по умолчанию")
            continue
        try:
            h, m = raw.split(":")
            int(h)
            int(m)
            print(f"  OK  {key}={raw}")
        except ValueError:
            print(f"  FAIL {key}={raw!r} — формат ЧЧ:ММ")
            ok = False

    sheet = os.getenv("DAILY_MENU_SHEET_ID", "").strip()
    gid = os.getenv("DAILY_MENU_GID", "").strip()
    if sheet and gid:
        print(f"  OK  DAILY_MENU_SHEET_ID задан, gid={gid}")
    elif sheet or gid:
        print("  WARN меню Sheets — нужны оба: DAILY_MENU_SHEET_ID и DAILY_MENU_GID")
    else:
        print("  WARN DAILY_MENU_SHEET_ID / DAILY_MENU_GID — не заданы")

    menu_chat = os.getenv("MENU_CHAT_ID", "@s_mestoest").strip()
    print(f"  OK  MENU_CHAT_ID={menu_chat}")

    tag = os.getenv("MENU_HASHTAG", "#меню")
    print(f"  OK  MENU_HASHTAG={tag!r}")

    return ok


async def check_telegram() -> bool:
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        print("  SKIP Telegram — нет BOT_TOKEN")
        return False

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        me = await bot.get_me()
        wh = await bot.get_webhook_info()
        print(f"  OK  бот @{me.username} (id={me.id})")
        if wh.url:
            print(f"  WARN webhook={wh.url!r} — polling не получит сообщения")
            print("       перезапустите бота (он сам сбрасывает webhook при старте)")
        else:
            print("  OK  webhook пустой — polling работает")
        return True
    except Exception as exc:
        print(f"  FAIL Telegram API — {exc}")
        print("       проверьте BOT_TOKEN (без кавычек и пробелов)")
        return False
    finally:
        await bot.session.close()


def check_config_load() -> bool:
    try:
        from bot.config import load_settings

        settings = load_settings()
        print(f"  OK  config загружен, staff_chat={settings.staff_chat_id}")
        return True
    except Exception as exc:
        print(f"  FAIL config — {type(exc).__name__}: {exc}")
        return False


async def main() -> None:
    print("=== Зависимости ===")
    imports_ok = check_imports()

    print("\n=== Переменные окружения ===")
    env_ok = check_env()

    print("\n=== Загрузка config ===")
    config_ok = check_config_load()

    print("\n=== Telegram API ===")
    tg_ok = await check_telegram()

    print()
    if imports_ok and env_ok and config_ok and tg_ok:
        print("Всё OK — бот должен запускаться. Если молчит, смотрите логи процесса на BotHost.")
        return

    print("Есть ошибки выше — бот не запустится или не будет отвечать. Исправьте и перезапустите.")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
