from __future__ import annotations

import asyncio
import logging

from aiogram.exceptions import TelegramAPIError

from murmur_space_bot.adapters.database import create_database, initialize_schema
from murmur_space_bot.adapters.telegram.bot import create_bot, create_dispatcher
from murmur_space_bot.adapters.telegram.todo_board import TodoBoardManager
from murmur_space_bot.config import Settings


async def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    engine, session_factory = create_database(settings.database_url)
    await initialize_schema(engine)
    bot = create_bot(settings)
    todo_board = TodoBoardManager(settings)
    async with session_factory() as session:
        try:
            await todo_board.refresh(bot, session)
        except TelegramAPIError:
            # A replacement message may have been sent before pinning failed.
            # Preserve its ID so the next refresh edits instead of duplicating it.
            await session.commit()
            logging.getLogger(__name__).exception(
                "Could not initialize the pinned todo dashboard"
            )
        else:
            await session.commit()

    dispatcher = create_dispatcher(settings, session_factory, todo_board)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
