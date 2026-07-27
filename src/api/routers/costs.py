"""
Cost Monitoring API Endpoints

Provides cost data at multiple grains:
  - /api/v1/costs/summary       – overall summary
  - /api/v1/costs/by-subscription
  - /api/v1/costs/by-service
  - /api/v1/costs/by-resource-type
  - /api/v1/costs/trends         – daily time-series
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func as sqla_func, cast, Date
from sqlalchemy.orm import Session

from src.common.database import get_session
from src.models import CostRecord, CostAggregation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/costs", tags=["Costs"])


# ── Response schemas ──


class CostSummaryResponse(BaseModel):
    total_cost: float
    currency: str = "USD"
    resource_count: int
    subscription_count: int
    period_start: str
    period_end: str
    top_services: List[dict]
    top_subscriptions: List[dict]
    trend_pct: Optional[float] = None  # MoM change


class CostBreakdownItem(BaseModel):
    name: str
    total_cost: float
    percentage: float
    resource_count: int


class CostTrendItem(BaseModel):
    date: str
    cost: float


# ── Endpoints ──


@router.get("/summary", response_model=CostSummaryResponse)
def cost_summary(
    days: int = Query(30, ge=1, le=365),
    subscription_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Aggregated cost summary for the last N days."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    base = db.query(CostRecord).filter(CostRecord.date >= start)
    if subscription_id:
        base = base.filter(CostRecord.subscription_id == subscription_id)

    total_cost = float(
        db.query(sqla_func.sum(CostRecord.cost))
        .filter(CostRecord.date >= start)
        .scalar() or 0
    )

    resource_count = (
        db.query(sqla_func.count(sqla_func.distinct(CostRecord.resource_id)))
        .filter(CostRecord.date >= start)
        .scalar() or 0
    )

    subscription_count = (
        db.query(sqla_func.count(sqla_func.distinct(CostRecord.subscription_id)))
        .filter(CostRecord.date >= start)
        .scalar() or 0
    )

    top_services = [
        {"service": r.service_name, "cost": float(r.total)}
        for r in db.query(
            CostRecord.service_name,
            sqla_func.sum(CostRecord.cost).label("total"),
        )
        .filter(CostRecord.date >= start)
        .group_by(CostRecord.service_name)
        .order_by(desc("total"))
        .limit(10)
        .all()
    ]

    top_subs = [
        {"subscription_id": r.subscription_id, "cost": float(r.total)}
        for r in db.query(
            CostRecord.subscription_id,
            sqla_func.sum(CostRecord.cost).label("total"),
        )
        .filter(CostRecord.date >= start)
        .group_by(CostRecord.subscription_id)
        .order_by(desc("total"))
        .limit(5)
        .all()
    ]

    # MoM trend
    prev_start = start - timedelta(days=days)
    prev_cost = float(
        db.query(sqla_func.sum(CostRecord.cost))
        .filter(CostRecord.date >= prev_start, CostRecord.date < start)
        .scalar() or 0
    )
    trend_pct = ((total_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else None

    return CostSummaryResponse(
        total_cost=total_cost,
        resource_count=resource_count,
        subscription_count=subscription_count,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        top_services=top_services,
        top_subscriptions=top_subs,
        trend_pct=round(trend_pct, 2) if trend_pct is not None else None,
    )


@router.get("/by-subscription", response_model=List[CostBreakdownItem])
def costs_by_subscription(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_session),
):
    """Cost breakdown by subscription."""
    start = datetime.utcnow() - timedelta(days=days)
    total = float(db.query(sqla_func.sum(CostRecord.cost)).filter(CostRecord.date >= start).scalar() or 1)

    rows = (
        db.query(
            CostRecord.subscription_id,
            sqla_func.sum(CostRecord.cost).label("total"),
            sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("cnt"),
        )
        .filter(CostRecord.date >= start)
        .group_by(CostRecord.subscription_id)
        .order_by(desc("total"))
        .all()
    )

    return [
        CostBreakdownItem(
            name=r.subscription_id,
            total_cost=float(r.total),
            percentage=round(float(r.total) / total * 100, 2),
            resource_count=r.cnt,
        )
        for r in rows
    ]


@router.get("/by-service", response_model=List[CostBreakdownItem])
def costs_by_service(
    days: int = Query(30, ge=1, le=365),
    subscription_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Cost breakdown by Azure service type."""
    start = datetime.utcnow() - timedelta(days=days)
    q = db.query(
        CostRecord.service_name,
        sqla_func.sum(CostRecord.cost).label("total"),
        sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("cnt"),
    ).filter(CostRecord.date >= start)
    if subscription_id:
        q = q.filter(CostRecord.subscription_id == subscription_id)

    total = float(
        db.query(sqla_func.sum(CostRecord.cost)).filter(CostRecord.date >= start).scalar() or 1
    )

    rows = q.group_by(CostRecord.service_name).order_by(desc("total")).all()

    return [
        CostBreakdownItem(
            name=r.service_name,
            total_cost=float(r.total),
            percentage=round(float(r.total) / total * 100, 2),
            resource_count=r.cnt,
        )
        for r in rows
    ]


@router.get("/by-resource-type", response_model=List[CostBreakdownItem])
def costs_by_resource_type(
    days: int = Query(30, ge=1, le=365),
    subscription_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Cost breakdown by Azure resource type."""
    start = datetime.utcnow() - timedelta(days=days)
    q = db.query(
        CostRecord.resource_type,
        sqla_func.sum(CostRecord.cost).label("total"),
        sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("cnt"),
    ).filter(CostRecord.date >= start)
    if subscription_id:
        q = q.filter(CostRecord.subscription_id == subscription_id)

    total = float(
        db.query(sqla_func.sum(CostRecord.cost)).filter(CostRecord.date >= start).scalar() or 1
    )

    rows = q.group_by(CostRecord.resource_type).order_by(desc("total")).all()

    return [
        CostBreakdownItem(
            name=r.resource_type,
            total_cost=float(r.total),
            percentage=round(float(r.total) / total * 100, 2),
            resource_count=r.cnt,
        )
        for r in rows
    ]


@router.get("/trends", response_model=List[CostTrendItem])
def cost_trends(
    days: int = Query(30, ge=1, le=365),
    subscription_id: Optional[str] = None,
    service_name: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Daily cost time-series for charting."""
    start = datetime.utcnow() - timedelta(days=days)
    q = db.query(
        cast(CostRecord.date, Date).label("day"),
        sqla_func.sum(CostRecord.cost).label("total"),
    ).filter(CostRecord.date >= start)

    if subscription_id:
        q = q.filter(CostRecord.subscription_id == subscription_id)
    if service_name:
        q = q.filter(CostRecord.service_name == service_name)

    rows = q.group_by("day").order_by("day").all()

    return [
        CostTrendItem(date=str(r.day), cost=float(r.total))
        for r in rows
    ]


# ── Chargeback / Showback ──


@router.get("/chargeback")
def chargeback_report(
    tag_key: str = Query("CostCenter", description="Tag key to group by (e.g., CostCenter, Team, Department, Environment)"),
    days: int = Query(30, ge=1, le=365),
    subscription_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """
    Chargeback/showback report grouped by a tag dimension.

    Groups costs by the specified tag key (e.g., CostCenter, Team, Environment)
    and returns per-group cost allocation with percentages.

    Pricing model:
    - Direct costs: actual Azure consumption per tag group
    - Shared costs: untagged resources distributed proportionally
    - Internal rate: optional markup for platform team overhead
    """
    from sqlalchemy import text

    start = datetime.utcnow() - timedelta(days=days)

    # Costs grouped by tag value
    tagged_costs = db.execute(text("""
        SELECT
            COALESCE(tags::json->>:tag_key, 'UNTAGGED') as tag_value,
            ROUND(SUM(cost)::numeric, 2) as total_cost,
            COUNT(DISTINCT resource_id) as resource_count,
            COUNT(DISTINCT service_name) as service_count
        FROM cost_records
        WHERE date >= :start_date
            AND (:sub_id IS NULL OR subscription_id = :sub_id)
        GROUP BY tag_value
        ORDER BY total_cost DESC
    """), {
        "tag_key": tag_key,
        "start_date": start,
        "sub_id": subscription_id,
    }).fetchall()

    total_cost = sum(float(r[1]) for r in tagged_costs)
    untagged_cost = 0

    groups = []
    for row in tagged_costs:
        tag_val = row[0]
        cost = float(row[1])
        pct = round(cost / total_cost * 100, 2) if total_cost > 0 else 0

        if tag_val == "UNTAGGED":
            untagged_cost = cost

        groups.append({
            "tag_value": tag_val,
            "direct_cost": cost,
            "percentage": pct,
            "resource_count": row[2],
            "service_count": row[3],
        })

    # Distribute untagged costs proportionally (showback model)
    tagged_total = total_cost - untagged_cost
    for g in groups:
        if g["tag_value"] != "UNTAGGED" and tagged_total > 0:
            share = g["direct_cost"] / tagged_total
            g["shared_cost_allocation"] = round(untagged_cost * share, 2)
            g["total_chargeback"] = round(g["direct_cost"] + g["shared_cost_allocation"], 2)
        else:
            g["shared_cost_allocation"] = 0
            g["total_chargeback"] = g["direct_cost"]

    return {
        "tag_key": tag_key,
        "period_days": days,
        "total_cost": total_cost,
        "tagged_cost": round(tagged_total, 2),
        "untagged_cost": round(untagged_cost, 2),
        "tag_coverage_pct": round(tagged_total / total_cost * 100, 2) if total_cost > 0 else 0,
        "groups": groups,
        "pricing_model": {
            "type": "direct_plus_shared",
            "description": "Direct costs allocated by tag. Untagged costs distributed proportionally among tagged groups.",
            "internal_markup_pct": 0,
            "notes": "Set internal_markup_pct > 0 to add platform team overhead charge."
        },
    }


@router.get("/tag-compliance")
def tag_compliance(
    required_tags: str = Query("CostCenter,Environment,Owner", description="Comma-separated required tag keys"),
    days: int = Query(30, ge=1, le=365),
    subscription_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """
    Tag compliance report showing which resources are missing required tags.
    """
    from sqlalchemy import text

    start = datetime.utcnow() - timedelta(days=days)
    req_tags = [t.strip() for t in required_tags.split(",") if t.strip()]

    # Get all distinct resources with their tags and cost
    resources = db.execute(text("""
        SELECT
            resource_id,
            resource_name,
            service_name,
            resource_group,
            subscription_id,
            tags::text as tags_text,
            ROUND(SUM(cost)::numeric, 2) as total_cost
        FROM cost_records
        WHERE date >= :start_date
            AND (:sub_id IS NULL OR subscription_id = :sub_id)
            AND resource_id != ''
        GROUP BY resource_id, resource_name, service_name, resource_group, subscription_id, tags::text
        ORDER BY total_cost DESC
    """), {"start_date": start, "sub_id": subscription_id}).fetchall()

    import json
    total_resources = len(resources)
    fully_tagged = 0
    partially_tagged = 0
    untagged = 0
    total_untagged_cost = 0
    missing_breakdown = {tag: {"count": 0, "cost": 0} for tag in req_tags}
    worst_offenders = []

    for r in resources:
        try:
            tags = json.loads(r[5]) if r[5] and r[5] != '{}' else {}
        except (json.JSONDecodeError, TypeError):
            tags = {}

        cost = float(r[6])
        missing = [t for t in req_tags if t not in tags]

        if not missing:
            fully_tagged += 1
        elif len(missing) == len(req_tags):
            untagged += 1
            total_untagged_cost += cost
        else:
            partially_tagged += 1

        for m in missing:
            missing_breakdown[m]["count"] += 1
            missing_breakdown[m]["cost"] += cost

        if missing and cost > 100:
            worst_offenders.append({
                "resource_name": r[1],
                "service": r[2],
                "cost": cost,
                "missing_tags": missing,
            })

    worst_offenders.sort(key=lambda x: x["cost"], reverse=True)

    return {
        "required_tags": req_tags,
        "period_days": days,
        "total_resources": total_resources,
        "fully_compliant": fully_tagged,
        "partially_compliant": partially_tagged,
        "non_compliant": untagged,
        "compliance_pct": round(fully_tagged / total_resources * 100, 1) if total_resources > 0 else 0,
        "untagged_cost": round(total_untagged_cost, 2),
        "missing_tag_breakdown": {
            tag: {"resources_missing": v["count"], "cost_at_risk": round(v["cost"], 2)}
            for tag, v in missing_breakdown.items()
        },
        "top_non_compliant_resources": worst_offenders[:20],
    }
