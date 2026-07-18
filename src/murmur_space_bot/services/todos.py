from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from murmur_space_bot.models.base import utc_now
from murmur_space_bot.models.todo import Todo, TodoStatus
from murmur_space_bot.models.user import User
from murmur_space_bot.services.confirmations import ConfirmationStore
from murmur_space_bot.services.errors import InvalidTodoStateError, TodoNotFoundError


TODO_LOAD_OPTIONS = (
    selectinload(Todo.created_by),
    selectinload(Todo.taken_by),
    selectinload(Todo.done_by),
)


@dataclass(frozen=True, slots=True)
class TodoDashboard:
    pending: list[Todo]
    recently_done: list[Todo]


@dataclass(frozen=True, slots=True)
class TodoPressResult:
    todo: Todo
    completed: bool


class TodoConfirmationStore(ConfirmationStore):
    """Confirmation state for todo-task taps."""


class TodoService:
    def __init__(
        self,
        session: AsyncSession,
        confirmations: TodoConfirmationStore | None = None,
    ) -> None:
        self.session = session
        self.confirmations = confirmations or TodoConfirmationStore()

    async def create_task(self, description: str, creator: User) -> Todo:
        description = description.strip()
        if not description:
            raise InvalidTodoStateError("Tell me what needs doing first, nya 🐾")
        if len(description) > 1000:
            raise InvalidTodoStateError(
                "That task is a bit too fluffy—keep it under 1000 characters 🐾"
            )

        todo = Todo(
            description=description,
            created_by=creator,
            taken_by=None,
            done_by=None,
        )
        self.session.add(todo)
        await self.session.flush()
        return todo

    async def get_dashboard(self, done_limit: int = 5) -> TodoDashboard:
        pending = list(
            await self.session.scalars(
                select(Todo)
                .where(Todo.status == TodoStatus.PENDING)
                .options(*TODO_LOAD_OPTIONS)
                .order_by(Todo.created_at, Todo.id)
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
        return TodoDashboard(pending, recently_done)

    async def press_task(
        self,
        task_id: int,
        actor: User,
        *,
        pressed_at: datetime | None = None,
    ) -> TodoPressResult:
        todo = await self._get_pending(task_id)
        confirmed = await self.confirmations.arm_or_confirm(
            item_id=task_id,
            user_id=actor.id,
            pressed_at=pressed_at or utc_now(),
        )
        if not confirmed:
            return TodoPressResult(todo=todo, completed=False)

        try:
            todo = await self.complete_task(task_id, actor)
        finally:
            await self.confirmations.clear_item(task_id)
        return TodoPressResult(todo=todo, completed=True)

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

    async def _get_pending(self, task_id: int) -> Todo:
        todo = await self.session.scalar(
            select(Todo)
            .where(Todo.id == task_id, Todo.status == TodoStatus.PENDING)
            .options(*TODO_LOAD_OPTIONS)
        )
        if todo is None:
            existing = await self.session.get(Todo, task_id)
            if existing is None:
                raise TodoNotFoundError("I couldn't find that task 🐾")
            raise InvalidTodoStateError("That task is already sparkling in Done ✨")
        return todo

    async def _get_loaded(self, task_id: int, *, refresh: bool = False) -> Todo:
        statement = select(Todo).where(Todo.id == task_id).options(*TODO_LOAD_OPTIONS)
        if refresh:
            statement = statement.execution_options(populate_existing=True)
        todo = await self.session.scalar(statement)
        if todo is None:
            raise TodoNotFoundError("I couldn't find that task 🐾")
        return todo
