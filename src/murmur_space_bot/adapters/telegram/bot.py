from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from murmur_space_bot.adapters.database import DatabaseSessionMiddleware
from murmur_space_bot.adapters.telegram import todo_handlers, user_handlers
from murmur_space_bot.adapters.telegram.todo_board import TodoBoardManager
from murmur_space_bot.adapters.telegram.user_sync import UserSyncMiddleware
from murmur_space_bot.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )


def create_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    todo_board: TodoBoardManager | None = None,
) -> Dispatcher:
    dispatcher = Dispatcher(
        settings=settings,
        todo_board=todo_board or TodoBoardManager(settings),
    )
    dispatcher.update.outer_middleware(DatabaseSessionMiddleware(session_factory))
    dispatcher.update.outer_middleware(UserSyncMiddleware(settings))
    dispatcher.include_router(user_handlers.router)
    dispatcher.include_router(todo_handlers.router)
    return dispatcher
