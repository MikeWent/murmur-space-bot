from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def format_local_time(value: datetime, local_timezone: ZoneInfo) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(local_timezone).strftime("%Y-%m-%d %H:%M")

