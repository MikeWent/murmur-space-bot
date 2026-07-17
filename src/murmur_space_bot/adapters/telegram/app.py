from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from murmur_space_bot.adapters.database import DatabaseSessionMiddleware
from murmur_space_bot.adapters.telegram.menu.router import router as menu_router
from murmur_space_bot.adapters.telegram.middleware.user_sync import UserSyncMiddleware
from murmur_space_bot.adapters.telegram.shopping.board import ShoppingBoardManager
from murmur_space_bot.adapters.telegram.shopping.router import router as shopping_router
from murmur_space_bot.adapters.telegram.todos.board import TodoBoardManager
from murmur_space_bot.adapters.telegram.todos.router import router as todo_router
from murmur_space_bot.adapters.telegram.users.router import router as user_router
from murmur_space_bot.config import Settings
from murmur_space_bot.services.shopping import ShoppingConfirmationStore


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
    shopping_board: ShoppingBoardManager | None = None,
    shopping_confirmations: ShoppingConfirmationStore | None = None,
) -> Dispatcher:
    dispatcher = Dispatcher(
        settings=settings,
        todo_board=todo_board or TodoBoardManager(settings),
        shopping_board=shopping_board or ShoppingBoardManager(settings),
        shopping_confirmations=(
            shopping_confirmations or ShoppingConfirmationStore()
        ),
    )
    dispatcher.update.outer_middleware(DatabaseSessionMiddleware(session_factory))
    dispatcher.update.outer_middleware(UserSyncMiddleware(settings))
    dispatcher.include_router(user_router)
    dispatcher.include_router(todo_router)
    dispatcher.include_router(shopping_router)
    dispatcher.include_router(menu_router)
    return dispatcher
