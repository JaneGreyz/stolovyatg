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


def is_working_hours(settings: Settings, now: datetime | None = None) -> bool:
    tz = get_tz(settings)
    current = now or datetime.now(tz)

    if settings.work_weekdays_only and current.weekday() >= 5:
        return False

    current_time = current.time()
    return settings.work_start <= current_time <= settings.work_end


def format_work_hours(settings: Settings) -> str:
    start = settings.work_start.strftime("%H:%M")
    end = settings.work_end.strftime("%H:%M")
    if settings.work_weekdays_only:
        return f"по будням с {start} до {end}"
    return f"с {start} до {end}"
