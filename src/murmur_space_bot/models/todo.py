from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from murmur_space_bot.models.base import Base, utc_now
from murmur_space_bot.models.user import User


class TodoStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(1000))
    status: Mapped[TodoStatus] = mapped_column(
        Enum(TodoStatus, native_enum=False, values_callable=lambda enum: [e.value for e in enum]),
        default=TodoStatus.PENDING,
        index=True,
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    taken_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    done_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id], lazy="raise")
    taken_by: Mapped[User | None] = relationship(foreign_keys=[taken_by_id], lazy="raise")
    done_by: Mapped[User | None] = relationship(foreign_keys=[done_by_id], lazy="raise")


class TodoBoard(Base):
    __tablename__ = "todo_boards"
    __table_args__ = (UniqueConstraint("chat_id", "topic_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    topic_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
