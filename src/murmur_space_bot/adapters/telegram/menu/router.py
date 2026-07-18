from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.common.topics import send_to_topic
from murmur_space_bot.adapters.telegram.menu.views import (
    ADD_ITEM_BUTTON,
    ADD_TASK_BUTTON,
    CANCEL_BUTTON,
    SHOPPING_BUTTON,
    TASKS_BUTTON,
    cancel_keyboard,
    main_menu_keyboard,
    welcome_text,
)
from murmur_space_bot.adapters.telegram.shopping.board import ShoppingBoardManager
from murmur_space_bot.adapters.telegram.shopping.views import (
    format_item_added,
    format_shopping_list,
    shopping_keyboard,
)
from murmur_space_bot.adapters.telegram.todos.board import TodoBoardManager
from murmur_space_bot.adapters.telegram.todos.views import (
    format_created,
    format_dashboard,
    todo_keyboard,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.models.user import User
from murmur_space_bot.services.errors import ServiceError
from murmur_space_bot.services.shopping import ShoppingService
from murmur_space_bot.services.todos import TodoService

router = Router(name="private-menu")
logger = logging.getLogger(__name__)


class MenuState(StatesGroup):
    waiting_for_task = State()
    waiting_for_item = State()


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def start_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(welcome_text(), reply_markup=main_menu_keyboard())


@router.message(F.chat.type == ChatType.PRIVATE, F.text == TASKS_BUTTON)
async def show_tasks(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    dashboard = await TodoService(session).get_dashboard(settings.recent_done_limit)
    await message.answer(
        format_dashboard(dashboard),
        reply_markup=todo_keyboard(dashboard),
    )


@router.message(F.chat.type == ChatType.PRIVATE, F.text == SHOPPING_BUTTON)
async def show_shopping(message: Message, session: AsyncSession) -> None:
    items = await ShoppingService(session).get_active_items()
    await message.answer(
        format_shopping_list(items),
        reply_markup=shopping_keyboard(items),
    )


@router.message(F.chat.type == ChatType.PRIVATE, F.text == ADD_TASK_BUTTON)
async def ask_for_task(message: Message, state: FSMContext) -> None:
    await state.set_state(MenuState.waiting_for_task)
    await message.answer(
        "What needs doing? ✨",
        reply_markup=cancel_keyboard("Describe the task…"),
    )


@router.message(F.chat.type == ChatType.PRIVATE, F.text == ADD_ITEM_BUTTON)
async def ask_for_item(message: Message, state: FSMContext) -> None:
    await state.set_state(MenuState.waiting_for_item)
    await message.answer(
        "What should I add to the shopping list? 🛒",
        reply_markup=cancel_keyboard("Type an item or paste a link…"),
    )


@router.message(
    F.chat.type == ChatType.PRIVATE,
    F.text == CANCEL_BUTTON,
    StateFilter("*"),
)
async def cancel_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled ♡", reply_markup=main_menu_keyboard())


@router.message(MenuState.waiting_for_task, F.chat.type == ChatType.PRIVATE)
async def add_task(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    settings: Settings,
    bot: Bot,
    todo_board: TodoBoardManager,
) -> None:
    try:
        todo = await TodoService(session).create_task(message.text or "", db_user)
    except ServiceError as exc:
        await message.answer(
            str(exc),
            reply_markup=cancel_keyboard("Describe the task…"),
        )
        return

    await state.clear()
    text = format_created(todo)
    await message.answer(text, reply_markup=main_menu_keyboard())
    await asyncio.gather(
        _send_to_todo_topic(bot, settings, text),
        _refresh_todo_board(todo_board, bot, session),
    )


@router.message(MenuState.waiting_for_item, F.chat.type == ChatType.PRIVATE)
async def add_item(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    settings: Settings,
    bot: Bot,
    shopping_board: ShoppingBoardManager,
) -> None:
    try:
        item = await ShoppingService(session).add_item(message.text or "", db_user)
    except ServiceError as exc:
        await message.answer(
            str(exc),
            reply_markup=cancel_keyboard("Type an item or paste a link…"),
        )
        return

    await state.clear()
    text = format_item_added(item)
    await message.answer(text, reply_markup=main_menu_keyboard())
    await asyncio.gather(
        _send_to_shopping_topic(bot, settings, text),
        _refresh_shopping_board(shopping_board, bot, session),
    )


@router.message(StateFilter(None), F.chat.type == ChatType.PRIVATE)
async def show_menu_fallback(message: Message) -> None:
    await message.answer(
        "Choose a card below and I'll take it from there 🐾",
        reply_markup=main_menu_keyboard(),
    )


async def _refresh_todo_board(
    todo_board: TodoBoardManager,
    bot: Bot,
    session: AsyncSession,
) -> None:
    try:
        await todo_board.refresh(bot, session)
    except TelegramAPIError:
        logger.exception("Could not refresh the pinned todo dashboard")


async def _refresh_shopping_board(
    shopping_board: ShoppingBoardManager,
    bot: Bot,
    session: AsyncSession,
) -> None:
    try:
        await shopping_board.refresh(bot, session)
    except TelegramAPIError:
        logger.exception("Could not refresh the pinned shopping list")


async def _send_to_shopping_topic(
    bot: Bot,
    settings: Settings,
    text: str,
) -> None:
    try:
        await send_to_topic(
            bot,
            chat_id=settings.shopping_chat_id,
            topic_id=settings.shopping_topic_id,
            text=text,
        )
    except TelegramAPIError:
        logger.exception("Could not mirror shopping notification")


async def _send_to_todo_topic(
    bot: Bot,
    settings: Settings,
    text: str,
) -> None:
    try:
        await send_to_topic(
            bot,
            chat_id=settings.todo_chat_id,
            topic_id=settings.todo_topic_id,
            text=text,
        )
    except TelegramAPIError:
        logger.exception("Could not mirror task notification")
