from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.menu.router import (
    MenuState,
    add_item,
    add_task,
    ask_for_item,
    ask_for_task,
    show_shopping,
    show_tasks,
    start_menu,
)
from murmur_space_bot.adapters.telegram.menu.views import (
    ADD_ITEM_BUTTON,
    ADD_TASK_BUTTON,
    SHOPPING_BUTTON,
    TASKS_BUTTON,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.services.shopping import ShoppingService
from murmur_space_bot.services.todos import TodoService
from murmur_space_bot.services.users import UserService


@dataclass
class FakeMessage:
    text: str | None = None
    answers: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append((text, kwargs))


@dataclass
class FakeState:
    value: Any = None

    async def set_state(self, value: Any) -> None:
        self.value = value

    async def clear(self) -> None:
        self.value = None


@dataclass
class RecordingBoard:
    refresh_count: int = 0

    async def refresh(self, bot: Any, session: Any) -> int:
        self.refresh_count += 1
        return 100


@dataclass
class FakeBot:
    sent: list[dict[str, Any]] = field(default_factory=list)

    async def send_message(self, **kwargs: Any) -> None:
        self.sent.append(kwargs)


def settings() -> Settings:
    return Settings(
        telegram_bot_token="test-token",
        database_url="sqlite+aiosqlite:///:memory:",
        initial_resident_ids=frozenset(),
        recent_done_limit=5,
        todo_chat_id=-100123,
        todo_topic_id=55,
        shopping_chat_id=-100456,
        shopping_topic_id=77,
        timezone=ZoneInfo("Asia/Tbilisi"),
        log_level="INFO",
    )


async def test_private_menu_guides_task_and_shopping_creation(
    session: AsyncSession,
) -> None:
    user = await UserService(session).sync_telegram_user(
        telegram_id=42,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    state = FakeState()
    bot = FakeBot()
    todo_board = RecordingBoard()
    shopping_board = RecordingBoard()

    welcome = FakeMessage()
    await start_menu(welcome, state)
    welcome_markup = welcome.answers[-1][1]["reply_markup"]
    button_rows = [
        [button.text for button in row]
        for row in welcome_markup.keyboard
    ]
    assert button_rows == [
        [TASKS_BUTTON, SHOPPING_BUTTON],
        [ADD_TASK_BUTTON, ADD_ITEM_BUTTON],
    ]
    assert welcome_markup.is_persistent is True

    task_prompt = FakeMessage()
    await ask_for_task(task_prompt, state)
    assert state.value == MenuState.waiting_for_task
    assert "What needs doing?" in task_prompt.answers[-1][0]

    task_input = FakeMessage(text="Review the new logo")
    await add_task(
        task_input,
        state,
        session,
        user,
        settings(),
        bot,
        todo_board,
    )
    assert state.value is None
    assert todo_board.refresh_count == 1
    assert task_input.answers[-1][1]["reply_markup"].is_persistent is True

    tasks_view = FakeMessage()
    await show_tasks(tasks_view, session, settings())
    tasks_text, tasks_kwargs = tasks_view.answers[-1]
    assert "Review the new logo" in tasks_text
    assert tasks_kwargs["reply_markup"].inline_keyboard[0][
        0
    ].callback_data.startswith("todo:done:")

    item_prompt = FakeMessage()
    await ask_for_item(item_prompt, state)
    assert state.value == MenuState.waiting_for_item
    assert "shopping list" in item_prompt.answers[-1][0]

    item_input = FakeMessage(text="Pink sticky notes")
    await add_item(
        item_input,
        state,
        session,
        user,
        settings(),
        bot,
        shopping_board,
    )
    assert state.value is None
    assert shopping_board.refresh_count == 1
    assert item_input.answers[-1][1]["reply_markup"].is_persistent is True

    shopping_view = FakeMessage()
    await show_shopping(shopping_view, session)
    shopping_text, shopping_kwargs = shopping_view.answers[-1]
    assert "Pink sticky notes" in shopping_text
    assert shopping_kwargs["reply_markup"].inline_keyboard[0][
        0
    ].callback_data.startswith("need:")

    dashboard = await TodoService(session).get_dashboard()
    items = await ShoppingService(session).get_active_items()
    assert [todo.description for todo in dashboard.pending] == [
        "Review the new logo"
    ]
    assert [item.name for item in items] == ["Pink sticky notes"]

    assert len(bot.sent) == 2
    assert bot.sent[0]["chat_id"] == settings().todo_chat_id
    assert bot.sent[0]["message_thread_id"] == settings().todo_topic_id
    assert "Review the new logo" in bot.sent[0]["text"]
    assert bot.sent[1]["chat_id"] == settings().shopping_chat_id
    assert bot.sent[1]["message_thread_id"] == settings().shopping_topic_id
    assert "Pink sticky notes" in bot.sent[1]["text"]
