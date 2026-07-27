"""Central tool registry and invocation-time authorization policy."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable

from src.agents.ports import AgentTool


class ToolPolicyError(PermissionError):
    pass


@dataclass(frozen=True)
class ToolPolicy:
    grants: dict[str, frozenset[str]]

    def authorize(self, persona: str, tool: AgentTool) -> None:
        if not tool.read_only:
            raise ToolPolicyError(f"Tool is not read-only: {tool.name}")
        if tool.name not in self.grants.get(persona, frozenset()):
            raise ToolPolicyError(f"Persona {persona} may not invoke {tool.name}")


class ToolRegistry:
    def __init__(self, tools: Iterable[AgentTool], policy: ToolPolicy, timeout_seconds: float = 30):
        self._tools = {tool.name: tool for tool in tools}
        self._policy = policy
        self._timeout_seconds = timeout_seconds

    def schemas_for(self, persona: str) -> list[dict[str, Any]]:
        schemas = []
        for tool in self._tools.values():
            try:
                self._policy.authorize(persona, tool)
            except ToolPolicyError:
                continue
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_schema.model_json_schema(),
                },
            })
        return schemas

    async def invoke(self, persona: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolPolicyError(f"Unknown tool: {name}")
        self._policy.authorize(persona, tool)
        validated = tool.args_schema.model_validate(arguments)
        return await asyncio.wait_for(
            tool.invoke(validated.model_dump()),
            timeout=self._timeout_seconds,
        )