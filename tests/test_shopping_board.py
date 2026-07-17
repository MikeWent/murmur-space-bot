from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.shopping.board import ShoppingBoardManager
from murmur_space_bot.adapters.telegram.shopping.views import (
    format_shopping_list,
    shopping_keyboard,
)
from murmur_space_bot.config import Settings
from murmur_space_bot.services.shopping import ShoppingService
from murmur_space_bot.services.shopping_board import ShoppingBoardService
from murmur_space_bot.services.users import UserService


class BoardBot:
    def __init__(self) -> None:
        self.next_message_id = 200
        self.sent: list[dict[str, Any]] = []
        self.edited: list[dict[str, Any]] = []
        self.pinned: list[dict[str, Any]] = []
        self.missing_message_ids: set[int] = set()

    async def send_message(self, **kwargs: Any) -> Any:
        self.sent.append(kwargs)
        message = SimpleNamespace(message_id=self.next_message_id)
        self.next_message_id += 1
        return message

    async def edit_message_text(self, **kwargs: Any) -> bool:
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


async def add_item(session: AsyncSession) -> None:
    user = await UserService(session).sync_telegram_user(
        telegram_id=1,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    await ShoppingService(session).add_item("Oat milk", user)


async def test_shopping_board_has_item_buttons_and_is_pinned(
    session: AsyncSession,
) -> None:
    await add_item(session)
    bot = BoardBot()
    manager = ShoppingBoardManager(settings())

    message_id = await manager.refresh(
        bot,
        session,
        updated_at=datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc),
    )

    assert message_id == 200
    assert bot.sent[0]["message_thread_id"] == 77
    assert "Tap an item <b>twice</b>" in bot.sent[0]["text"]
    assert (
        '• Oat milk — by <a href="https://t.me/alice">Alice</a>'
        in bot.sent[0]["text"]
    )
    assert "Freshly updated: 2026-07-17 16:00" in bot.sent[0]["text"]
    button = bot.sent[0]["reply_markup"].inline_keyboard[0][0]
    assert "Oat milk" in button.text
    assert "Alice" not in button.text
    assert button.callback_data == "need:1"
    assert bot.pinned[-1]["message_id"] == 200
    board = await ShoppingBoardService(session).get(-100456, 77)
    assert board is not None
    assert board.message_id == 200


async def test_deleted_shopping_board_is_recreated(session: AsyncSession) -> None:
    bot = BoardBot()
    manager = ShoppingBoardManager(settings())
    await manager.refresh(bot, session)
    bot.missing_message_ids.add(200)

    message_id = await manager.refresh(bot, session)

    assert message_id == 201
    assert len(bot.sent) == 2
    board = await ShoppingBoardService(session).get(-100456, 77)
    assert board is not None
    assert board.message_id == 201


async def test_list_text_has_clickable_links_and_item_attribution(
    session: AsyncSession,
) -> None:
    user = await UserService(session).sync_telegram_user(
        telegram_id=1,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    url = (
        "https://www.amazon.com/FLASHFORGE-Adventurer-5M-Detachable-"
        "220x220x220mm/dp/B0CH4NYL6J/ref=pd_ci_mcx_mh_mcx_views_0_title?"
        "pd_rd_w=AQH7O&content-id=amzn1.sym.781fe6e1-9487-4a74-b81e-"
        "5a879e5ec273%3Aamzn1.symc.c3d5766d-b606-46b8-ab07-1d9d1da0638a&"
        "pf_rd_p=781fe6e1-9487-4a74-b81e-5a879e5ec273&"
        "pf_rd_r=S428XP4E18CMEYBNQD5G&pd_rd_wg=4IziW&"
        "pd_rd_r=05d6cdbd-bb25-47cf-bda8-a738ea0d66c0&"
        "pd_rd_i=B0CH4NYL6J&th=1"
    )
    item = await ShoppingService(session).add_item(f"3d printer {url}", user)
    items = await ShoppingService(session).get_active_items()

    text = format_shopping_list(items)

    assert item.name == f"3d printer {url}"
    assert f'<a href="{escape(url, quote=True)}">www.amazon.com/…</a>' in text
    assert '— by <a href="https://t.me/alice">Alice</a>' in text
    keyboard = shopping_keyboard(items)
    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "3d printer 🔗"
    assert url not in button.text
    assert len(button.text) <= 64
    assert button.callback_data == "need:1"
