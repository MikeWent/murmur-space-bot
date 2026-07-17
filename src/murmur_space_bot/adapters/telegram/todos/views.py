from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from murmur_space_bot.adapters.telegram.common.user_links import user_link
from murmur_space_bot.models.todo import Todo
from murmur_space_bot.services.todos import TodoDashboard

TODO_CALLBACK_PREFIX = "todo:"
BUTTON_TEXT_LIMIT = 64


def format_created(todo: Todo) -> str:
    return f"🌸 Added task: <b>{escape(todo.description)}</b>"


def format_completed(todo: Todo) -> str:
    actor = user_link(todo.done_by) if todo.done_by else "a mystery kitty"
    return f"✅ Task <b>{escape(todo.description)}</b> finished by {actor}!"


def format_dashboard(dashboard: TodoDashboard) -> str:
    sections = [
        _format_section("🌸 To do", dashboard.pending, _format_pending),
        _format_section("🐾 In progress", dashboard.in_progress, _format_in_progress),
        # _format_section("✨ Done", dashboard.recently_done, _format_done),
    ]
    return "\n\n".join(
        (
            *sections,
            "<i>Tap 🐾 to start a task, then ✨ when it's finished</i>",
        )
    )


def todo_keyboard(dashboard: TodoDashboard) -> InlineKeyboardMarkup | None:
    buttons = [
        _status_button(todo, action="start", label="🐾 Start")
        for todo in dashboard.pending
    ]
    buttons.extend(
        _status_button(todo, action="done", label="✨ Finish")
        for todo in dashboard.in_progress
    )
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons])


def format_pinned_dashboard(
    dashboard: TodoDashboard,
    updated_at: datetime,
    local_timezone: ZoneInfo,
) -> str:
    return "\n".join(
        (
            format_dashboard(dashboard),
            # f"<i>Freshly updated: {format_local_time(updated_at, local_timezone)}</i>",
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
    return f"  {escape(todo.description)}"


def _format_in_progress(todo: Todo) -> str:
    actor = user_link(todo.taken_by) if todo.taken_by else "a mystery kitty"
    return f"  {escape(todo.description)} — {actor}"


def _format_done(todo: Todo) -> str:
    actor = user_link(todo.done_by) if todo.done_by else "a mystery kitty"
    return f"  <s>{escape(todo.description)}</s> — {actor}"


def _status_button(todo: Todo, *, action: str, label: str) -> InlineKeyboardButton:
    prefix = f"{label} · "
    available = BUTTON_TEXT_LIMIT - len(prefix)
    description = todo.description
    if len(description) > available:
        description = f"{description[: available - 1].rstrip()}…"
    return InlineKeyboardButton(
        text=f"{prefix}{description}",
        callback_data=f"{TODO_CALLBACK_PREFIX}{action}:{todo.id}",
    )
