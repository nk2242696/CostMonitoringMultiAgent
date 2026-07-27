"""Reusable LangGraph topology for chat and background FinOps reviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Send

from src.agents.state import AgentState

AgentNode = Callable[[AgentState], Awaitable[dict]]
EVIDENCE_PERSONAS = frozenset({"cost_analyst", "cloud_architect"})


@dataclass(frozen=True)
class AgentGraphNodes:
    intake: AgentNode
    cost_analyst: AgentNode
    cloud_architect: AgentNode
    validate_evidence: AgentNode
    optimize: AgentNode
    review_governance: AgentNode
    communicate: AgentNode
    finalize: AgentNode


def _specialist_input(
    state: AgentState, persona: str, *, refinement: bool = False
) -> AgentState:
    """Create an isolated fan-out payload without duplicating reduced lists."""
    return AgentState(
        run_id=state.get("run_id", ""),
        thread_id=state.get("thread_id", ""),
        workflow_kind=state.get("workflow_kind", "chat"),
        actor_id=state.get("actor_id", ""),
        request_id=state.get("request_id", ""),
        messages=state.get("messages", []),
        scope=state.get("scope", {}),
        plan=state.get("plan", {}),
        active_persona=persona,
        refinement_count=state.get("refinement_count", 0) + (1 if refinement else 0),
    )


def _route_specialists(state: AgentState) -> list[Send]:
    selected = state.get("selected_personas", [])
    allowed = [name for name in selected if name in EVIDENCE_PERSONAS]
    if not allowed:
        allowed = ["cost_analyst"]
    return [Send("evidence_specialist", _specialist_input(state, name)) for name in allowed]


def _route_after_governance(state: AgentState, max_refinement_rounds: int):
    verdict = state.get("governance_verdict", {})
    requested = [
        name for name in verdict.get("refinement_personas", [])
        if name in EVIDENCE_PERSONAS
    ]
    if requested and state.get("refinement_count", 0) < max_refinement_rounds:
        return [
            Send("evidence_specialist", _specialist_input(state, name, refinement=True))
            for name in requested
        ]
    return "communicate"


def build_agent_graph(
    nodes: AgentGraphNodes,
    *,
    max_refinement_rounds: int = 2,
    checkpointer=None,
):
    """Compile the policy-shaped graph with optional durable checkpointing."""

    async def evidence_specialist(state: AgentState) -> dict:
        persona = state.get("active_persona")
        if persona == "cost_analyst":
            return await nodes.cost_analyst(state)
        if persona == "cloud_architect":
            return await nodes.cloud_architect(state)
        return {"errors": [{"category": "routing", "message": "Unknown specialist"}]}

    graph = StateGraph(AgentState)
    graph.add_node("intake", nodes.intake)
    graph.add_node("evidence_specialist", evidence_specialist)
    graph.add_node("validate_evidence", nodes.validate_evidence)
    graph.add_node("optimize", nodes.optimize)
    graph.add_node("review_governance", nodes.review_governance)
    graph.add_node("communicate", nodes.communicate)
    graph.add_node("finalize", nodes.finalize)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", _route_specialists, ["evidence_specialist"])
    graph.add_edge("evidence_specialist", "validate_evidence")
    graph.add_edge("validate_evidence", "optimize")
    graph.add_edge("optimize", "review_governance")
    graph.add_conditional_edges(
        "review_governance",
        lambda state: _route_after_governance(state, max_refinement_rounds),
        ["evidence_specialist", "communicate"],
    )
    graph.add_edge("communicate", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)