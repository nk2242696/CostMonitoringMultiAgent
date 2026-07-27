"""Application runtime for durable, evidence-backed LangGraph executions."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from src.agents.graph import AgentGraphNodes, build_agent_graph
from src.agents.model_factory import ConfiguredAgentModelFactory
from src.agents.personas import get_persona
from src.agents.state import (
    ExecutionPlan,
    FinalResponse,
    Finding,
    GovernanceVerdict,
    Proposal,
)
from src.agents.tool_loop import run_tool_calling_turn
from src.agents.tools import CostSummaryTool, ResourceInventoryTool, ToolPolicy, ToolRegistry
from src.common.config import AgentRuntimeConfig, WorkspaceConfig
from src.integrations.llm.client import LLMSettings
from src.models import AgentArtifact, AgentEvent, AgentMessageRecord, AgentRun
from src.monitoring.storage.repositories import CostRecordRepository


class AgentRuntimeUnavailable(RuntimeError):
    pass


class AgentBudgetExceeded(RuntimeError):
    pass


class AgentRuntime:
    """Execute the shared graph while persisting only sanitized state and evidence."""

    def __init__(
        self,
        db: Session,
        agent_config: AgentRuntimeConfig,
        workspace: WorkspaceConfig,
        *,
        checkpointer: Any = None,
        model_factory: Any = None,
    ):
        self.db = db
        self.config = agent_config
        self.workspace = workspace
        self.checkpointer = checkpointer
        self.model_factory = model_factory or ConfiguredAgentModelFactory(
            LLMSettings.from_env(), agent_config
        )
        self._model: Any = None
        self._current_run: AgentRun | None = None
        self._model_calls = 0
        self._tool_calls = 0
        policy = ToolPolicy({
            "cost_analyst": frozenset({"cost_summary"}),
            "cloud_architect": frozenset({"resource_inventory"}),
        })
        self.tools = ToolRegistry(
            [
                CostSummaryTool(CostRecordRepository(db)),
                ResourceInventoryTool(db),
            ],
            policy,
            timeout_seconds=agent_config.agent_node_timeout_seconds,
        )

    async def run_chat(
        self,
        message: str,
        *,
        thread_id: str,
        actor_id: str,
        request_id: str,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._run(
            message,
            workflow_kind="chat",
            thread_id=thread_id,
            actor_id=actor_id,
            request_id=request_id,
            scope=scope,
        )

    async def run_background_review(
        self,
        message: str,
        *,
        thread_id: str,
        actor_id: str = "scheduler",
        request_id: str,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._run(
            message,
            workflow_kind="background_review",
            thread_id=thread_id,
            actor_id=actor_id,
            request_id=request_id,
            scope=scope,
        )

    async def _run(
        self,
        message: str,
        *,
        workflow_kind: str,
        thread_id: str,
        actor_id: str,
        request_id: str,
        scope: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not self.config.agent_runtime_enabled:
            raise AgentRuntimeUnavailable("agent_runtime_unavailable: feature is disabled")
        settings = LLMSettings.from_env()
        if settings.provider == "disabled":
            raise AgentRuntimeUnavailable("agent_runtime_unavailable: LLM provider is disabled")

        run_id = str(uuid.uuid4())
        run = AgentRun(
            run_id=run_id,
            thread_id=thread_id,
            workflow_kind=workflow_kind,
            actor_id=actor_id,
            request_id=request_id,
            scope=scope or {},
            status="running",
            model=self.config.agent_chat_model or settings.model,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.flush()
        self._current_run = run
        self.db.add(AgentMessageRecord(
            message_id=str(uuid.uuid4()), agent_run_id=run.id, thread_id=thread_id,
            actor_id=actor_id, role="user", content=message, message_metadata={},
        ))
        self._event("run", "runtime", "started", {"workflow_kind": workflow_kind})
        started = time.perf_counter()

        try:
            self._model = self.model_factory.create(workflow_kind=workflow_kind)
            graph = build_agent_graph(
                self._nodes(),
                max_refinement_rounds=self.config.agent_max_refinement_rounds,
                checkpointer=self.checkpointer,
            )
            initial = cast(dict[str, Any], {
                "run_id": run_id,
                "thread_id": thread_id,
                "workflow_kind": workflow_kind,
                "actor_id": actor_id,
                "request_id": request_id,
                "messages": [{"role": "user", "content": message}],
                "scope": scope or {},
                "evidence": [], "findings": [], "conflicts": [],
                "proposals": [], "errors": [], "refinement_count": 0,
            })
            result = await asyncio.wait_for(
                graph.ainvoke(cast(Any, initial), config={"configurable": {"thread_id": thread_id}}),
                timeout=self.config.agent_workflow_timeout_seconds,
            )
            setattr(run, "status", "completed")
            setattr(run, "completed_at", datetime.now(timezone.utc))
            setattr(run, "latency_ms", int((time.perf_counter() - started) * 1000))
            setattr(run, "personas", result.get("selected_personas", []))
            setattr(run, "usage", result.get("usage", {}))
            answer = result.get("final_response", {}).get("answer", "")
            self.db.add(AgentMessageRecord(
                message_id=str(uuid.uuid4()), agent_run_id=run.id, thread_id=thread_id,
                actor_id=actor_id, role="assistant", content=answer,
                message_metadata={"ai_generated": True},
            ))
            self._persist_artifacts(result)
            self._event("run", "runtime", "completed", {"latency_ms": run.latency_ms})
            self.db.flush()
            return result
        except Exception as exc:
            setattr(run, "status", "failed")
            setattr(run, "completed_at", datetime.now(timezone.utc))
            setattr(run, "error_category", type(exc).__name__)
            setattr(run, "safe_error", "The agent workflow could not complete.")
            self._event("run", "runtime", "failed", {"error_category": type(exc).__name__})
            self.db.flush()
            raise
        finally:
            self._current_run = None

    def _nodes(self) -> AgentGraphNodes:
        return AgentGraphNodes(
            intake=self._intake,
            cost_analyst=self._cost_analyst,
            cloud_architect=self._cloud_architect,
            validate_evidence=self._validate_evidence,
            optimize=self._optimize,
            review_governance=self._govern,
            communicate=self._communicate,
            finalize=self._finalize,
        )

    async def _structured(self, persona: str, schema: type, prompt: str):
        contract = get_persona(persona)
        self._event("model", persona, "started", {
            "prompt_id": contract.prompt_id, "prompt_version": contract.prompt_version,
        })
        self._claim_model_call()
        result = await self._model.with_structured_output(schema).ainvoke([
            SystemMessage(content=contract.system_prompt),
            HumanMessage(content=prompt),
        ])
        self._event("model", persona, "completed", {"schema": schema.__name__})
        return result

    async def _intake(self, state):
        user_message = state["messages"][-1]["content"]
        plan = await self._structured(
            "finops_orchestrator", ExecutionPlan,
            f"Create a plan for this request: {user_message}. Select cost_analyst and/or cloud_architect.",
        )
        allowed = [p for p in plan.selected_personas if p in {"cost_analyst", "cloud_architect"}]
        if not allowed:
            allowed = ["cost_analyst"]
        return {"plan": plan.model_dump(), "selected_personas": allowed}

    async def _specialist(self, state, persona: str):
        contract = get_persona(persona)
        scope = state.get("scope", {})
        message = state["messages"][-1]["content"]
        result = await run_tool_calling_turn(
            model=self._model,
            registry=self.tools,
            persona=persona,
            messages=[SystemMessage(content=contract.system_prompt), HumanMessage(
                content=f"Investigate: {message}. Scope: {scope}. Request evidence using your available tool before concluding."
            )],
            max_tool_calls=self.config.agent_max_tool_calls,
            before_model_call=self._claim_model_call,
            before_tool_call=self._claim_tool_call,
        )
        evidence_ids = [item["evidence_id"] for item in result.evidence]
        finding = Finding(
            persona=persona,
            summary=str(result.response.content),
            evidence_ids=evidence_ids,
            confidence=0.75 if evidence_ids else 0.25,
        )
        self._event("specialist", persona, "completed", {
            "tool_calls": result.tool_call_count, "evidence_count": len(evidence_ids),
        })
        return {
            "evidence": result.evidence,
            "findings": [finding.model_dump()],
            "refinement_count": state.get("refinement_count", 0),
        }

    async def _cost_analyst(self, state):
        return await self._specialist(state, "cost_analyst")

    async def _cloud_architect(self, state):
        return await self._specialist(state, "cloud_architect")

    async def _validate_evidence(self, state):
        evidence_ids = {item.get("evidence_id") for item in state.get("evidence", [])}
        conflicts = [] if evidence_ids else ["No tool evidence was returned."]
        return {"conflicts": conflicts}

    async def _optimize(self, state):
        proposal = await self._structured(
            "optimization_specialist", Proposal,
            f"Create one bounded proposal from findings {state.get('findings', [])} and evidence IDs. "
            "Do not invent savings; use null when unavailable.",
        )
        return {"proposals": [proposal.model_dump()]}

    async def _govern(self, state):
        policy = self.workspace.model_dump()
        verdict = await self._structured(
            "risk_governance_reviewer", GovernanceVerdict,
            f"Review proposals {state.get('proposals', [])}; conflicts {state.get('conflicts', [])}; "
            f"workspace policy {policy}. Request refinement only from cost_analyst or cloud_architect.",
        )
        # Reserve at least one call for executive communication. A refinement
        # cycle needs a specialist call pair plus optimization and governance.
        remaining = self.config.agent_max_model_calls - self._model_calls
        refinements = verdict.refinement_personas[:1] if remaining >= 5 else []
        verdict = verdict.model_copy(update={"refinement_personas": refinements})
        return {"governance_verdict": verdict.model_dump()}

    async def _communicate(self, state):
        final = await self._structured(
            "executive_communicator", FinalResponse,
            f"Summarize only these findings {state.get('findings', [])}, proposals "
            f"{state.get('proposals', [])}, evidence IDs and governance {state.get('governance_verdict', {})}.",
        )
        return {"final_response": final.model_dump()}

    async def _finalize(self, state):
        existing = state.get("usage", {})
        return {
            "status": "completed",
            "usage": {
                **existing,
                "model_calls": self._model_calls,
                "tool_calls": self._tool_calls,
            },
        }

    def _event(self, event_type: str, node: str, status: str, details: dict[str, Any]):
        if self._current_run is None:
            return
        prompt_id = details.pop("prompt_id", None)
        prompt_version = details.pop("prompt_version", None)
        self.db.add(AgentEvent(
            event_id=str(uuid.uuid4()), agent_run_id=self._current_run.id,
            event_type=event_type, node_name=node, persona=node if node != "runtime" else None,
            prompt_id=prompt_id, prompt_version=prompt_version, status=status, details=details,
        ))

    def _claim_model_call(self) -> None:
        if self._model_calls >= self.config.agent_max_model_calls:
            raise AgentBudgetExceeded(
                f"Model-call budget exceeded ({self.config.agent_max_model_calls})"
            )
        self._model_calls += 1

    def _claim_tool_call(self) -> None:
        if self._tool_calls >= self.config.agent_max_tool_calls:
            raise AgentBudgetExceeded(
                f"Tool-call budget exceeded ({self.config.agent_max_tool_calls})"
            )
        self._tool_calls += 1

    def _persist_artifacts(self, result: dict[str, Any]) -> None:
        if self._current_run is None:
            return
        for artifact_type, key in (
            ("evidence", "evidence"), ("finding", "findings"), ("proposal", "proposals")
        ):
            for payload in result.get(key, []):
                self.db.add(AgentArtifact(
                    artifact_id=str(uuid.uuid4()), agent_run_id=self._current_run.id,
                    artifact_type=artifact_type, persona=payload.get("persona"), payload=payload,
                    citations=payload.get("evidence_ids", []),
                    requires_human_approval=bool(payload.get("requires_human_approval", False)),
                ))
        if result.get("governance_verdict"):
            self.db.add(AgentArtifact(
                artifact_id=str(uuid.uuid4()), agent_run_id=self._current_run.id,
                artifact_type="governance_verdict", payload=result["governance_verdict"],
                citations=[], requires_human_approval=True,
            ))