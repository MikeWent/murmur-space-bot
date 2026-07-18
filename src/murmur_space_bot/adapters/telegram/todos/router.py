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
from murmur_space_bot.adapters.telegram.todos.board import TodoBoardManager
from murmur_space_bot.adapters.telegram.todos.views import (
    TODO_CALLBACK_PREFIX,
    format_completed,
    format_created,
    format_dashboard,
    todo_keyboard,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.models.user import User
from murmur_space_bot.services.errors import ServiceError
from murmur_space_bot.services.todo_board import TodoBoardService
from murmur_space_bot.services.todos import TodoConfirmationStore, TodoService

router = Router(name="todos")
logger = logging.getLogger(__name__)


@router.message(Command("todo"))
async def todo_command(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User,
    settings: Settings,
    bot: Bot,
    todo_board: TodoBoardManager,
) -> None:
    in_group = is_group_chat(message)
    if in_group:
        await react_writing(message)

    service = TodoService(session)
    task_text = (command.args or "").strip()
    try:
        if task_text:
            todo = await service.create_task(task_text, db_user)
            notification = format_created(todo)
            if in_group:
                await _notify_topic(bot, settings, notification)
            else:
                await message.answer(notification)
            await _refresh_board(todo_board, bot, session)
        elif _is_todo_topic(message, settings):
            await _reply_to_pinned_board(message, bot, session, settings, todo_board)
        else:
            dashboard = await service.get_dashboard(settings.recent_done_limit)
            await message.answer(
                format_dashboard(dashboard),
                reply_markup=todo_keyboard(dashboard),
            )
    except ServiceError as exc:
        await message.answer(str(exc))


@router.callback_query(F.data.startswith(TODO_CALLBACK_PREFIX))
async def todo_item_pressed(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    settings: Settings,
    bot: Bot,
    todo_board: TodoBoardManager,
    todo_confirmations: TodoConfirmationStore | None = None,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer("This todo list wandered off, nya 🐾", show_alert=True)
        return

    action, task_id = _parse_callback_data(callback.data)
    if action is None or task_id is None:
        await callback.answer("This button looks a little wonky 🐾", show_alert=True)
        return

    service = TodoService(session, todo_confirmations)
    try:
        result = await service.press_task(task_id, db_user)
    except ServiceError as exc:
        await callback.answer(str(exc), show_alert=True)
        await _refresh_views(message, bot, session, settings, todo_board)
        return

    if not result.completed:
        await callback.answer("🌸 PRESS TWICE to mark this task done")
        return

    await callback.answer("Task is done ✨")
    await _refresh_views(message, bot, session, settings, todo_board)
    await _notify(message, bot, settings, format_completed(result.todo))


def _parse_callback_data(data: str | None) -> tuple[str | None, int | None]:
    if not data or not data.startswith(TODO_CALLBACK_PREFIX):
        return None, None
    try:
        action, raw_task_id = data.removeprefix(TODO_CALLBACK_PREFIX).split(
            ":", maxsplit=1
        )
        task_id = int(raw_task_id)
    except ValueError:
        return None, None
    if action != "done" or task_id < 1:
        return None, None
    return action, task_id


async def _refresh_views(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    todo_board: TodoBoardManager,
) -> None:
    board = await TodoBoardService(session).get(
        settings.todo_chat_id, settings.todo_topic_id
    )
    is_pinned_board = (
        board is not None
        and message.chat.id == settings.todo_chat_id
        and message.message_id == board.message_id
    )
    if not is_pinned_board:
        dashboard = await TodoService(session).get_dashboard(
            settings.recent_done_limit
        )
        try:
            await message.edit_text(
                format_dashboard(dashboard),
                reply_markup=todo_keyboard(dashboard),
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in exc.message.lower():
                logger.exception("Could not update the original todo-list message")
    await _refresh_board(todo_board, bot, session)


async def _notify(
    message: Message,
    bot: Bot,
    settings: Settings,
    text: str,
) -> None:
    await _notify_topic(bot, settings, text)

    if not _is_todo_topic(message, settings):
        try:
            await message.answer(text)
        except TelegramAPIError:
            logger.exception("Could not send todo notification to the source chat")


async def _notify_topic(bot: Bot, settings: Settings, text: str) -> None:
    try:
        await send_to_topic(
            bot,
            chat_id=settings.todo_chat_id,
            topic_id=settings.todo_topic_id,
            text=text,
        )
    except TelegramAPIError:
        logger.exception("Could not send todo notification to its topic")


def _is_todo_topic(message: Message, settings: Settings) -> bool:
    return is_topic(
        message,
        chat_id=settings.todo_chat_id,
        topic_id=settings.todo_topic_id,
    )


async def _refresh_board(
    todo_board: TodoBoardManager,
    bot: Bot,
    session: AsyncSession,
) -> None:
    try:
        await todo_board.refresh(bot, session)
    except TelegramAPIError:
        logger.exception("Could not refresh the pinned todo dashboard")


async def _reply_to_pinned_board(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    todo_board: TodoBoardManager,
) -> None:
    await _refresh_board(todo_board, bot, session)
    board = await TodoBoardService(session).get(
        settings.todo_chat_id, settings.todo_topic_id
    )
    if board is None:
        await message.answer("The pinned todo list is hiding right now, nya 🐾")
        return
    try:
        await message.answer(
            "Our current todo list is pinned right here 🌸",
            reply_parameters=ReplyParameters(message_id=board.message_id),
        )
    except TelegramAPIError:
        logger.exception("Could not reply to the pinned todo dashboard")
        await message.answer("The pinned todo list is hiding right now, nya 🐾")
