from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.adapters.telegram.formatting import format_user
from murmur_space_bot.models.user import User, UserTier
from murmur_space_bot.services.errors import ServiceError
from murmur_space_bot.services.users import UserService

router = Router(name="users")


@router.message(Command("user"))
async def user_command(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User,
    db_replied_user: User | None = None,
) -> None:
    service = UserService(session)
    args = (command.args or "").split()

    try:
        if not args:
            await message.answer(format_user(db_user))
            return

        action = args[0].lower()
        if action == "resident":
            if len(args) != 2:
                await message.answer("Usage: /user resident &lt;username|telegram-id&gt;")
                return
            target = await service.resolve_user(args[1])
            await service.change_tier(actor=db_user, target=target, tier=UserTier.RESIDENT)
        elif action == "guest":
            if len(args) != 1 or db_replied_user is None:
                await message.answer("Reply to a user's message with /user guest")
                return
            target = db_replied_user
            await service.change_tier(actor=db_user, target=target, tier=UserTier.GUEST)
        else:
            await message.answer(
                "Usage: /user [resident &lt;username|telegram-id&gt;|guest in reply]"
            )
            return
    except ServiceError as exc:
        await message.answer(str(exc))
        return

    await message.answer(format_user(target))
