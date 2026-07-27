"""
AI Recommendations API Endpoints (All 3 Tiers)

  - /api/v1/recommendations           – list / filter
  - /api/v1/recommendations/summary   – stats
  - /api/v1/recommendations/{id}      – get / update status
  - /api/v1/recommendations/generate  – trigger Tier 1 gap analysis
  - /api/v1/recommendations/{id}/script – Tier 2 automation script
  - /api/v1/recommendations/{id}/approve – approval workflow
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func as sqla_func
from sqlalchemy.orm import Session

from src.common.database import get_session
from src.models import AIRecommendation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/recommendations", tags=["Recommendations"])


# ── Response schemas ──


class RecommendationResponse(BaseModel):
    id: int
    recommendation_id: str
    tier: int
    source: str
    category: str
    title: str
    recommendation_text: str
    service_name: Optional[str]
    current_cost: Optional[float]
    potential_savings: Optional[float]
    savings_percentage: Optional[float]
    priority: str
    confidence_score: Optional[float]
    implementation_effort: Optional[str]
    action_items: Optional[list]
    status: str
    automation_script: Optional[str]
    automation_type: Optional[str]
    generated_at: Optional[datetime]

    class Config:
        from_attributes = True


class RecommendationSummary(BaseModel):
    total: int
    total_potential_savings: float
    by_tier: Dict[str, int]
    by_priority: Dict[str, int]
    by_status: Dict[str, int]
    by_category: Dict[str, int]


# ── Endpoints ──


@router.get("", response_model=List[RecommendationResponse])
def list_recommendations(
    tier: Optional[int] = Query(None, ge=1, le=3),
    priority: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected|implemented|dismissed)$"),
    category: Optional[str] = None,
    service_name: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """List AI recommendations with filters. Supports all 3 tiers."""
    q = db.query(AIRecommendation).order_by(
        desc(AIRecommendation.potential_savings),
        desc(AIRecommendation.generated_at),
    )
    if tier:
        q = q.filter(AIRecommendation.tier == tier)
    if priority:
        q = q.filter(AIRecommendation.priority == priority)
    if status:
        q = q.filter(AIRecommendation.status == status)
    if category:
        q = q.filter(AIRecommendation.category == category)
    if service_name:
        q = q.filter(AIRecommendation.service_name == service_name)
    if source:
        q = q.filter(AIRecommendation.source == source)

    recs = q.limit(limit).all()
    return [
        RecommendationResponse(
            id=r.id,
            recommendation_id=r.recommendation_id,
            tier=r.tier,
            source=r.source,
            category=r.category,
            title=r.title,
            recommendation_text=r.recommendation_text or "",
            service_name=r.service_name,
            current_cost=float(r.current_cost) if r.current_cost else None,
            potential_savings=float(r.potential_savings) if r.potential_savings else None,
            savings_percentage=float(r.savings_percentage) if r.savings_percentage else None,
            priority=r.priority,
            confidence_score=float(r.confidence_score) if r.confidence_score else None,
            implementation_effort=r.implementation_effort,
            action_items=r.action_items,
            status=r.status,
            automation_script=r.automation_script,
            automation_type=r.automation_type,
            generated_at=r.generated_at,
        )
        for r in recs
    ]


@router.get("/summary", response_model=RecommendationSummary)
def recommendations_summary(db: Session = Depends(get_session)):
    """Summary statistics across all recommendation tiers."""
    total = db.query(sqla_func.count(AIRecommendation.id)).scalar() or 0
    total_savings = float(
        db.query(sqla_func.sum(AIRecommendation.potential_savings)).scalar() or 0
    )

    def _group_counts(column):
        rows = db.query(column, sqla_func.count(AIRecommendation.id)).group_by(column).all()
        return {str(k): v for k, v in rows if k is not None}

    return RecommendationSummary(
        total=total,
        total_potential_savings=total_savings,
        by_tier=_group_counts(AIRecommendation.tier),
        by_priority=_group_counts(AIRecommendation.priority),
        by_status=_group_counts(AIRecommendation.status),
        by_category=_group_counts(AIRecommendation.category),
    )


@router.patch("/{recommendation_id}/status")
def update_status(
    recommendation_id: str,
    status: str = Query(..., pattern="^(approved|rejected|implemented|dismissed|assigned|in_progress|completed)$"),
    notes: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Update the status of a recommendation."""
    rec = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.recommendation_id == recommendation_id)
        .first()
    )
    if not rec:
        raise HTTPException(404, "Recommendation not found")

    rec.status = status
    if notes:
        rec.notes = notes
    if status == "implemented":
        rec.implemented_at = datetime.utcnow()
    if status == "approved":
        rec.approved_at = datetime.utcnow()
    db.commit()
    return {"message": "Status updated", "recommendation_id": recommendation_id, "status": status}


@router.post("/generate")
def generate_recommendations(
    subscription_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Generate AI-powered cost optimization recommendations using GPT-4o."""
    import subprocess
    import sys

    # Run the AI generator script as a subprocess so it doesn't block the API
    result = subprocess.run(
        [sys.executable, "scripts/generate_ai_recommendations.py"],
        capture_output=True,
        text=True,
        timeout=600,
        env={**__import__("os").environ, "ENVIRONMENT": "dev"},
    )

    if result.returncode != 0:
        raise HTTPException(500, f"Generation failed: {result.stderr[-500:]}")

    # Count what was generated
    total = db.query(sqla_func.count(AIRecommendation.id)).scalar() or 0
    total_savings = float(db.query(sqla_func.sum(AIRecommendation.potential_savings)).scalar() or 0)

    return {
        "message": f"Generated {total} AI-powered recommendations using GPT-4o.",
        "total_potential_savings": total_savings,
        "source": "ai_engine (gpt-4o)",
    }


@router.post("/{recommendation_id}/approve")
def approve_recommendation(
    recommendation_id: str,
    approved_by: str = "user",
    db: Session = Depends(get_session),
):
    """Approve a recommendation and generate its automation script (Tier 2)."""
    from src.recommendations.automation.engine import AutomationEngine

    engine = AutomationEngine(db)
    if not engine.approve(recommendation_id, approved_by):
        raise HTTPException(404, "Recommendation not found")

    script = engine.generate_script(recommendation_id)
    return {
        "message": "Recommendation approved",
        "recommendation_id": recommendation_id,
        "script_generated": script is not None,
        "script_preview": (script[:500] + "...") if script and len(script) > 500 else script,
    }


@router.get("/{recommendation_id}/script")
def get_automation_script(
    recommendation_id: str,
    script_type: str = Query("azure_cli", pattern="^(azure_cli|powershell|python|terraform)$"),
    db: Session = Depends(get_session),
):
    """Get or generate the automation script for a recommendation (Tier 2)."""
    from src.recommendations.automation.engine import AutomationEngine

    rec = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.recommendation_id == recommendation_id)
        .first()
    )
    if not rec:
        raise HTTPException(404, "Recommendation not found")

    if rec.automation_script and rec.automation_type == script_type:
        return {"script": rec.automation_script, "type": rec.automation_type}

    engine = AutomationEngine(db)
    script = engine.generate_script(recommendation_id, script_type)
    if not script:
        raise HTTPException(404, "No automation template available for this recommendation")

    return {"script": script, "type": script_type}


# ── Workflow endpoints ──


class AssignRequest(BaseModel):
    assigned_to: str
    notes: Optional[str] = None


class StepCompleteRequest(BaseModel):
    completed_by: str
    actual_outcome: Optional[str] = None
    evidence_url: Optional[str] = None


@router.patch("/{recommendation_id}/assign")
def assign_recommendation(
    recommendation_id: str,
    body: AssignRequest,
    db: Session = Depends(get_session),
):
    """Assign a recommendation to a user/team for implementation."""
    rec = db.query(AIRecommendation).filter(
        AIRecommendation.recommendation_id == recommendation_id
    ).first()
    if not rec:
        raise HTTPException(404, "Recommendation not found")

    rec.status = "assigned"
    rec.approved_by = body.assigned_to
    rec.approved_at = datetime.utcnow()
    if body.notes:
        rec.notes = body.notes

    # Track assignment in metadata
    meta = rec.rec_metadata or {}
    meta["assigned_to"] = body.assigned_to
    meta["assigned_at"] = datetime.utcnow().isoformat()
    meta["workflow_status"] = "assigned"
    rec.rec_metadata = meta

    db.commit()
    return {
        "message": f"Recommendation assigned to {body.assigned_to}",
        "recommendation_id": recommendation_id,
        "status": "assigned",
    }


@router.patch("/{recommendation_id}/steps/{step_num}/complete")
def complete_step(
    recommendation_id: str,
    step_num: int,
    body: StepCompleteRequest,
    db: Session = Depends(get_session),
):
    """Mark a specific implementation step as completed."""
    rec = db.query(AIRecommendation).filter(
        AIRecommendation.recommendation_id == recommendation_id
    ).first()
    if not rec:
        raise HTTPException(404, "Recommendation not found")

    meta = rec.rec_metadata or {}
    steps = meta.get("steps_json", meta.get("steps", []))

    if not steps or step_num < 1 or step_num > len(steps):
        raise HTTPException(400, f"Invalid step number. This recommendation has {len(steps)} steps.")

    # Update step status
    step = steps[step_num - 1]
    step["step_status"] = "completed"
    step["completed_by"] = body.completed_by
    step["completed_at"] = datetime.utcnow().isoformat()
    if body.actual_outcome:
        step["actual_outcome"] = body.actual_outcome
    if body.evidence_url:
        step["evidence_url"] = body.evidence_url

    meta["steps_json"] = steps
    meta["steps"] = steps

    # Check if all steps are complete
    all_done = all(s.get("step_status") == "completed" for s in steps)
    completed_count = sum(1 for s in steps if s.get("step_status") == "completed")

    meta["workflow_status"] = "completed" if all_done else "in_progress"
    meta["steps_completed"] = completed_count
    meta["steps_total"] = len(steps)
    rec.rec_metadata = meta

    if rec.status not in ("implemented", "completed"):
        rec.status = "implemented" if all_done else "in_progress"
    if all_done:
        rec.implemented_at = datetime.utcnow()

    db.commit()
    return {
        "message": f"Step {step_num} completed by {body.completed_by}",
        "recommendation_id": recommendation_id,
        "step": step_num,
        "steps_completed": completed_count,
        "steps_total": len(steps),
        "all_complete": all_done,
        "recommendation_status": rec.status,
    }


@router.get("/{recommendation_id}/progress")
def get_progress(
    recommendation_id: str,
    db: Session = Depends(get_session),
):
    """Get implementation progress for a recommendation."""
    rec = db.query(AIRecommendation).filter(
        AIRecommendation.recommendation_id == recommendation_id
    ).first()
    if not rec:
        raise HTTPException(404, "Recommendation not found")

    meta = rec.rec_metadata or {}
    steps = meta.get("steps_json", meta.get("steps", []))
    completed = sum(1 for s in steps if s.get("step_status") == "completed")

    step_details = []
    for s in steps:
        step_details.append({
            "step_number": s.get("step_number"),
            "title": s.get("title"),
            "status": s.get("step_status", "not_started"),
            "completed_by": s.get("completed_by"),
            "completed_at": s.get("completed_at"),
            "azure_cli": s.get("azure_cli"),
            "estimated_time": s.get("estimated_time"),
            "risk": s.get("risk"),
        })

    return {
        "recommendation_id": recommendation_id,
        "title": rec.title,
        "service": rec.service_name,
        "status": rec.status,
        "assigned_to": meta.get("assigned_to"),
        "subscription_id": rec.subscription_id or "",
        "resource_id": rec.resource_id or "",
        "current_cost": float(rec.current_cost) if rec.current_cost else 0,
        "potential_savings": float(rec.potential_savings) if rec.potential_savings else 0,
        "savings_percentage": float(rec.savings_percentage) if rec.savings_percentage else 0,
        "steps_completed": completed,
        "steps_total": len(steps),
        "progress_pct": round(completed / len(steps) * 100) if steps else 0,
        "steps": step_details,
    }


@router.post("/{recommendation_id}/validate")
def validate_savings(
    recommendation_id: str,
    db: Session = Depends(get_session),
):
    """Validate actual savings by comparing cost before and after implementation."""
    from datetime import timedelta

    rec = db.query(AIRecommendation).filter(
        AIRecommendation.recommendation_id == recommendation_id
    ).first()
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    if not rec.implemented_at:
        raise HTTPException(400, "Recommendation not yet implemented — nothing to validate")

    from src.models import CostRecord
    impl_date = rec.implemented_at

    # Cost for 7 days before implementation
    before_start = impl_date - timedelta(days=14)
    before_end = impl_date - timedelta(days=1)
    cost_before = float(
        db.query(sqla_func.sum(CostRecord.cost)).filter(
            CostRecord.service_name == rec.service_name,
            CostRecord.date >= before_start,
            CostRecord.date <= before_end,
        ).scalar() or 0
    )

    # Cost for 7 days after implementation
    after_start = impl_date
    after_end = impl_date + timedelta(days=13)
    cost_after = float(
        db.query(sqla_func.sum(CostRecord.cost)).filter(
            CostRecord.service_name == rec.service_name,
            CostRecord.date >= after_start,
            CostRecord.date <= after_end,
        ).scalar() or 0
    )

    actual_savings = cost_before - cost_after
    predicted_savings = float(rec.potential_savings or 0)
    accuracy = (actual_savings / predicted_savings * 100) if predicted_savings > 0 else 0

    # Store validation result
    meta = rec.rec_metadata or {}
    meta["validation"] = {
        "validated_at": datetime.utcnow().isoformat(),
        "cost_before_14d": round(cost_before, 2),
        "cost_after_14d": round(cost_after, 2),
        "actual_savings_14d": round(actual_savings, 2),
        "predicted_monthly_savings": round(predicted_savings, 2),
        "accuracy_pct": round(accuracy, 1),
        "status": "confirmed" if actual_savings > 0 else "no_improvement",
    }
    rec.rec_metadata = meta
    rec.implementation_result = meta["validation"]

    db.commit()
    return meta["validation"]


# ── Command Execution endpoints ──


class ExecuteRequest(BaseModel):
    confirm: bool = False
    dry_run: bool = False
    executed_by: str = "user"
    custom_command: Optional[str] = None


class RevertRequest(BaseModel):
    confirm: bool = False
    executed_by: str = "user"


@router.post("/{recommendation_id}/steps/{step_num}/execute")
def execute_step(
    recommendation_id: str,
    step_num: int,
    body: ExecuteRequest,
    db: Session = Depends(get_session),
):
    """
    Execute the Azure CLI command for a recommendation step.

    Set dry_run=true to validate without running.
    Set confirm=true to actually execute (safety gate).
    """
    from src.recommendations.automation.engine import CommandExecutor

    executor = CommandExecutor(db)
    result = executor.execute(
        recommendation_id=recommendation_id,
        step_num=step_num,
        confirm=body.confirm,
        dry_run=body.dry_run,
        executed_by=body.executed_by,
        custom_command=body.custom_command,
    )

    return result


@router.post("/{recommendation_id}/steps/{step_num}/revert")
def revert_step(
    recommendation_id: str,
    step_num: int,
    body: RevertRequest,
    db: Session = Depends(get_session),
):
    """
    Execute the rollback command for a previously executed step.
    Set confirm=true to actually revert (safety gate).
    """
    from src.recommendations.automation.engine import CommandExecutor

    executor = CommandExecutor(db)
    result = executor.revert(
        recommendation_id=recommendation_id,
        step_num=step_num,
        confirm=body.confirm,
        executed_by=body.executed_by,
    )

    return result


# ── Resource Intelligence / Diagnostics ──


@router.get("/{recommendation_id}/diagnose")
def diagnose_resource(
    recommendation_id: str,
    db: Session = Depends(get_session),
):
    """
    Run Azure Monitor diagnostics for the resource in this recommendation.
    Fetches real metrics (CPU/DWU/memory), resource config (SKU, auto-pause),
    activity log, and Azure Advisor recommendations.

    Returns evidence data + all az CLI commands used so you can verify yourself.
    """
    from src.collection.resource_intelligence import ResourceIntelligence

    rec = db.query(AIRecommendation).filter(
        AIRecommendation.recommendation_id == recommendation_id
    ).first()
    if not rec:
        raise HTTPException(404, "Recommendation not found")

    # Build resource_id from cost data if not stored directly
    resource_id = rec.resource_id or ""

    # If no resource_id, try to find it from cost_records
    if not resource_id or len(resource_id) < 20:
        from src.models import CostRecord
        # Extract resource name hints from the recommendation title
        # e.g., "mantissparesuat: Optimize Azure Synapse..." -> search for "mantissparesuat"
        title_hint = (rec.title or "").split(":")[0].strip().lower()
        cost_rec = None
        if title_hint and len(title_hint) > 3:
            cost_rec = db.query(CostRecord.resource_id).filter(
                CostRecord.resource_id.ilike(f"%{title_hint}%"),
                CostRecord.resource_id.isnot(None),
                CostRecord.resource_id != "",
            ).first()
        # Fallback to service_name match
        if not cost_rec:
            cost_rec = db.query(CostRecord.resource_id).filter(
                CostRecord.service_name == rec.service_name,
                CostRecord.resource_id.isnot(None),
                CostRecord.resource_id != "",
            ).first()
        if cost_rec:
            resource_id = cost_rec[0]

    if not resource_id or len(resource_id) < 20:
        return {
            "success": False,
            "error": "No Azure resource ID found. Cannot run diagnostics.",
            "hint": "Run: az resource list --query \"[?contains(name, 'resource-name')]\" --output table",
        }

    diagnostics = ResourceIntelligence.diagnose_resource(
        resource_id=resource_id,
        resource_type=rec.resource_type,
        resource_name=rec.service_name,
        subscription_id=rec.subscription_id,
    )

    # Metrics-based analysis — all scores calculated from real data
    analysis = ResourceIntelligence.analyze_from_metrics(diagnostics)
    evidence_summary = ResourceIntelligence.generate_evidence_summary(diagnostics)

    return {
        "success": True,
        "recommendation_id": recommendation_id,
        "title": rec.title,
        "service": rec.service_name,
        "resource_id": resource_id,
        "evidence_summary": evidence_summary,
        "analysis": {
            "utilization_score": analysis["utilization_score"],
            "savings_potential_pct": analysis["savings_potential_pct"],
            "improvement_areas": analysis["improvement_areas"],
            "auto_pause_enabled": analysis["config"]["auto_pause_enabled"],
            "is_paused": analysis["config"]["is_paused"],
        },
        "commands_used": diagnostics.get("commands_used", []),
    }
