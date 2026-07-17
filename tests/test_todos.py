from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.models.todo import TodoStatus
from murmur_space_bot.services.errors import InvalidTodoStateError, TodoNotFoundError
from murmur_space_bot.services.todos import TodoService
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
    worker = await make_user(session, 2, "worker")
    finisher = await make_user(session, 3, "finisher")
    service = TodoService(session)

    todo = await service.create_task("Fix the lamp", creator)
    assert todo.id == 1
    assert todo.status is TodoStatus.PENDING
    assert todo.created_by is creator

    todo = await service.start_task(todo.id, worker)
    assert todo.status is TodoStatus.IN_PROGRESS
    assert todo.taken_by is worker

    todo = await service.complete_task(todo.id, finisher)
    assert todo.status is TodoStatus.DONE
    assert todo.taken_by is worker
    assert todo.done_by is finisher


async def test_start_is_idempotent_for_same_user(session: AsyncSession) -> None:
    user = await make_user(session, 1, "worker")
    service = TodoService(session)
    todo = await service.create_task("Task", user)

    first = await service.start_task(todo.id, user)
    second = await service.start_task(todo.id, user)
    assert first.id == second.id
    assert second.taken_by is user


async def test_invalid_task_transitions(session: AsyncSession) -> None:
    first_user = await make_user(session, 1, "first")
    second_user = await make_user(session, 2, "second")
    service = TodoService(session)
    todo = await service.create_task("Task", first_user)
    await service.start_task(todo.id, first_user)

    with pytest.raises(InvalidTodoStateError):
        await service.start_task(todo.id, second_user)

    await service.complete_task(todo.id, second_user)
    with pytest.raises(InvalidTodoStateError):
        await service.complete_task(todo.id, first_user)
    with pytest.raises(TodoNotFoundError):
        await service.start_task(999, first_user)


async def test_dashboard_groups_tasks_and_limits_recent_done(
    session: AsyncSession,
) -> None:
    user = await make_user(session, 1, "worker")
    service = TodoService(session)
    pending = await service.create_task("Pending", user)
    active = await service.create_task("Active", user)
    done_one = await service.create_task("Done one", user)
    done_two = await service.create_task("Done two", user)

    await service.start_task(active.id, user)
    await service.complete_task(done_one.id, user)
    await service.complete_task(done_two.id, user)
    dashboard = await service.get_dashboard(done_limit=1)

    assert [task.id for task in dashboard.pending] == [pending.id]
    assert [task.id for task in dashboard.in_progress] == [active.id]
    assert [task.id for task in dashboard.recently_done] == [done_two.id]


async def test_task_description_validation(session: AsyncSession) -> None:
    user = await make_user(session, 1, "creator")
    service = TodoService(session)

    with pytest.raises(InvalidTodoStateError):
        await service.create_task("   ", user)
    with pytest.raises(InvalidTodoStateError):
        await service.create_task("x" * 1001, user)

