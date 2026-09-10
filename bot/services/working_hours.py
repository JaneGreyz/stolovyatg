from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from bot.config import Settings

MOSCOW_TZ = timezone(timedelta(hours=3))


def get_tz(settings: Settings):
    try:
        return ZoneInfo(settings.timezone)
    except Exception:
        return MOSCOW_TZ


def _now(settings: Settings, now: datetime | None = None) -> datetime:
    tz = get_tz(settings)
    return now or datetime.now(tz)


def is_weekday(settings: Settings, now: datetime | None = None) -> bool:
    if not settings.work_weekdays_only:
        return True
    return _now(settings, now).weekday() < 5


def is_delivery_hours(settings: Settings, now: datetime | None = None) -> bool:
    """Приём заказов на доставку (будни, work_start — work_end)."""
    current = _now(settings, now)
    if settings.work_weekdays_only and current.weekday() >= 5:
        return False
    current_time = current.time()
    return settings.work_start <= current_time <= settings.work_end


def is_working_hours(settings: Settings, now: datetime | None = None) -> bool:
    return is_delivery_hours(settings, now)


def is_breakfast_hours(settings: Settings, now: datetime | None = None) -> bool:
    """8:45–10:00 — только завтраки из постоянного меню."""
    if not is_delivery_hours(settings, now):
        return False
    current_time = _now(settings, now).time()
    return settings.work_start <= current_time < settings.full_menu_start


def is_full_menu_hours(settings: Settings, now: datetime | None = None) -> bool:
    """С 10:00 — ланч и актуальное меню дня."""
    if not is_delivery_hours(settings, now):
        return False
    current_time = _now(settings, now).time()
    return settings.full_menu_start <= current_time <= settings.work_end


def format_work_hours(settings: Settings) -> str:
    start = settings.work_start.strftime("%H:%M")
    full = settings.full_menu_start.strftime("%H:%M")
    end = settings.work_end.strftime("%H:%M")
    if settings.work_weekdays_only:
        return (
            f"по будням с {start} до {end} "
            f"(завтраки с {start}, ланч и меню дня — с {full})"
        )
    return (
        f"с {start} до {end} "
        f"(завтраки с {start}, ланч — с {full})"
    )
