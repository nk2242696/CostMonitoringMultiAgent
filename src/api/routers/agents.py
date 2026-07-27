"""Actor-scoped APIs for inspecting durable agent runs and evidence."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_api_key_owner, get_db
from src.monitoring.storage.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentRunRepository,
)

router = APIRouter(prefix="/api/v1/agents", tags=["Agent Runs"])


def _run_or_404(db: Session, run_id: str, actor_id: str):
    run = AgentRunRepository(db).get_for_actor(run_id, actor_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.get("/runs")
def list_runs(
    limit: int = 50,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_api_key_owner),
):
    runs = AgentRunRepository(db).list_for_actor(actor_id, limit)
    return [{
        "run_id": run.run_id, "thread_id": run.thread_id,
        "workflow_kind": run.workflow_kind, "status": run.status,
        "personas": run.personas or [], "usage": run.usage or {},
        "created_at": run.created_at,
    } for run in runs]


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_api_key_owner),
):
    run = _run_or_404(db, run_id, actor_id)
    return {
        "run_id": run.run_id, "thread_id": run.thread_id,
        "workflow_kind": run.workflow_kind, "status": run.status,
        "model": run.model, "personas": run.personas or [],
        "usage": run.usage or {}, "latency_ms": run.latency_ms,
        "error_category": run.error_category, "safe_error": run.safe_error,
        "started_at": run.started_at, "completed_at": run.completed_at,
    }


@router.get("/runs/{run_id}/events")
def get_run_events(
    run_id: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_api_key_owner),
):
    run = _run_or_404(db, run_id, actor_id)
    return [{
        "event_id": event.event_id, "event_type": event.event_type,
        "node_name": event.node_name, "persona": event.persona,
        "prompt_id": event.prompt_id, "prompt_version": event.prompt_version,
        "status": event.status, "duration_ms": event.duration_ms,
        "details": event.details, "created_at": event.created_at,
    } for event in AgentEventRepository(db).list_for_run(run.id)]


@router.get("/runs/{run_id}/artifacts")
def get_run_artifacts(
    run_id: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_api_key_owner),
):
    run = _run_or_404(db, run_id, actor_id)
    return [{
        "artifact_id": item.artifact_id, "artifact_type": item.artifact_type,
        "persona": item.persona, "payload": item.payload,
        "citations": item.citations,
        "requires_human_approval": item.requires_human_approval,
        "created_at": item.created_at,
    } for item in AgentArtifactRepository(db).list_for_run(run.id)]