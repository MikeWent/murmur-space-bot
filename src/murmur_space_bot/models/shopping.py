from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from murmur_space_bot.models.base import Base, utc_now
from murmur_space_bot.models.user import User


class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bought_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    bought_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    added_by: Mapped[User] = relationship(foreign_keys=[added_by_id], lazy="raise")
    bought_by: Mapped[User | None] = relationship(
        foreign_keys=[bought_by_id], lazy="raise"
    )


class ShoppingBoard(Base):
    __tablename__ = "shopping_boards"
    __table_args__ = (UniqueConstraint("chat_id", "topic_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    topic_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
