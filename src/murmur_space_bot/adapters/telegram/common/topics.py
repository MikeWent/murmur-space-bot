from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message


def is_topic(message: Message, *, chat_id: int, topic_id: int) -> bool:
    return message.chat.id == chat_id and message.message_thread_id == topic_id


async def send_to_topic(
    bot: Bot,
    *,
    chat_id: int,
    topic_id: int,
    text: str,
) -> None:
    """Send a message to a forum topic without relying on reply inference."""
    await bot.send_message(
        chat_id=chat_id,
        message_thread_id=topic_id,
        text=text,
    )
