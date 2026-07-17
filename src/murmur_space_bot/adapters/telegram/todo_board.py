from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.formatting import format_pinned_dashboard
from murmur_space_bot.config import Settings
from murmur_space_bot.models.base import utc_now
from murmur_space_bot.services.todo_board import TodoBoardService
from murmur_space_bot.services.todos import TodoService


class TodoBoardManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def refresh(
        self,
        bot: Bot,
        session: AsyncSession,
        *,
        updated_at: datetime | None = None,
    ) -> int:
        dashboard = await TodoService(session).get_dashboard(
            self.settings.recent_done_limit
        )
        text = format_pinned_dashboard(
            dashboard,
            updated_at or utc_now(),
            self.settings.timezone,
        )
        board_service = TodoBoardService(session)
        board = await board_service.get(
            self.settings.todo_chat_id, self.settings.todo_topic_id
        )

        if board is not None:
            try:
                await bot.edit_message_text(
                    text=text,
                    chat_id=self.settings.todo_chat_id,
                    message_id=board.message_id,
                )
            except TelegramBadRequest as exc:
                if self._message_not_modified(exc):
                    await self._pin(bot, board.message_id)
                    return board.message_id
                if not self._message_is_missing(exc):
                    raise
            else:
                await self._pin(bot, board.message_id)
                return board.message_id

        message = await bot.send_message(
            chat_id=self.settings.todo_chat_id,
            message_thread_id=self.settings.todo_topic_id,
            text=text,
        )
        await board_service.store_message(
            chat_id=self.settings.todo_chat_id,
            topic_id=self.settings.todo_topic_id,
            message_id=message.message_id,
        )
        await self._pin(bot, message.message_id)
        return message.message_id

    async def _pin(self, bot: Bot, message_id: int) -> None:
        try:
            await bot.pin_chat_message(
                chat_id=self.settings.todo_chat_id,
                message_id=message_id,
                disable_notification=True,
            )
        except TelegramBadRequest as exc:
            if "message is already pinned" not in exc.message.lower():
                raise

    @staticmethod
    def _message_is_missing(exc: TelegramBadRequest) -> bool:
        message = exc.message.lower()
        return "message to edit not found" in message or "message not found" in message

    @staticmethod
    def _message_not_modified(exc: TelegramBadRequest) -> bool:
        return "message is not modified" in exc.message.lower()
