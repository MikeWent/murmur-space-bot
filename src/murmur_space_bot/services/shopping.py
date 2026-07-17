from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from murmur_space_bot.models.base import utc_now
from murmur_space_bot.models.shopping import ShoppingItem
from murmur_space_bot.models.user import User
from murmur_space_bot.services.confirmations import (
    CONFIRMATION_WINDOW,
    ConfirmationStore,
)
from murmur_space_bot.services.errors import (
    DuplicateShoppingItemError,
    InvalidShoppingItemError,
    ShoppingItemNotFoundError,
)

MAX_ITEM_LENGTH = 2000
SHOPPING_LOAD_OPTIONS = (
    selectinload(ShoppingItem.added_by),
    selectinload(ShoppingItem.bought_by),
)


@dataclass(frozen=True, slots=True)
class ShoppingPressResult:
    item: ShoppingItem
    bought: bool


class ShoppingConfirmationStore(ConfirmationStore):
    """Confirmation state for shopping-item taps."""


class ShoppingService:
    def __init__(
        self,
        session: AsyncSession,
        confirmations: ShoppingConfirmationStore | None = None,
    ) -> None:
        self.session = session
        self.confirmations = confirmations or ShoppingConfirmationStore()

    async def add_item(self, name: str, actor: User) -> ShoppingItem:
        name = " ".join(name.split())
        if not name:
            raise InvalidShoppingItemError("Tell me what to add first, nya 🐾")
        if len(name) > MAX_ITEM_LENGTH:
            raise InvalidShoppingItemError(
                f"That item is a bit too fluffy—keep it under {MAX_ITEM_LENGTH} "
                "characters 🐾"
            )

        duplicate = await self.session.scalar(
            select(ShoppingItem.id).where(
                ShoppingItem.bought_at.is_(None),
                func.lower(ShoppingItem.name) == name.lower(),
            )
        )
        if duplicate is not None:
            raise DuplicateShoppingItemError(
                "That item is already waiting on the shopping list 🛒"
            )

        item = ShoppingItem(name=name, added_by_id=actor.id)
        self.session.add(item)
        await self.session.flush()
        return await self._get_loaded(item.id)

    async def get_active_items(self) -> list[ShoppingItem]:
        return list(
            await self.session.scalars(
                select(ShoppingItem)
                .where(ShoppingItem.bought_at.is_(None))
                .options(*SHOPPING_LOAD_OPTIONS)
                .order_by(ShoppingItem.created_at, ShoppingItem.id)
            )
        )

    async def press_item(
        self,
        item_id: int,
        actor: User,
        *,
        pressed_at: datetime | None = None,
    ) -> ShoppingPressResult:
        now = pressed_at or utc_now()
        item = await self._get_active(item_id)
        confirmed = await self.confirmations.arm_or_confirm(
            item_id=item_id,
            user_id=actor.id,
            pressed_at=now,
        )
        if not confirmed:
            return ShoppingPressResult(item=item, bought=False)

        result = await self.session.execute(
            update(ShoppingItem)
            .where(ShoppingItem.id == item_id, ShoppingItem.bought_at.is_(None))
            .values(bought_by_id=actor.id, bought_at=now)
        )
        if result.rowcount != 1:
            await self.confirmations.clear_item(item_id)
            raise ShoppingItemNotFoundError(
                "That item has already left the shopping list 🐾"
            )
        await self.confirmations.clear_item(item_id)
        await self.session.flush()
        return ShoppingPressResult(
            item=await self._get_loaded(item_id, refresh=True),
            bought=True,
        )

    async def _get_active(self, item_id: int) -> ShoppingItem:
        item = await self.session.scalar(
            select(ShoppingItem)
            .where(ShoppingItem.id == item_id, ShoppingItem.bought_at.is_(None))
            .options(*SHOPPING_LOAD_OPTIONS)
        )
        if item is None:
            raise ShoppingItemNotFoundError(
                "That item has already left the shopping list 🐾"
            )
        return item

    async def _get_loaded(
        self, item_id: int, *, refresh: bool = False
    ) -> ShoppingItem:
        statement = (
            select(ShoppingItem)
            .where(ShoppingItem.id == item_id)
            .options(*SHOPPING_LOAD_OPTIONS)
        )
        if refresh:
            statement = statement.execution_options(populate_existing=True)
        item = await self.session.scalar(statement)
        if item is None:
            raise ShoppingItemNotFoundError("I couldn't find that shopping item 🐾")
        return item
