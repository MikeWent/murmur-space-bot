from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.config import Settings
from murmur_space_bot.services.users import UserService


class UserSyncMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]
        service = UserService(session, self.settings.initial_resident_ids)
        telegram_user = data.get("event_from_user")

        if telegram_user is not None and not telegram_user.is_bot:
            data["db_user"] = await service.sync_telegram_user(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
            )

        message = self._message_from_update(event)
        replied_user = (
            message.reply_to_message.from_user
            if message and message.reply_to_message
            else None
        )
        if replied_user is not None and not replied_user.is_bot:
            data["db_replied_user"] = await service.sync_telegram_user(
                telegram_id=replied_user.id,
                username=replied_user.username,
                first_name=replied_user.first_name,
                last_name=replied_user.last_name,
            )

        return await handler(event, data)

    @staticmethod
    def _message_from_update(event: TelegramObject) -> Message | None:
        if isinstance(event, Update):
            return event.message or event.edited_message
        if isinstance(event, Message):
            return event
        return None

