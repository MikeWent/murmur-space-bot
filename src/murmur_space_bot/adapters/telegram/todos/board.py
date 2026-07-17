from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.common.pinned_messages import (
    publish_pinned_message,
)
from murmur_space_bot.adapters.telegram.todos.views import format_pinned_dashboard
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

        async def store_message_id(message_id: int) -> None:
            await board_service.store_message(
                chat_id=self.settings.todo_chat_id,
                topic_id=self.settings.todo_topic_id,
                message_id=message_id,
            )

        return await publish_pinned_message(
            bot,
            chat_id=self.settings.todo_chat_id,
            topic_id=self.settings.todo_topic_id,
            text=text,
            current_message_id=board.message_id if board else None,
            store_message_id=store_message_id,
        )

