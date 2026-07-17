from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.common.pinned_messages import (
    publish_pinned_message,
)
from murmur_space_bot.adapters.telegram.shopping.views import (
    format_shopping_list,
    shopping_keyboard,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.models.base import utc_now
from murmur_space_bot.services.shopping import ShoppingService
from murmur_space_bot.services.shopping_board import ShoppingBoardService


class ShoppingBoardManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def refresh(
        self,
        bot: Bot,
        session: AsyncSession,
        *,
        updated_at: datetime | None = None,
    ) -> int:
        items = await ShoppingService(session).get_active_items()
        text = format_shopping_list(
            items,
            updated_at=updated_at or utc_now(),
            local_timezone=self.settings.timezone,
        )
        board_service = ShoppingBoardService(session)
        board = await board_service.get(
            self.settings.shopping_chat_id,
            self.settings.shopping_topic_id,
        )

        async def store_message_id(message_id: int) -> None:
            await board_service.store_message(
                chat_id=self.settings.shopping_chat_id,
                topic_id=self.settings.shopping_topic_id,
                message_id=message_id,
            )

        return await publish_pinned_message(
            bot,
            chat_id=self.settings.shopping_chat_id,
            topic_id=self.settings.shopping_topic_id,
            text=text,
            current_message_id=board.message_id if board else None,
            store_message_id=store_message_id,
            reply_markup=shopping_keyboard(items),
        )

