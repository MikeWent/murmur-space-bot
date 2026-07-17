from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.formatting import (
    format_completed,
    format_dashboard,
    format_pinned_dashboard,
    format_user,
    user_label,
)
from murmur_space_bot.services.todos import TodoService
from murmur_space_bot.services.users import UserService


async def test_user_links_do_not_render_username_mentions(session: AsyncSession) -> None:
    user = await UserService(session).sync_telegram_user(
        telegram_id=1,
        username="alice",
        first_name="Alice",
        last_name="Example",
    )

    assert user_label(user) == '<a href="https://t.me/alice">Alice Example</a>'
    assert "@alice" not in user_label(user)
    assert "@alice" not in format_user(user)


async def test_done_formatting_and_pinned_footer(session: AsyncSession) -> None:
    user = await UserService(session).sync_telegram_user(
        telegram_id=1,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    service = TodoService(session)
    todo = await service.create_task("Wash all the dishes", user)
    todo = await service.complete_task(todo.id, user)
    dashboard = await service.get_dashboard()

    notification = format_completed(todo)
    assert "Wash all the dishes" in notification
    assert "@alice" not in notification

    rendered = format_dashboard(dashboard)
    assert "<b>Done</b>" in rendered
    assert "Recently done" not in rendered

    pinned = format_pinned_dashboard(
        dashboard,
        datetime(2026, 7, 17, 12, 34, tzinfo=timezone.utc),
        ZoneInfo("Asia/Tbilisi"),
    )
    assert "/todo paint walls" in pinned
    assert "/doing id" in pinned
    assert "/done id" in pinned
    assert pinned.endswith(
        "<i>Last updated: 2026-07-17 16:34 (Asia/Tbilisi)</i>"
    )
