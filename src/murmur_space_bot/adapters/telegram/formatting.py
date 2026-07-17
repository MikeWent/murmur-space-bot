from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo

from murmur_space_bot.models.todo import Todo
from murmur_space_bot.models.user import User
from murmur_space_bot.services.todos import TodoDashboard


def user_label(user: User) -> str:
    if user.username:
        url = f"https://t.me/{quote(user.username, safe='')}"
        return f'<a href="{url}">{escape(user.display_name)}</a>'
    return escape(user.display_name)


def format_user(user: User) -> str:
    username = user_label(user) if user.username else "—"
    return "\n".join(
        (
            f"<b>{escape(user.display_name)}</b>",
            f"Telegram ID: <code>{user.telegram_id}</code>",
            f"Username: {username}",
            f"Tier: <b>{user.tier.value}</b>",
            # f"Registered: {user.created_at:%Y-%m-%d}",
            # f"Last seen: {user.last_seen_at:%Y-%m-%d %H:%M UTC}",
        )
    )


def format_created(todo: Todo) -> str:
    return f"Created task <b>#{todo.id}</b>: {escape(todo.description)}"


def format_completed(todo: Todo) -> str:
    actor = user_label(todo.done_by) if todo.done_by else "unknown"
    return (
        f"Task #{todo.id}: <b>{escape(todo.description)}</b> completed by {actor}"
    )


def format_dashboard(dashboard: TodoDashboard) -> str:
    sections = [
        _format_section("To do", dashboard.pending, _format_pending),
        _format_section("In progress", dashboard.in_progress, _format_in_progress),
        _format_section("Done", dashboard.recently_done, _format_done),
    ]
    return "\n\n".join(sections)


def format_pinned_dashboard(
    dashboard: TodoDashboard,
    updated_at: datetime,
    local_timezone: ZoneInfo,
) -> str:
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    local_updated_at = updated_at.astimezone(local_timezone)
    return "\n".join(
        (
            format_dashboard(dashboard),
            "\n<code>/todo paint walls</code>, <code>/doing id</code>, <code>/done id</code>",
            f"<i>Last updated: {local_updated_at:%Y-%m-%d %H:%M}"
        )
    )


def _format_section(
    title: str, tasks: list[Todo], formatter: Callable[[Todo], str]
) -> str:
    lines = [f"<b>{title}</b>"]
    lines.extend(formatter(todo) for todo in tasks)
    if not tasks:
        lines.append("— none")
    return "\n".join(lines)


def _format_pending(todo: Todo) -> str:
    return f"  {escape(todo.description)} <code>#{todo.id}</code>"


def _format_in_progress(todo: Todo) -> str:
    actor = user_label(todo.taken_by) if todo.taken_by else "unknown"
    return f"  {escape(todo.description)} <code>#{todo.id}</code> — {actor}"


def _format_done(todo: Todo) -> str:
    actor = user_label(todo.done_by) if todo.done_by else "unknown"
    return f"  <s>{escape(todo.description)}</s> <code>#{todo.id}</code> — {actor}"
