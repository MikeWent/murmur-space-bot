from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from murmur_space_bot.adapters.telegram.common.time import format_local_time
from murmur_space_bot.adapters.telegram.common.user_links import user_link
from murmur_space_bot.models.todo import Todo
from murmur_space_bot.services.todos import TodoDashboard


def format_created(todo: Todo) -> str:
    return f"🌸 Added task <b>#{todo.id}</b>: {escape(todo.description)}"


def format_completed(todo: Todo) -> str:
    actor = user_link(todo.done_by) if todo.done_by else "a mystery kitty"
    return f"✅ Task #{todo.id}: <b>{escape(todo.description)}</b> finished by {actor}!"


def format_dashboard(dashboard: TodoDashboard) -> str:
    sections = [
        _format_section("🌸 To do", dashboard.pending, _format_pending),
        _format_section("🐾 In progress", dashboard.in_progress, _format_in_progress),
        _format_section("✨ Done", dashboard.recently_done, _format_done),
    ]
    return "\n\n".join(sections)


def format_pinned_dashboard(
    dashboard: TodoDashboard,
    updated_at: datetime,
    local_timezone: ZoneInfo,
) -> str:
    return "\n".join(
        (
            format_dashboard(dashboard),
            "\n<code>/todo paint walls</code>, <code>/doing id</code>, <code>/done id</code>",
            f"<i>Freshly updated: {format_local_time(updated_at, local_timezone)}</i>",
        )
    )


def _format_section(
    title: str, tasks: list[Todo], formatter: Callable[[Todo], str]
) -> str:
    lines = [f"<b>{title}</b>"]
    lines.extend(formatter(todo) for todo in tasks)
    if not tasks:
        lines.append("— all clear ♡")
    return "\n".join(lines)


def _format_pending(todo: Todo) -> str:
    return f"  {escape(todo.description)} <code>#{todo.id}</code>"


def _format_in_progress(todo: Todo) -> str:
    actor = user_link(todo.taken_by) if todo.taken_by else "a mystery kitty"
    return f"  {escape(todo.description)} <code>#{todo.id}</code> — {actor}"


def _format_done(todo: Todo) -> str:
    actor = user_link(todo.done_by) if todo.done_by else "a mystery kitty"
    return f"  <s>{escape(todo.description)}</s> <code>#{todo.id}</code> — {actor}"
