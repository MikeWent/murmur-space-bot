from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.shopping.router import (
    need_command,
    needs_command,
    shopping_item_pressed,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.services.shopping import (
    ShoppingConfirmationStore,
    ShoppingService,
)
from murmur_space_bot.services.shopping_board import ShoppingBoardService
from murmur_space_bot.services.users import UserService


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

    async def refresh(self, bot, session) -> int:
        self.refresh_count += 1
        return 200


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


async def make_user(session: AsyncSession):
    return await UserService(session).sync_telegram_user(
        telegram_id=1,
        username="alice",
        first_name="Alice",
        last_name=None,
    )


def message(
    bot: FakeBot,
    user,
    *,
    chat_id: int = -999,
    topic_id: int = 12,
) -> Message:
    return Message(
        message_id=10,
        date=datetime.now(timezone.utc),
        chat=Chat(id=chat_id, type="supergroup"),
        message_thread_id=topic_id,
        from_user=TelegramUser(
            id=user.telegram_id,
            is_bot=False,
            first_name=user.first_name,
            username=user.username,
        ),
        text="/needs",
    ).as_(bot)


async def test_need_in_group_reacts_and_notifies_only_shopping_topic(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    bot = FakeBot()
    source = message(bot, user)
    board = RecordingBoard()

    await need_command(
        source,
        SimpleNamespace(args="Oat milk"),
        session,
        user,
        settings(),
        bot,
        board,
    )

    assert board.refresh_count == 1
    assert len(await ShoppingService(session).get_active_items()) == 1
    send_requests = [
        request
        for request in bot.requests
        if request.__class__.__name__ == "SendMessage"
    ]
    assert len(send_requests) == 1
    topic_notification = send_requests[0]
    assert topic_notification.chat_id == -100456
    assert topic_notification.message_thread_id == 77
    reaction_requests = [
        request
        for request in bot.requests
        if request.__class__.__name__ == "SetMessageReaction"
    ]
    assert len(reaction_requests) == 1
    assert reaction_requests[0].reaction[0].emoji == "✍️"
    await bot.session.close()


async def test_needs_in_its_topic_replies_to_pinned_board(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    await ShoppingBoardService(session).store_message(
        chat_id=-100456,
        topic_id=77,
        message_id=200,
    )
    bot = FakeBot()
    source = message(bot, user, chat_id=-100456, topic_id=77)
    board = RecordingBoard()

    await needs_command(source, session, settings(), bot, board)

    assert board.refresh_count == 1
    send_requests = [
        request
        for request in bot.requests
        if request.__class__.__name__ == "SendMessage"
    ]
    assert len(send_requests) == 1
    assert (
        send_requests[0].text
        == "Our current shopping list is pinned right here 🌸"
    )
    assert send_requests[0].reply_parameters.message_id == 200
    await bot.session.close()


async def test_need_does_not_duplicate_notification_inside_shopping_topic(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    bot = FakeBot()
    source = message(bot, user, chat_id=-100456, topic_id=77)

    await need_command(
        source,
        SimpleNamespace(args="Dish soap"),
        session,
        user,
        settings(),
        bot,
        RecordingBoard(),
    )

    send_requests = [
        request
        for request in bot.requests
        if request.__class__.__name__ == "SendMessage"
    ]
    assert len(send_requests) == 1
    assert send_requests[0].chat_id == -100456
    assert send_requests[0].message_thread_id == 77
    await bot.session.close()


async def test_two_taps_buy_update_original_and_mirror_notification(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    item = await ShoppingService(session).add_item("Coffee", user)
    bot = FakeBot()
    source = message(bot, user)
    board = RecordingBoard()
    confirmations = ShoppingConfirmationStore()

    first = CallbackQuery(
        id="first",
        from_user=source.from_user,
        chat_instance="chat",
        message=source,
        data=f"need:{item.id}",
    ).as_(bot)
    second = CallbackQuery(
        id="second",
        from_user=source.from_user,
        chat_instance="chat",
        message=source,
        data=f"need:{item.id}",
    ).as_(bot)

    await shopping_item_pressed(
        first, session, user, settings(), bot, board, confirmations
    )
    assert board.refresh_count == 0
    assert len(await ShoppingService(session).get_active_items()) == 1

    await shopping_item_pressed(
        second, session, user, settings(), bot, board, confirmations
    )
    assert board.refresh_count == 1
    assert await ShoppingService(session).get_active_items() == []
    request_names = [request.__class__.__name__ for request in bot.requests]
    assert "EditMessageText" in request_names
    assert request_names.count("SendMessage") == 2
    await bot.session.close()


async def test_buy_on_pinned_board_sends_one_notification_to_shopping_topic(
    session: AsyncSession,
) -> None:
    user = await make_user(session)
    item = await ShoppingService(session).add_item("Coffee", user)
    await ShoppingBoardService(session).store_message(
        chat_id=-100456,
        topic_id=77,
        message_id=10,
    )
    bot = FakeBot()
    source = message(bot, user, chat_id=-100456, topic_id=77)
    board = RecordingBoard()
    confirmations = ShoppingConfirmationStore()

    for callback_id in ("first", "second"):
        callback = CallbackQuery(
            id=callback_id,
            from_user=source.from_user,
            chat_instance="chat",
            message=source,
            data=f"need:{item.id}",
        ).as_(bot)
        await shopping_item_pressed(
            callback,
            session,
            user,
            settings(),
            bot,
            board,
            confirmations,
        )

    send_requests = [
        request
        for request in bot.requests
        if request.__class__.__name__ == "SendMessage"
    ]
    assert len(send_requests) == 1
    assert send_requests[0].chat_id == -100456
    assert send_requests[0].message_thread_id == 77
    assert "Coffee" in send_requests[0].text
    assert board.refresh_count == 1
    assert await ShoppingService(session).get_active_items() == []
    await bot.session.close()
