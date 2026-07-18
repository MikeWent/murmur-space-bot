from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message, ReplyParameters
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.common.reactions import (
    is_group_chat,
    react_writing,
)
from murmur_space_bot.adapters.telegram.common.topics import is_topic, send_to_topic
from murmur_space_bot.adapters.telegram.shopping.board import ShoppingBoardManager
from murmur_space_bot.adapters.telegram.shopping.views import (
    CALLBACK_PREFIX,
    format_item_added,
    format_item_bought,
    format_shopping_list,
    shopping_keyboard,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.models.user import User
from murmur_space_bot.services.errors import ServiceError
from murmur_space_bot.services.shopping import (
    ShoppingConfirmationStore,
    ShoppingService,
)
from murmur_space_bot.services.shopping_board import ShoppingBoardService

router = Router(name="shopping")
logger = logging.getLogger(__name__)


@router.message(Command("needs"))
async def needs_command(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
    shopping_board: ShoppingBoardManager,
) -> None:
    if _is_shopping_topic(message, settings):
        await _reply_to_pinned_board(
            message, bot, session, settings, shopping_board
        )
        return
    items = await ShoppingService(session).get_active_items()
    await message.answer(
        format_shopping_list(items),
        reply_markup=shopping_keyboard(items),
    )


@router.message(Command("need"))
async def need_command(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User,
    settings: Settings,
    bot: Bot,
    shopping_board: ShoppingBoardManager,
) -> None:
    in_group = is_group_chat(message)
    if in_group:
        await react_writing(message)

    try:
        item = await ShoppingService(session).add_item(command.args or "", db_user)
    except ServiceError as exc:
        await message.answer(str(exc))
        return

    notification = format_item_added(item)
    if in_group:
        await _notify_topic(bot, settings, notification)
    else:
        await _notify(message, bot, settings, notification)
    await _refresh_board(shopping_board, bot, session)


@router.callback_query(F.data.startswith(CALLBACK_PREFIX))
async def shopping_item_pressed(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    settings: Settings,
    bot: Bot,
    shopping_board: ShoppingBoardManager,
    shopping_confirmations: ShoppingConfirmationStore,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer(
            "This shopping list wandered off, nya 🐾", show_alert=True
        )
        return

    try:
        item_id = int((callback.data or "").removeprefix(CALLBACK_PREFIX))
    except ValueError:
        await callback.answer("This button looks a little wonky 🐾", show_alert=True)
        return

    try:
        result = await ShoppingService(
            session, shopping_confirmations
        ).press_item(item_id, db_user)
    except ServiceError as exc:
        await callback.answer(str(exc), show_alert=True)
        await _refresh_views(message, bot, session, settings, shopping_board)
        return

    if not result.bought:
        await callback.answer(" 🌸 PRESS TWICE to confirm it's bought")
        return

    await callback.answer("Marked as bought ✨")
    await _refresh_views(message, bot, session, settings, shopping_board)
    await _notify(message, bot, settings, format_item_bought(result.item))


async def _refresh_views(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    shopping_board: ShoppingBoardManager,
) -> None:
    board = await ShoppingBoardService(session).get(
        settings.shopping_chat_id, settings.shopping_topic_id
    )
    is_pinned_board = (
        board is not None
        and message.chat.id == settings.shopping_chat_id
        and message.message_id == board.message_id
    )
    if not is_pinned_board:
        items = await ShoppingService(session).get_active_items()
        try:
            await message.edit_text(
                format_shopping_list(items),
                reply_markup=shopping_keyboard(items),
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in exc.message.lower():
                logger.exception("Could not update the original shopping-list message")
    await _refresh_board(shopping_board, bot, session)


async def _refresh_board(
    shopping_board: ShoppingBoardManager,
    bot: Bot,
    session: AsyncSession,
) -> None:
    try:
        await shopping_board.refresh(bot, session)
    except TelegramAPIError:
        logger.exception("Could not refresh the pinned shopping list")


async def _notify(
    message: Message,
    bot: Bot,
    settings: Settings,
    text: str,
) -> None:
    await _notify_topic(bot, settings, text)

    if not _is_shopping_topic(message, settings):
        try:
            await message.answer(text)
        except TelegramAPIError:
            logger.exception("Could not send shopping notification to source chat")


async def _notify_topic(bot: Bot, settings: Settings, text: str) -> None:
    try:
        await send_to_topic(
            bot,
            chat_id=settings.shopping_chat_id,
            topic_id=settings.shopping_topic_id,
            text=text,
        )
    except TelegramAPIError:
        logger.exception("Could not send shopping notification to its topic")


def _is_shopping_topic(message: Message, settings: Settings) -> bool:
    return is_topic(
        message,
        chat_id=settings.shopping_chat_id,
        topic_id=settings.shopping_topic_id,
    )


async def _reply_to_pinned_board(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    shopping_board: ShoppingBoardManager,
) -> None:
    await _refresh_board(shopping_board, bot, session)
    board = await ShoppingBoardService(session).get(
        settings.shopping_chat_id, settings.shopping_topic_id
    )
    if board is None:
        await message.answer("The pinned shopping list is hiding right now, nya 🐾")
        return
    try:
        await message.answer(
            "Our current shopping list is pinned right here 🌸",
            reply_parameters=ReplyParameters(message_id=board.message_id),
        )
    except TelegramAPIError:
        logger.exception("Could not reply to the pinned shopping list")
        await message.answer("The pinned shopping list is hiding right now, nya 🐾")
