from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.models.base import utc_now
from murmur_space_bot.models.user import User, UserTier
from murmur_space_bot.services.errors import InsufficientTierError, UserNotFoundError


class UserService:
    def __init__(
        self,
        session: AsyncSession,
        initial_resident_ids: frozenset[int] = frozenset(),
    ) -> None:
        self.session = session
        self.initial_resident_ids = initial_resident_ids

    async def sync_telegram_user(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
        seen_at: datetime | None = None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        now = seen_at or utc_now()
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                tier=(
                    UserTier.RESIDENT
                    if telegram_id in self.initial_resident_ids
                    else UserTier.GUEST
                ),
                last_seen_at=now,
            )
            self.session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.last_seen_at = now
        await self.session.flush()
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def resolve_user(self, username_or_id: str) -> User:
        value = username_or_id.strip()
        if not value:
            raise UserNotFoundError("Specify a username or Telegram ID.")

        if value.lstrip("-").isdigit():
            user = await self.get_by_telegram_id(int(value))
        else:
            username = value.removeprefix("@").lower()
            user = await self.session.scalar(
                select(User).where(func.lower(User.username) == username)
            )
        if user is None:
            raise UserNotFoundError("User was not found in the bot database.")
        return user

    def is_resident(self, user: User) -> bool:
        return user.tier == UserTier.RESIDENT

    def require_resident(self, user: User) -> None:
        if not self.is_resident(user):
            raise InsufficientTierError("Only residents can change user tiers.")

    async def change_tier(self, *, actor: User, target: User, tier: UserTier) -> User:
        self.require_resident(actor)
        target.tier = tier
        await self.session.flush()
        return target
