from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.models import Base
from murmur_space_bot.services.errors import DuplicateShoppingItemError
from murmur_space_bot.services.shopping import (
    ShoppingConfirmationStore,
    ShoppingService,
)
from murmur_space_bot.services.users import UserService


async def make_user(session: AsyncSession, telegram_id: int, name: str):
    return await UserService(session).sync_telegram_user(
        telegram_id=telegram_id,
        username=name.lower(),
        first_name=name,
        last_name=None,
    )


async def test_add_and_list_items_with_attribution(session: AsyncSession) -> None:
    alice = await make_user(session, 1, "Alice")
    service = ShoppingService(session)

    item = await service.add_item("  oat   milk  ", alice)
    active = await service.get_active_items()

    assert item.name == "oat milk"
    assert active == [item]
    assert active[0].added_by is alice
    assert "shopping_confirmations" not in Base.metadata.tables


async def test_confirmation_store_is_shared_across_service_instances(
    session: AsyncSession,
) -> None:
    alice = await make_user(session, 1, "Alice")
    confirmations = ShoppingConfirmationStore()
    first_service = ShoppingService(session, confirmations)
    item = await first_service.add_item("Flour", alice)
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)

    first = await first_service.press_item(item.id, alice, pressed_at=now)
    second = await ShoppingService(session, confirmations).press_item(
        item.id,
        alice,
        pressed_at=now + timedelta(seconds=1),
    )

    assert not first.bought
    assert second.bought


async def test_active_duplicate_is_rejected_case_insensitively(
    session: AsyncSession,
) -> None:
    alice = await make_user(session, 1, "Alice")
    service = ShoppingService(session)
    await service.add_item("Oat Milk", alice)

    with pytest.raises(DuplicateShoppingItemError):
        await service.add_item("oat milk", alice)


async def test_same_person_must_press_twice_to_buy(session: AsyncSession) -> None:
    alice = await make_user(session, 1, "Alice")
    bob = await make_user(session, 2, "Bob")
    service = ShoppingService(session)
    item = await service.add_item("Coffee", alice)
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)

    first_alice = await service.press_item(item.id, alice, pressed_at=now)
    first_bob = await service.press_item(item.id, bob, pressed_at=now)
    second_alice = await service.press_item(
        item.id, alice, pressed_at=now + timedelta(seconds=10)
    )

    assert not first_alice.bought
    assert not first_bob.bought
    assert second_alice.bought
    assert second_alice.item.bought_by is alice
    assert await service.get_active_items() == []


async def test_confirmation_expires_after_thirty_seconds(
    session: AsyncSession,
) -> None:
    alice = await make_user(session, 1, "Alice")
    service = ShoppingService(session)
    item = await service.add_item("Tea", alice)
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)

    assert not (await service.press_item(item.id, alice, pressed_at=now)).bought
    assert not (
        await service.press_item(
            item.id, alice, pressed_at=now + timedelta(seconds=31)
        )
    ).bought
    assert (
        await service.press_item(
            item.id, alice, pressed_at=now + timedelta(seconds=32)
        )
    ).bought


async def test_bought_item_can_be_added_again(session: AsyncSession) -> None:
    alice = await make_user(session, 1, "Alice")
    service = ShoppingService(session)
    first = await service.add_item("Apples", alice)
    now = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
    await service.press_item(first.id, alice, pressed_at=now)
    await service.press_item(
        first.id, alice, pressed_at=now + timedelta(seconds=1)
    )

    second = await service.add_item("Apples", alice)
    assert second.id != first.id
