"""Framework-independent ports for the agent runtime."""

from __future__ import annotations

from typing import Any, Protocol


class AgentModelFactory(Protocol):
    def create(self, *, workflow_kind: str) -> Any: ...


class AgentTool(Protocol):
    name: str
    description: str
    read_only: bool
    args_schema: type[Any]

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]: ...


class AgentRunRepository(Protocol):
    def create_run(self, run: Any) -> Any: ...

    def update_status(self, run_id: str, status: str) -> None: ...


class AgentAuditRepository(Protocol):
    def append_event(self, event: Any) -> Any: ...