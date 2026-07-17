from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone


CONFIRMATION_WINDOW = timedelta(seconds=30)


class ConfirmationStore:
    """Process-local, expiring confirmation state for double-tap actions."""

    def __init__(self, window: timedelta = CONFIRMATION_WINDOW) -> None:
        self.window = window
        self._confirmations: dict[tuple[int, int], datetime] = {}
        self._lock = asyncio.Lock()

    async def arm_or_confirm(
        self,
        *,
        item_id: int,
        user_id: int,
        pressed_at: datetime,
    ) -> bool:
        now = self._aware(pressed_at)
        key = (item_id, user_id)
        async with self._lock:
            self._remove_expired(now)
            previous = self._confirmations.pop(key, None)
            if previous is not None and now - previous <= self.window:
                return True
            self._confirmations[key] = now
            return False

    async def clear_item(self, item_id: int) -> None:
        async with self._lock:
            keys = [key for key in self._confirmations if key[0] == item_id]
            for key in keys:
                del self._confirmations[key]

    def _remove_expired(self, now: datetime) -> None:
        expired = [
            key
            for key, confirmed_at in self._confirmations.items()
            if now - confirmed_at > self.window
        ]
        for key in expired:
            del self._confirmations[key]

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
