from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.common.user_links import user_link
from murmur_space_bot.adapters.telegram.todos.views import (
    format_completed,
    format_dashboard,
    format_pinned_dashboard,
)
from murmur_space_bot.adapters.telegram.users.views import format_user
from murmur_space_bot.services.todos import TodoService
from murmur_space_bot.services.users import UserService


async def test_user_links_do_not_render_username_mentions(session: AsyncSession) -> None:
    user = await UserService(session).sync_telegram_user(
        telegram_id=1,
        username="alice",
        first_name="Alice",
        last_name="Example",
    )

    assert user_link(user) == '<a href="https://t.me/alice">Alice Example</a>'
    assert "@alice" not in user_link(user)
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
    assert f"#{todo.id}" not in notification

    rendered = format_dashboard(dashboard)
    assert "<b>✨ Done</b>" in rendered
    assert "Recently done" not in rendered
    assert f"#{todo.id}" not in rendered

    pinned = format_pinned_dashboard(
        dashboard,
        datetime(2026, 7, 17, 12, 34, tzinfo=timezone.utc),
        ZoneInfo("Asia/Tbilisi"),
    )
    assert "/doing" not in pinned
    assert "/done" not in pinned
    assert f"#{todo.id}" not in pinned
