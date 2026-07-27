"""
Alert & Budget Management API Endpoints

  - Budget CRUD (create, list, update, delete)
  - Alert listing, acknowledgement, resolution
  - Manual alert trigger / evaluation
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.alerting.rules_engine import RulesEngine
from src.common.database import get_session
from src.models import CostAlert, CostBudget

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Alerts & Budgets"])


# ── Request / Response schemas ──


class BudgetCreate(BaseModel):
    name: str
    subscription_id: str
    amount: float
    time_grain: str = "Monthly"
    resource_group: Optional[str] = None
    scope_type: str = "subscription"
    scope_value: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    alert_thresholds: dict = Field(default_factory=lambda: {"warning": 0.75, "critical": 0.90, "exceeded": 1.0})
    notification_channels: List[str] = Field(default_factory=lambda: ["email"])


class BudgetResponse(BaseModel):
    id: int
    budget_id: str
    name: str
    subscription_id: str
    amount: float
    currency: str
    time_grain: str
    current_spend: float
    status: str
    alert_thresholds: dict
    notification_channels: list
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    alert_id: str
    alert_type: str
    severity: str
    title: str
    description: Optional[str]
    subscription_id: Optional[str]
    current_value: Optional[float]
    threshold_value: Optional[float]
    threshold_percentage: Optional[float]
    status: str
    notification_sent: bool
    fired_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Budget endpoints ──


@router.post("/budgets", response_model=BudgetResponse, status_code=201)
def create_budget(body: BudgetCreate, db: Session = Depends(get_session)):
    """Create a new cost budget with alert thresholds."""
    now = datetime.utcnow()
    budget = CostBudget(
        budget_id=str(uuid.uuid4()),
        name=body.name,
        subscription_id=body.subscription_id,
        resource_group=body.resource_group,
        scope_type=body.scope_type,
        scope_value=body.scope_value,
        amount=body.amount,
        time_grain=body.time_grain,
        start_date=body.start_date or now.replace(day=1),
        end_date=body.end_date or now.replace(month=12, day=31),
        alert_thresholds=body.alert_thresholds,
        notification_channels=body.notification_channels,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/budgets", response_model=List[BudgetResponse])
def list_budgets(
    subscription_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """List all budgets, optionally filtered."""
    q = db.query(CostBudget)
    if subscription_id:
        q = q.filter(CostBudget.subscription_id == subscription_id)
    if status:
        q = q.filter(CostBudget.status == status)
    return q.order_by(CostBudget.created_at.desc()).all()


@router.get("/budgets/{budget_id}", response_model=BudgetResponse)
def get_budget(budget_id: str, db: Session = Depends(get_session)):
    budget = db.query(CostBudget).filter(CostBudget.budget_id == budget_id).first()
    if not budget:
        raise HTTPException(404, "Budget not found")
    return budget


@router.patch("/budgets/{budget_id}")
def update_budget(
    budget_id: str,
    amount: Optional[float] = None,
    status: Optional[str] = None,
    alert_thresholds: Optional[dict] = None,
    db: Session = Depends(get_session),
):
    """Update budget amount, status, or thresholds."""
    budget = db.query(CostBudget).filter(CostBudget.budget_id == budget_id).first()
    if not budget:
        raise HTTPException(404, "Budget not found")
    if amount is not None:
        budget.amount = amount
    if status:
        budget.status = status
    if alert_thresholds:
        budget.alert_thresholds = alert_thresholds
    db.commit()
    return {"message": "Budget updated", "budget_id": budget_id}


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(budget_id: str, db: Session = Depends(get_session)):
    budget = db.query(CostBudget).filter(CostBudget.budget_id == budget_id).first()
    if not budget:
        raise HTTPException(404, "Budget not found")
    db.delete(budget)
    db.commit()


# ── Alert endpoints ──


@router.get("/alerts", response_model=List[AlertResponse])
def list_alerts(
    status: Optional[str] = Query(None, pattern="^(active|acknowledged|resolved|suppressed)$"),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    subscription_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """List alerts with optional filters."""
    q = db.query(CostAlert)
    if status:
        q = q.filter(CostAlert.status == status)
    if severity:
        q = q.filter(CostAlert.severity == severity)
    if subscription_id:
        q = q.filter(CostAlert.subscription_id == subscription_id)
    return q.order_by(CostAlert.fired_at.desc()).limit(limit).all()


@router.patch("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = "user",
    db: Session = Depends(get_session),
):
    alert = db.query(CostAlert).filter(CostAlert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = "acknowledged"
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at = datetime.utcnow()
    db.commit()
    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_session),
):
    alert = db.query(CostAlert).filter(CostAlert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    db.commit()
    return {"message": "Alert resolved", "alert_id": alert_id}


@router.post("/alerts/evaluate")
def evaluate_alerts(db: Session = Depends(get_session)):
    """Manually trigger alert rule evaluation."""
    engine = RulesEngine(db)
    new_alerts = engine.evaluate_all()
    return {
        "message": f"Evaluated rules. {len(new_alerts)} new alert(s) fired.",
        "alerts": [
            {"alert_id": a.alert_id, "type": a.alert_type, "severity": a.severity, "title": a.title}
            for a in new_alerts
        ],
    }
