from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ReplyParameters
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.common.topics import is_topic
from murmur_space_bot.adapters.telegram.common.user_links import user_link
from murmur_space_bot.adapters.telegram.todos.board import TodoBoardManager
from murmur_space_bot.adapters.telegram.todos.views import (
    format_completed,
    format_created,
    format_dashboard,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.models.user import User
from murmur_space_bot.services.errors import ServiceError
from murmur_space_bot.services.todo_board import TodoBoardService
from murmur_space_bot.services.todos import TodoService

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
    service = TodoService(session)
    task_text = (command.args or "").strip()
    try:
        if task_text:
            todo = await service.create_task(task_text, db_user)
            await message.answer(format_created(todo))
            await _refresh_board(todo_board, bot, session)
        elif is_topic(
            message,
            chat_id=settings.todo_chat_id,
            topic_id=settings.todo_topic_id,
        ):
            await _reply_to_pinned_board(message, bot, session, settings, todo_board)
        else:
            dashboard = await service.get_dashboard(settings.recent_done_limit)
            await message.answer(format_dashboard(dashboard))
    except ServiceError as exc:
        await message.answer(str(exc))


@router.message(Command("doing"))
async def doing_command(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User,
    bot: Bot,
    todo_board: TodoBoardManager,
) -> None:
    task_id = await _parse_task_id(message, command, "doing")
    if task_id is None:
        return
    try:
        todo = await TodoService(session).start_task(task_id, db_user)
    except ServiceError as exc:
        await message.answer(str(exc))
        return
    await message.answer(
        f"🐾 Task <b>#{todo.id}</b> is in progress with {user_link(db_user)}."
    )
    await _refresh_board(todo_board, bot, session)


@router.message(Command("done"))
async def done_command(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User,
    bot: Bot,
    todo_board: TodoBoardManager,
) -> None:
    task_id = await _parse_task_id(message, command, "done")
    if task_id is None:
        return
    try:
        todo = await TodoService(session).complete_task(task_id, db_user)
    except ServiceError as exc:
        await message.answer(str(exc))
        return
    await message.answer(format_completed(todo))
    await _refresh_board(todo_board, bot, session)


async def _parse_task_id(
    message: Message, command: CommandObject, command_name: str
) -> int | None:
    value = (command.args or "").strip()
    if not value.isdigit() or int(value) < 1:
        await message.answer(f"🌸 Try: /{command_name} &lt;task-id&gt;")
        return None
    return int(value)


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
