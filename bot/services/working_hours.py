from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from bot.config import Settings


def is_working_hours(settings: Settings, now: datetime | None = None) -> bool:
    tz = ZoneInfo(settings.timezone)
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
