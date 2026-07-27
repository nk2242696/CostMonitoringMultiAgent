"""Lifecycle management for the official asynchronous PostgreSQL checkpointer."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def checkpoint_connection_string(database_url: str) -> str:
    """Convert SQLAlchemy's psycopg2 URL into a psycopg v3 connection string."""
    return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)


class AgentCheckpointManager:
    def __init__(self, database_url: str):
        self.database_url = checkpoint_connection_string(database_url)
        self._stack: AsyncExitStack | None = None
        self.saver: Any = None

    async def start(self) -> Any:
        if self.saver is not None:
            return self.saver
        stack = AsyncExitStack()
        saver = await stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(self.database_url)
        )
        await saver.setup()
        self._stack = stack
        self.saver = saver
        return saver

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self.saver = None