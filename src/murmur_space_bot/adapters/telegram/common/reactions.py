from __future__ import annotations

import logging

from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, ReactionTypeEmoji

logger = logging.getLogger(__name__)

WRITING_REACTION = "✍️"


def is_group_chat(message: Message) -> bool:
    return getattr(message.chat, "type", None) in {
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    }


async def react_writing(message: Message) -> None:
    """Acknowledge a group command without blocking it if reactions are unavailable."""
    try:
        await message.react([ReactionTypeEmoji(emoji=WRITING_REACTION)])
    except TelegramAPIError:
        logger.exception("Could not react to a group command")
