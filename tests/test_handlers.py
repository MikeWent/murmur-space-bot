from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.methods import TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    MessageEntity,
    Update,
    User as TelegramUser,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from murmur_space_bot.adapters.database import initialize_schema
from murmur_space_bot.adapters.telegram.app import create_bot, create_dispatcher
from murmur_space_bot.adapters.telegram.todos.router import (
    todo_item_pressed,
    todo_command,
)
from murmur_space_bot.adapters.telegram.users.router import user_command
from murmur_space_bot.config import Settings
from murmur_space_bot.models.todo import TodoStatus
from murmur_space_bot.models.user import UserTier
from murmur_space_bot.services.todos import TodoConfirmationStore, TodoService
from murmur_space_bot.services.todo_board import TodoBoardService
from murmur_space_bot.services.users import UserService


@dataclass
class FakeMessage:
    chat: Any = field(default_factory=lambda: SimpleNamespace(id=-999))
    message_thread_id: int | None = None
    answers: list[str] = field(default_factory=list)
    answer_kwargs: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append(text)
        self.answer_kwargs.append(kwargs)


class FakeBot(Bot):
    def __init__(self) -> None:
        super().__init__("123456:test-token")
        self.requests: list[TelegramMethod[Any]] = []

    async def __call__(
        self, method: TelegramMethod[Any], request_timeout: int | None = None
    ) -> Any:
        self.requests.append(method)
        return True


@dataclass
class RecordingBoard:
    refresh_count: int = 0

    async def refresh(self, bot: Any, session: AsyncSession) -> int:
        self.refresh_count += 1
        return 100


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


async def test_bot_disables_link_previews_by_default() -> None:
    app_settings = settings()
    app_settings = Settings(
        telegram_bot_token="123456:test-token",
        database_url=app_settings.database_url,
        initial_resident_ids=app_settings.initial_resident_ids,
        recent_done_limit=app_settings.recent_done_limit,
        todo_chat_id=app_settings.todo_chat_id,
        todo_topic_id=app_settings.todo_topic_id,
        shopping_chat_id=app_settings.shopping_chat_id,
        shopping_topic_id=app_settings.shopping_topic_id,
        timezone=app_settings.timezone,
        log_level=app_settings.log_level,
    )
    bot = create_bot(app_settings)

    assert bot.default.link_preview_is_disabled is True
    await bot.session.close()


async def make_user(
    session: AsyncSession, telegram_id: int, username: str, tier: UserTier = UserTier.GUEST
):
    user = await UserService(session).sync_telegram_user(
        telegram_id=telegram_id,
        username=username,
        first_name=username,
        last_name=None,
    )
    user.tier = tier
    await session.flush()
    return user


async def test_todo_command_creates_and_lists_task_without_visible_id(
    session: AsyncSession,
) -> None:
    user = await make_user(session, 1, "creator")
    message = FakeMessage()
    board = RecordingBoard()
    bot = FakeBot()

    await todo_command(
        message,
        SimpleNamespace(args="Replace bulb"),
        session,
        user,
        settings(),
        bot,
        board,
    )
    assert "Replace bulb" in message.answers[-1]
    assert "#1" not in message.answers[-1]
    assert board.refresh_count == 1

    await todo_command(
        message,
        SimpleNamespace(args=None),
        session,
        user,
        settings(),
        bot,
        board,
    )
    assert "Replace bulb" in message.answers[-1]
    assert "#1" not in message.answers[-1]
    keyboard = message.answer_kwargs[-1]["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "todo:done:1"
    assert board.refresh_count == 1
    await bot.session.close()


async def test_todo_in_its_topic_replies_to_pinned_board(
    session: AsyncSession,
) -> None:
    user = await make_user(session, 1, "creator")
    await TodoBoardService(session).store_message(
        chat_id=-100123,
        topic_id=55,
        message_id=100,
    )
    message = FakeMessage(
        chat=SimpleNamespace(id=-100123),
        message_thread_id=55,
    )
    board = RecordingBoard()
    bot = FakeBot()

    await todo_command(
        message,
        SimpleNamespace(args=None),
        session,
        user,
        settings(),
        bot,
        board,
    )

    assert board.refresh_count == 1
    assert message.answers == ["Our current todo list is pinned right here 🌸"]
    assert message.answer_kwargs[0]["reply_parameters"].message_id == 100
    await bot.session.close()


async def test_todo_button_requires_two_taps_then_refreshes_views(
    session: AsyncSession,
) -> None:
    user = await make_user(session, 1, "worker")
    todo = await TodoService(session).create_task("Clean the kitchen", user)
    bot = FakeBot()
    board = RecordingBoard()
    confirmations = TodoConfirmationStore()
    source = Message(
        message_id=10,
        date=datetime.now(timezone.utc),
        chat=Chat(id=-999, type="supergroup"),
        from_user=TelegramUser(
            id=user.telegram_id,
            is_bot=False,
            first_name=user.first_name,
            username=user.username,
        ),
        text="/todo",
    ).as_(bot)

    first = CallbackQuery(
        id="first",
        from_user=source.from_user,
        chat_instance="chat",
        message=source,
        data=f"todo:done:{todo.id}",
    ).as_(bot)
    await todo_item_pressed(
        first, session, user, settings(), bot, board, confirmations
    )
    assert todo.status is TodoStatus.PENDING

    done = CallbackQuery(
        id="done",
        from_user=source.from_user,
        chat_instance="chat",
        message=source,
        data=f"todo:done:{todo.id}",
    ).as_(bot)
    await todo_item_pressed(
        done, session, user, settings(), bot, board, confirmations
    )

    assert todo.status is TodoStatus.DONE
    assert todo.done_by is user
    assert board.refresh_count == 1
    request_names = [request.__class__.__name__ for request in bot.requests]
    assert request_names.count("AnswerCallbackQuery") == 2
    assert request_names.count("EditMessageText") == 1
    notifications = [
        request
        for request in bot.requests
        if request.__class__.__name__ == "SendMessage"
    ]
    assert len(notifications) == 2
    topic_notifications = [
        request
        for request in notifications
        if request.chat_id == settings().todo_chat_id
        and request.message_thread_id == settings().todo_topic_id
    ]
    assert len(topic_notifications) == 1
    assert "finished by" in topic_notifications[0].text
    await bot.session.close()


async def test_first_tap_on_pinned_board_sends_no_message_notification(
    session: AsyncSession,
) -> None:
    user = await make_user(session, 1, "worker")
    todo = await TodoService(session).create_task("Water the plants", user)
    await TodoBoardService(session).store_message(
        chat_id=-100123,
        topic_id=55,
        message_id=100,
    )
    bot = FakeBot()
    board = RecordingBoard()
    source = Message(
        message_id=100,
        date=datetime.now(timezone.utc),
        chat=Chat(id=-100123, type="supergroup"),
        message_thread_id=55,
        from_user=TelegramUser(
            id=user.telegram_id,
            is_bot=False,
            first_name=user.first_name,
            username=user.username,
        ),
        text="todo board",
    ).as_(bot)
    callback = CallbackQuery(
        id="first",
        from_user=source.from_user,
        chat_instance="chat",
        message=source,
        data=f"todo:done:{todo.id}",
    ).as_(bot)

    await todo_item_pressed(callback, session, user, settings(), bot, board)

    notifications = [
        request
        for request in bot.requests
        if request.__class__.__name__ == "SendMessage"
    ]
    assert notifications == []
    assert board.refresh_count == 0
    assert not any(
        request.__class__.__name__ == "EditMessageText"
        for request in bot.requests
    )
    await bot.session.close()


async def test_guest_cannot_promote_user_via_handler(session: AsyncSession) -> None:
    actor = await make_user(session, 1, "actor")
    await make_user(session, 2, "target")
    message = FakeMessage()

    await user_command(
        message,
        SimpleNamespace(args="resident @target"),
        session,
        actor,
    )

    assert message.answers == ["Only residents can change community tiers 🌸"]


async def test_resident_can_demote_replied_user(session: AsyncSession) -> None:
    actor = await make_user(session, 1, "actor", UserTier.RESIDENT)
    target = await make_user(session, 2, "target", UserTier.RESIDENT)
    message = FakeMessage()

    await user_command(
        message,
        SimpleNamespace(args="guest"),
        session,
        actor,
        target,
    )

    assert target.tier is UserTier.GUEST
    assert "Community tier · <b>guest</b>" in message.answers[-1]


async def test_dispatcher_syncs_user_and_injects_session() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    await initialize_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app_settings = settings()
    dispatcher = create_dispatcher(app_settings, factory)
    bot = FakeBot()
    update = Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=Chat(id=10, type="private"),
            from_user=TelegramUser(
                id=42, is_bot=False, first_name="New", username="new_user"
            ),
            text="/user",
            entities=[MessageEntity(type="bot_command", offset=0, length=5)],
        ),
    )

    await dispatcher.feed_update(bot, update)

    async with factory() as db_session:
        user = await UserService(db_session).get_by_telegram_id(42)
        assert user is not None
        assert user.username == "new_user"
    assert len(bot.requests) == 1
    assert "Telegram ID · <code>42</code>" in bot.requests[0].text
    await bot.session.close()
    await engine.dispose()
