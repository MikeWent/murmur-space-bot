from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from murmur_space_bot.models.todo_board import TodoBoard


class TodoBoardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, chat_id: int, topic_id: int) -> TodoBoard | None:
        return await self.session.scalar(
            select(TodoBoard).where(
                TodoBoard.chat_id == chat_id,
                TodoBoard.topic_id == topic_id,
            )
        )

    async def store_message(
        self, *, chat_id: int, topic_id: int, message_id: int
    ) -> TodoBoard:
        board = await self.get(chat_id, topic_id)
        if board is None:
            board = TodoBoard(
                chat_id=chat_id,
                topic_id=topic_id,
                message_id=message_id,
            )
            self.session.add(board)
        else:
            board.message_id = message_id
        await self.session.flush()
        return board
