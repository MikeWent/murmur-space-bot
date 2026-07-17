from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from murmur_space_bot.models.base import utc_now
from murmur_space_bot.models.todo import Todo, TodoStatus
from murmur_space_bot.models.user import User
from murmur_space_bot.services.errors import InvalidTodoStateError, TodoNotFoundError


TODO_LOAD_OPTIONS = (
    selectinload(Todo.created_by),
    selectinload(Todo.taken_by),
    selectinload(Todo.done_by),
)


@dataclass(frozen=True, slots=True)
class TodoDashboard:
    pending: list[Todo]
    in_progress: list[Todo]
    recently_done: list[Todo]


class TodoService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_task(self, description: str, creator: User) -> Todo:
        description = description.strip()
        if not description:
            raise InvalidTodoStateError("Tell me what needs doing first, nya 🐾")
        if len(description) > 1000:
            raise InvalidTodoStateError(
                "That task is a bit too fluffy—keep it under 1000 characters 🐾"
            )

        todo = Todo(description=description, created_by_id=creator.id)
        self.session.add(todo)
        await self.session.flush()
        return await self._get_loaded(todo.id)

    async def get_dashboard(self, done_limit: int = 5) -> TodoDashboard:
        pending = list(
            await self.session.scalars(
                select(Todo)
                .where(Todo.status == TodoStatus.PENDING)
                .options(*TODO_LOAD_OPTIONS)
                .order_by(Todo.created_at, Todo.id)
            )
        )
        in_progress = list(
            await self.session.scalars(
                select(Todo)
                .where(Todo.status == TodoStatus.IN_PROGRESS)
                .options(*TODO_LOAD_OPTIONS)
                .order_by(Todo.started_at, Todo.id)
            )
        )
        recently_done = list(
            await self.session.scalars(
                select(Todo)
                .where(Todo.status == TodoStatus.DONE)
                .options(*TODO_LOAD_OPTIONS)
                .order_by(Todo.completed_at.desc(), Todo.id.desc())
                .limit(done_limit)
            )
        )
        return TodoDashboard(pending, in_progress, recently_done)

    async def start_task(self, task_id: int, actor: User) -> Todo:
        todo = await self.session.get(Todo, task_id)
        if todo is None:
            raise TodoNotFoundError("I couldn't find that task 🐾")
        if todo.status == TodoStatus.IN_PROGRESS and todo.taken_by_id == actor.id:
            return await self._get_loaded(task_id)
        if todo.status != TodoStatus.PENDING:
            raise InvalidTodoStateError("That task isn't ready to be claimed 🐾")

        result = await self.session.execute(
            update(Todo)
            .where(Todo.id == task_id, Todo.status == TodoStatus.PENDING)
            .values(
                status=TodoStatus.IN_PROGRESS,
                taken_by_id=actor.id,
                started_at=utc_now(),
            )
        )
        if result.rowcount != 1:
            raise InvalidTodoStateError("Another kitty just claimed that task 🐾")
        await self.session.flush()
        return await self._get_loaded(task_id, refresh=True)

    async def complete_task(self, task_id: int, actor: User) -> Todo:
        todo = await self.session.get(Todo, task_id)
        if todo is None:
            raise TodoNotFoundError("I couldn't find that task 🐾")
        if todo.status == TodoStatus.DONE:
            raise InvalidTodoStateError("That task is already sparkling in Done ✨")

        result = await self.session.execute(
            update(Todo)
            .where(Todo.id == task_id, Todo.status != TodoStatus.DONE)
            .values(
                status=TodoStatus.DONE,
                done_by_id=actor.id,
                completed_at=utc_now(),
            )
        )
        if result.rowcount != 1:
            raise InvalidTodoStateError("That task is already sparkling in Done ✨")
        await self.session.flush()
        return await self._get_loaded(task_id, refresh=True)

    async def _get_loaded(self, task_id: int, *, refresh: bool = False) -> Todo:
        statement = select(Todo).where(Todo.id == task_id).options(*TODO_LOAD_OPTIONS)
        if refresh:
            statement = statement.execution_options(populate_existing=True)
        todo = await self.session.scalar(statement)
        if todo is None:
            raise TodoNotFoundError("I couldn't find that task 🐾")
        return todo
