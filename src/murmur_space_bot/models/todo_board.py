from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from murmur_space_bot.models.base import Base, utc_now


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
