from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.models.user import UserTier
from murmur_space_bot.services.errors import InsufficientTierError, UserNotFoundError
from murmur_space_bot.services.users import UserService


async def sync_user(
    session: AsyncSession,
    telegram_id: int,
    username: str,
    *,
    initial_resident_ids: frozenset[int] = frozenset(),
):
    return await UserService(session, initial_resident_ids).sync_telegram_user(
        telegram_id=telegram_id,
        username=username,
        first_name=username.title(),
        last_name=None,
    )


async def test_sync_creates_guest_and_refreshes_profile(session: AsyncSession) -> None:
    user = await sync_user(session, 10, "first")
    assert user.tier is UserTier.GUEST

    same_user = await UserService(session).sync_telegram_user(
        telegram_id=10,
        username="renamed",
        first_name="New",
        last_name="Name",
    )

    assert same_user.id == user.id
    assert same_user.username == "renamed"
    assert same_user.display_name == "New Name"


async def test_initial_resident_is_only_bootstrapped_at_creation(
    session: AsyncSession,
) -> None:
    service = UserService(session, frozenset({10}))
    user = await service.sync_telegram_user(
        telegram_id=10, username="resident", first_name="Resident", last_name=None
    )
    assert service.is_resident(user)

    user.tier = UserTier.GUEST
    await session.flush()
    await service.sync_telegram_user(
        telegram_id=10, username="resident", first_name="Resident", last_name=None
    )
    assert user.tier is UserTier.GUEST


async def test_only_resident_can_change_tiers(session: AsyncSession) -> None:
    resident = await sync_user(
        session, 10, "resident", initial_resident_ids=frozenset({10})
    )
    guest = await sync_user(session, 20, "guest")
    service = UserService(session)

    assert service.is_resident(resident)
    assert not service.is_resident(guest)

    await service.change_tier(actor=resident, target=guest, tier=UserTier.RESIDENT)
    assert guest.tier is UserTier.RESIDENT

    resident.tier = UserTier.GUEST
    with pytest.raises(InsufficientTierError):
        await service.change_tier(actor=resident, target=guest, tier=UserTier.GUEST)


async def test_resolve_user_by_username_or_telegram_id(session: AsyncSession) -> None:
    user = await sync_user(session, 123456, "CaseSensitive")
    service = UserService(session)

    assert await service.resolve_user("@casesensitive") is user
    assert await service.resolve_user("123456") is user

    with pytest.raises(UserNotFoundError):
        await service.resolve_user("@missing")

