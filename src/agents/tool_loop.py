"""Bounded model-driven tool execution shared by specialist graph nodes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from langchain_core.messages import BaseMessage, ToolMessage

from src.agents.tools.registry import ToolRegistry


class ToolCallLimitError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolTurnResult:
    response: BaseMessage
    evidence: list[dict[str, Any]]
    tool_call_count: int
    model_call_count: int


async def run_tool_calling_turn(
    *,
    model: Any,
    registry: ToolRegistry,
    persona: str,
    messages: Sequence[BaseMessage],
    max_tool_calls: int,
    before_model_call: Callable[[], None] | None = None,
    before_tool_call: Callable[[], None] | None = None,
) -> ToolTurnResult:
    """Let a model request tools, execute them through policy, then synthesize.

    The loop accepts only registered tools, persists only normalized evidence,
    and stops after the configured call budget. It never exposes a database
    session or cloud SDK to the model.
    """
    schemas = registry.schemas_for(persona)
    bound_model = model.bind_tools(schemas)
    conversation = list(messages)
    evidence: list[dict[str, Any]] = []
    calls = 0
    model_calls = 0

    while True:
        if before_model_call is not None:
            before_model_call()
        response = await bound_model.ainvoke(conversation)
        model_calls += 1
        requested_calls = getattr(response, "tool_calls", None) or []
        if not requested_calls:
            return ToolTurnResult(
                response=response,
                evidence=evidence,
                tool_call_count=calls,
                model_call_count=model_calls,
            )

        if calls + len(requested_calls) > max_tool_calls:
            raise ToolCallLimitError(f"Tool-call budget exceeded ({max_tool_calls})")

        conversation.append(response)
        for requested in requested_calls:
            if before_tool_call is not None:
                before_tool_call()
            observation = await registry.invoke(
                persona,
                requested["name"],
                requested.get("args", {}),
            )
            calls += 1
            evidence.append(observation)
            conversation.append(
                ToolMessage(
                    content=json.dumps(observation, default=str),
                    tool_call_id=requested["id"],
                    name=requested["name"],
                )
            )