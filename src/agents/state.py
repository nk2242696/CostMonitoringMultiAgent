"""Serializable state and structured outputs for the agent graph."""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field


def keep_highest(left: int, right: int) -> int:
    """Merge refinement counters from parallel graph branches."""
    return left if left >= right else right


class WorkflowKind(str, Enum):
    CHAT = "chat"
    BACKGROUND_REVIEW = "background_review"


class ScopeFilters(BaseModel):
    subscription_ids: list[str] = Field(default_factory=list, max_length=50)
    start_date: str | None = None
    end_date: str | None = None


class ExecutionPlan(BaseModel):
    intent: str = Field(min_length=1, max_length=200)
    selected_personas: list[str] = Field(min_length=1, max_length=6)
    questions: list[str] = Field(default_factory=list, max_length=10)
    expected_evidence: list[str] = Field(default_factory=list, max_length=10)
    completion_criteria: list[str] = Field(default_factory=list, max_length=10)


class Evidence(BaseModel):
    evidence_id: str
    source: str
    collected_at: str
    query: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    persona: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class Proposal(BaseModel):
    title: str
    recommendation: str
    evidence_ids: list[str] = Field(min_length=1)
    potential_monthly_savings: float | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)
    risks: list[str] = Field(default_factory=list)
    requires_human_approval: Literal[True] = True


class GovernanceVerdict(BaseModel):
    approved_for_proposal: bool
    requires_human_approval: Literal[True] = True
    concerns: list[str] = Field(default_factory=list)
    refinement_personas: list[str] = Field(default_factory=list)


class FinalResponse(BaseModel):
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class UsageTotals(BaseModel):
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class AgentState(TypedDict, total=False):
    run_id: str
    thread_id: str
    workflow_kind: str
    actor_id: str
    request_id: str
    messages: list[dict[str, str]]
    scope: dict[str, Any]
    plan: dict[str, Any]
    selected_personas: list[str]
    active_persona: str
    evidence: Annotated[list[dict[str, Any]], operator.add]
    findings: Annotated[list[dict[str, Any]], operator.add]
    conflicts: Annotated[list[str], operator.add]
    proposals: Annotated[list[dict[str, Any]], operator.add]
    governance_verdict: dict[str, Any]
    final_response: dict[str, Any]
    usage: dict[str, int]
    refinement_count: Annotated[int, keep_highest]
    status: str
    errors: Annotated[list[dict[str, str]], operator.add]