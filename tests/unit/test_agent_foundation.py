"""Tests for the safe LangGraph runtime foundation."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.graph import AgentGraphNodes, build_agent_graph
from src.agents.checkpoints import checkpoint_connection_string
from src.agents.personas import PERSONAS
from src.agents.state import ExecutionPlan, Proposal
from src.agents.tool_loop import ToolCallLimitError, run_tool_calling_turn
from src.agents.tools import CostSummaryTool, ToolPolicy, ToolRegistry
from src.agents.tools.registry import ToolPolicyError
from src.common.config import AgentRuntimeConfig
from src.common.config import WorkspaceConfig
from src.agents.runtime import AgentBudgetExceeded, AgentRuntime
from src.integrations.llm.client import LLMSettings, create_langchain_chat_model
from src.monitoring.storage.repositories import CostRecordRepository
from tests.conftest import make_cost_record


class FakeToolCallingModel:
    def __init__(self):
        self.invocations = 0
        self.bound_tools = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages):
        self.invocations += 1
        if self.invocations == 1:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "cost_summary",
                    "args": {"lookback_days": 30, "top_n": 5},
                    "id": "call-1",
                    "type": "tool_call",
                }],
            )
        return AIMessage(content="Spend evidence collected from evidence ID ev-1.")


def _registry(db_session):
    return ToolRegistry(
        [CostSummaryTool(CostRecordRepository(db_session))],
        ToolPolicy({"cost_analyst": frozenset({"cost_summary"})}),
    )


def test_agent_runtime_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_ENABLED", raising=False)
    config = AgentRuntimeConfig()

    assert config.agent_runtime_enabled is False
    assert config.agent_max_refinement_rounds == 2
    assert config.agent_max_tool_calls == 8


def test_checkpoint_url_uses_psycopg_connection_scheme():
    assert checkpoint_connection_string(
        "postgresql+psycopg2://user:password@postgres/database"
    ) == "postgresql://user:password@postgres/database"


def test_runtime_enforces_workflow_model_budget(db_session):
    runtime = AgentRuntime(
        db_session,
        AgentRuntimeConfig(agent_max_model_calls=2),
        WorkspaceConfig(),
    )
    runtime._claim_model_call()
    runtime._claim_model_call()

    with pytest.raises(AgentBudgetExceeded, match="budget exceeded"):
        runtime._claim_model_call()


def test_all_six_personas_are_versioned():
    assert len(PERSONAS) == 6
    assert all(persona.prompt_version == "1.0.0" for persona in PERSONAS.values())


def test_structured_contracts_enforce_human_approval():
    plan = ExecutionPlan(intent="cost review", selected_personas=["cost_analyst"])
    proposal = Proposal(
        title="Review idle compute",
        recommendation="Validate utilization before resizing.",
        evidence_ids=["ev-1"],
        confidence=0.8,
        requires_human_approval=True,
    )

    assert plan.selected_personas == ["cost_analyst"]
    assert proposal.requires_human_approval is True


def test_langchain_factory_maps_azure_settings():
    settings = LLMSettings(
        provider="azure_openai",
        api_key="test-key",
        model="deployment-a",
        base_url="https://example.openai.azure.com",
        api_version="2024-12-01-preview",
    )
    with patch("langchain_openai.AzureChatOpenAI") as model_class:
        create_langchain_chat_model(settings, model_override="deployment-b")

    kwargs = model_class.call_args.kwargs
    assert kwargs["azure_deployment"] == "deployment-b"
    assert kwargs["azure_endpoint"] == settings.base_url
    assert kwargs["api_version"] == settings.api_version


@pytest.mark.asyncio
async def test_cost_tool_returns_bounded_canonical_evidence(db_session):
    db_session.add(make_cost_record(date=datetime.now(timezone.utc), cost=25.0))
    db_session.flush()

    result = await _registry(db_session).invoke(
        "cost_analyst", "cost_summary", {"lookback_days": 30, "top_n": 5}
    )

    assert result["source"] == "cost_records"
    assert result["data"]["total_cost"] == 25.0
    assert len(result["data"]["top_services"]) == 1


@pytest.mark.asyncio
async def test_cost_tool_filters_subscription_before_applying_limit(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all([
        make_cost_record(
            date=now,
            cost=25.0,
            subscription_id="subscription-a",
            service_name="Storage",
        ),
        make_cost_record(
            date=now,
            cost=100.0,
            subscription_id="subscription-b",
            service_name="Compute",
        ),
    ])
    db_session.flush()

    result = await _registry(db_session).invoke(
        "cost_analyst",
        "cost_summary",
        {"subscription_id": "subscription-a", "lookback_days": 30, "top_n": 1},
    )

    assert result["data"]["total_cost"] == 25.0
    assert result["data"]["top_services"] == [{
        "service_name": "Storage",
        "total_cost": 25.0,
        "resource_count": 1,
    }]


@pytest.mark.asyncio
async def test_tool_policy_denies_unapproved_persona(db_session):
    with pytest.raises(ToolPolicyError, match="may not invoke"):
        await _registry(db_session).invoke(
            "executive_communicator", "cost_summary", {"lookback_days": 30}
        )


@pytest.mark.asyncio
async def test_model_tool_call_is_executed_and_returned_as_evidence(db_session):
    db_session.add(make_cost_record(date=datetime.now(timezone.utc), cost=10.0))
    db_session.flush()
    model = FakeToolCallingModel()

    result = await run_tool_calling_turn(
        model=model,
        registry=_registry(db_session),
        persona="cost_analyst",
        messages=[HumanMessage(content="What did we spend?")],
        max_tool_calls=2,
    )

    assert model.invocations == 2
    assert model.bound_tools[0]["function"]["name"] == "cost_summary"
    assert result.tool_call_count == 1
    assert result.model_call_count == 2
    assert result.evidence[0]["data"]["total_cost"] == 10.0


@pytest.mark.asyncio
async def test_tool_call_budget_is_enforced(db_session):
    with pytest.raises(ToolCallLimitError, match="budget exceeded"):
        await run_tool_calling_turn(
            model=FakeToolCallingModel(),
            registry=_registry(db_session),
            persona="cost_analyst",
            messages=[HumanMessage(content="What did we spend?")],
            max_tool_calls=0,
        )


@pytest.mark.asyncio
async def test_workflow_callbacks_observe_every_model_and_tool_call(db_session):
    observed = {"models": 0, "tools": 0}

    result = await run_tool_calling_turn(
        model=FakeToolCallingModel(),
        registry=_registry(db_session),
        persona="cost_analyst",
        messages=[HumanMessage(content="What did we spend?")],
        max_tool_calls=2,
        before_model_call=lambda: observed.__setitem__("models", observed["models"] + 1),
        before_tool_call=lambda: observed.__setitem__("tools", observed["tools"] + 1),
    )

    assert observed == {"models": result.model_call_count, "tools": result.tool_call_count}


@pytest.mark.asyncio
async def test_graph_fans_out_specialists_and_governs_before_communication():
    events = []

    async def intake(state):
        events.append("intake")
        return {"selected_personas": ["cost_analyst", "cloud_architect"]}

    async def specialist(state):
        persona = state["active_persona"]
        events.append(persona)
        return {
            "evidence": [{
                "evidence_id": f"ev-{persona}",
                "source": persona,
                "collected_at": "2026-01-01T00:00:00Z",
                "query": {},
                "data": {},
            }],
            "findings": [{"persona": persona, "summary": "verified", "evidence_ids": []}],
        }

    async def validate(state):
        events.append("validate")
        assert len(state["evidence"]) == 2
        return {}

    async def optimize(state):
        events.append("optimize")
        return {"proposals": [{"title": "proposal", "requires_human_approval": True}]}

    async def govern(state):
        events.append("govern")
        return {"governance_verdict": {"approved_for_proposal": True, "refinement_personas": []}}

    async def communicate(state):
        events.append("communicate")
        assert "govern" in events
        return {"final_response": {"answer": "Governed result", "evidence_ids": []}}

    async def finalize(state):
        events.append("finalize")
        return {"status": "completed"}

    graph = build_agent_graph(AgentGraphNodes(
        intake=intake,
        cost_analyst=specialist,
        cloud_architect=specialist,
        validate_evidence=validate,
        optimize=optimize,
        review_governance=govern,
        communicate=communicate,
        finalize=finalize,
    ))
    result = await graph.ainvoke({
        "run_id": "run-1",
        "workflow_kind": "chat",
        "messages": [{"role": "user", "content": "Review cost and architecture"}],
        "evidence": [],
        "findings": [],
        "conflicts": [],
        "proposals": [],
        "errors": [],
        "refinement_count": 0,
    })

    assert result["status"] == "completed"
    assert "cost_analyst" in events
    assert "cloud_architect" in events
    assert events[-3:] == ["govern", "communicate", "finalize"]