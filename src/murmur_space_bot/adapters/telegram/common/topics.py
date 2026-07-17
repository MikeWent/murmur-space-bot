from __future__ import annotations

from aiogram.types import Message


def is_topic(message: Message, *, chat_id: int, topic_id: int) -> bool:
    return message.chat.id == chat_id and message.message_thread_id == topic_id

