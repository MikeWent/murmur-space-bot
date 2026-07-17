from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup


async def publish_pinned_message(
    bot: Bot,
    *,
    chat_id: int,
    topic_id: int,
    text: str,
    current_message_id: int | None,
    store_message_id: Callable[[int], Awaitable[None]],
    reply_markup: InlineKeyboardMarkup | None = None,
) -> int:
    """Edit and re-pin a canonical message, recreating it when deleted."""
    if current_message_id is not None:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=current_message_id,
                reply_markup=reply_markup,
            )
        except TelegramBadRequest as exc:
            if _message_not_modified(exc):
                await _pin(bot, chat_id, current_message_id)
                return current_message_id
            if not _message_is_missing(exc):
                raise
        else:
            await _pin(bot, chat_id, current_message_id)
            return current_message_id

    message = await bot.send_message(
        chat_id=chat_id,
        message_thread_id=topic_id,
        text=text,
        reply_markup=reply_markup,
    )
    await store_message_id(message.message_id)
    await _pin(bot, chat_id, message.message_id)
    return message.message_id


async def _pin(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=True,
        )
    except TelegramBadRequest as exc:
        if "message is already pinned" not in exc.message.lower():
            raise


def _message_is_missing(exc: TelegramBadRequest) -> bool:
    message = exc.message.lower()
    return "message to edit not found" in message or "message not found" in message


def _message_not_modified(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in exc.message.lower()

