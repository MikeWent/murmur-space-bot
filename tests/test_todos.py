from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.models.todo import TodoStatus
from murmur_space_bot.services.errors import InvalidTodoStateError, TodoNotFoundError
from murmur_space_bot.services.todos import TodoConfirmationStore, TodoService
from murmur_space_bot.services.users import UserService


async def make_user(session: AsyncSession, telegram_id: int, username: str):
    return await UserService(session).sync_telegram_user(
        telegram_id=telegram_id,
        username=username,
        first_name=username,
        last_name=None,
    )


async def test_task_lifecycle_and_attribution(session: AsyncSession) -> None:
    creator = await make_user(session, 1, "creator")
    finisher = await make_user(session, 3, "finisher")
    confirmations = TodoConfirmationStore()
    service = TodoService(session, confirmations)

    todo = await service.create_task("Fix the lamp", creator)
    assert todo.id == 1
    assert todo.status is TodoStatus.PENDING
    assert todo.created_by is creator

    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
    first = await service.press_task(todo.id, finisher, pressed_at=now)
    second = await service.press_task(
        todo.id, finisher, pressed_at=now + timedelta(seconds=1)
    )
    assert not first.completed
    assert second.completed
    assert second.todo.status is TodoStatus.DONE
    assert second.todo.done_by is finisher


async def test_same_person_must_press_twice_to_complete(session: AsyncSession) -> None:
    user = await make_user(session, 1, "worker")
    other = await make_user(session, 2, "other")
    confirmations = TodoConfirmationStore()
    service = TodoService(session, confirmations)
    todo = await service.create_task("Task", user)
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)

    first = await service.press_task(todo.id, user, pressed_at=now)
    other_first = await service.press_task(todo.id, other, pressed_at=now)
    second = await service.press_task(
        todo.id, user, pressed_at=now + timedelta(seconds=1)
    )
    assert not first.completed
    assert not other_first.completed
    assert second.completed
    assert second.todo.done_by is user


async def test_invalid_task_transitions(session: AsyncSession) -> None:
    first_user = await make_user(session, 1, "first")
    second_user = await make_user(session, 2, "second")
    service = TodoService(session)
    todo = await service.create_task("Task", first_user)

    await service.complete_task(todo.id, second_user)
    with pytest.raises(InvalidTodoStateError):
        await service.complete_task(todo.id, first_user)
    with pytest.raises(TodoNotFoundError):
        await service.press_task(999, first_user)


async def test_dashboard_groups_tasks_and_limits_recent_done(
    session: AsyncSession,
) -> None:
    user = await make_user(session, 1, "worker")
    service = TodoService(session)
    pending = await service.create_task("Pending", user)
    done_one = await service.create_task("Done one", user)
    done_two = await service.create_task("Done two", user)

    await service.complete_task(done_one.id, user)
    await service.complete_task(done_two.id, user)
    dashboard = await service.get_dashboard(done_limit=1)

    assert [task.id for task in dashboard.pending] == [pending.id]
    assert [task.id for task in dashboard.recently_done] == [done_two.id]


async def test_confirmation_expires_after_thirty_seconds(
    session: AsyncSession,
) -> None:
    user = await make_user(session, 1, "worker")
    service = TodoService(session)
    todo = await service.create_task("Task", user)
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)

    assert not (await service.press_task(todo.id, user, pressed_at=now)).completed
    assert not (
        await service.press_task(
            todo.id, user, pressed_at=now + timedelta(seconds=31)
        )
    ).completed
    assert (
        await service.press_task(
            todo.id, user, pressed_at=now + timedelta(seconds=32)
        )
    ).completed


async def test_task_description_validation(session: AsyncSession) -> None:
    user = await make_user(session, 1, "creator")
    service = TodoService(session)

    with pytest.raises(InvalidTodoStateError):
        await service.create_task("   ", user)
    with pytest.raises(InvalidTodoStateError):
        await service.create_task("x" * 1001, user)
