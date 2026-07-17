from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.todos.board import TodoBoardManager
from murmur_space_bot.config import Settings
from murmur_space_bot.services.todo_board import TodoBoardService


class BoardBot:
    def __init__(self) -> None:
        self.next_message_id = 100
        self.sent: list[dict[str, Any]] = []
        self.edited: list[dict[str, Any]] = []
        self.pinned: list[dict[str, Any]] = []
        self.missing_message_ids: set[int] = set()
        self.not_modified_message_ids: set[int] = set()

    async def send_message(self, **kwargs: Any) -> Any:
        self.sent.append(kwargs)
        message = SimpleNamespace(message_id=self.next_message_id)
        self.next_message_id += 1
        return message

    async def edit_message_text(self, **kwargs: Any) -> Any:
        self.edited.append(kwargs)
        if kwargs["message_id"] in self.missing_message_ids:
            raise TelegramBadRequest(
                method=EditMessageText(
                    chat_id=kwargs["chat_id"],
                    message_id=kwargs["message_id"],
                    text=kwargs["text"],
                ),
                message="Bad Request: message to edit not found",
            )
        if kwargs["message_id"] in self.not_modified_message_ids:
            raise TelegramBadRequest(
                method=EditMessageText(
                    chat_id=kwargs["chat_id"],
                    message_id=kwargs["message_id"],
                    text=kwargs["text"],
                ),
                message="Bad Request: message is not modified",
            )
        return True

    async def pin_chat_message(self, **kwargs: Any) -> bool:
        self.pinned.append(kwargs)
        return True


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


async def test_board_is_created_in_topic_stored_and_pinned(
    session: AsyncSession,
) -> None:
    bot = BoardBot()
    manager = TodoBoardManager(settings())

    message_id = await manager.refresh(
        bot,
        session,
        updated_at=datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
    )

    assert message_id == 100
    assert bot.sent[0]["chat_id"] == -100123
    assert bot.sent[0]["message_thread_id"] == 55
    assert bot.sent[0]["text"].endswith(
        "<i>Freshly updated: 2026-07-17 16:00</i>"
    )
    assert bot.pinned == [
        {"chat_id": -100123, "message_id": 100, "disable_notification": True}
    ]
    board = await TodoBoardService(session).get(-100123, 55)
    assert board is not None
    assert board.message_id == 100


async def test_existing_board_is_edited_and_repinned(session: AsyncSession) -> None:
    bot = BoardBot()
    manager = TodoBoardManager(settings())
    await manager.refresh(bot, session)

    message_id = await manager.refresh(bot, session)

    assert message_id == 100
    assert len(bot.sent) == 1
    assert bot.edited[-1]["message_id"] == 100
    assert len(bot.pinned) == 2


async def test_deleted_board_is_recreated_and_new_id_is_stored(
    session: AsyncSession,
) -> None:
    bot = BoardBot()
    manager = TodoBoardManager(settings())
    await manager.refresh(bot, session)
    bot.missing_message_ids.add(100)

    message_id = await manager.refresh(bot, session)

    assert message_id == 101
    assert len(bot.sent) == 2
    assert bot.sent[-1]["message_thread_id"] == 55
    assert bot.pinned[-1]["message_id"] == 101
    board = await TodoBoardService(session).get(-100123, 55)
    assert board is not None
    assert board.message_id == 101


async def test_unchanged_board_is_still_repinned(session: AsyncSession) -> None:
    bot = BoardBot()
    manager = TodoBoardManager(settings())
    await manager.refresh(bot, session)
    bot.not_modified_message_ids.add(100)

    message_id = await manager.refresh(bot, session)

    assert message_id == 100
    assert len(bot.sent) == 1
    assert len(bot.pinned) == 2
