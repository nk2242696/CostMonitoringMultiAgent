"""
Azure Cost Optimization Agent — FastAPI Application

This is the main entry-point that mounts all API routers.
Replaces the monolithic src/monitoring/api/main.py.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routers import alerts, chat, costs, forecasts, recommendations, spark
from src.api.middleware import register_middleware
from src.api.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Azure Cost Optimization Agent starting …")
    # Import here to avoid circular imports at module load time
    from src.common.database import get_database
    db = get_database()
    # Ensure tables exist (safe for production — CREATE IF NOT EXISTS)
    from src.models import Base
    Base.metadata.create_all(bind=db.get_engine())
    logger.info("Database tables verified.")
    yield
    from src.common.database import close_db
    close_db()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Azure Cost Optimization Agent",
    description=(
        "Comprehensive cost monitoring, alerting, forecasting, and 3-tier AI "
        "recommendation system for Azure workloads including Spark/Databricks analysis."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom middleware & exception handlers ──
register_middleware(app, enable_rate_limit=True, rate_limit_capacity=120)
register_exception_handlers(app)

# ── Static files (chat widget, dashboards) ──
static_path = Path(__file__).parent.parent / "monitoring" / "api" / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# ── Register routers ──
app.include_router(costs.router)
app.include_router(alerts.router)
app.include_router(forecasts.router)
app.include_router(recommendations.router)
app.include_router(spark.router)
app.include_router(chat.router)


# ── Health checks ──


@app.get("/health", tags=["Health"])
async def health():
    """Enhanced health check."""
    status = {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "version": "2.0.0"}
    try:
        from src.common.database import get_database
        db = get_database()
        with db.get_session() as session:
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
        status["database"] = "connected"
    except Exception as exc:
        status["status"] = "degraded"
        status["database"] = str(exc)
    return status


@app.get("/health/ready", tags=["Health"])
async def readiness():
    return {"status": "ready"}


@app.get("/health/live", tags=["Health"])
async def liveness():
    return {"status": "alive"}


# ── Prometheus metrics endpoint ──


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Expose Prometheus metrics for scraping."""
    from fastapi.responses import Response
    from prometheus_client import (
        CollectorRegistry,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    registry = CollectorRegistry()

    g_total = Gauge("azure_total_cost", "Total Azure cost (last 30d)", registry=registry)
    g_service = Gauge("azure_cost_by_service", "Cost by service", ["service_name"], registry=registry)
    g_sub = Gauge("azure_cost_by_subscription", "Cost by subscription", ["subscription_id"], registry=registry)
    g_records = Gauge("azure_cost_records_total", "Total cost records", registry=registry)
    g_alerts = Gauge("azure_active_alerts", "Active alert count", registry=registry)
    g_recommendations = Gauge("azure_pending_recommendations", "Pending recommendations", registry=registry)
    g_potential_savings = Gauge("azure_potential_savings", "Total potential savings", registry=registry)

    try:
        from src.common.database import get_database
        from src.models import CostRecord, CostAlert, AIRecommendation
        from sqlalchemy import func as sqla_func
        from datetime import timedelta

        db = get_database()
        with db.get_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=30)

            # Total cost
            total = float(session.query(sqla_func.sum(CostRecord.cost)).filter(CostRecord.date >= cutoff).scalar() or 0)
            g_total.set(total)

            # Records count
            count = session.query(sqla_func.count(CostRecord.id)).scalar() or 0
            g_records.set(count)

            # By service
            for row in session.query(CostRecord.service_name, sqla_func.sum(CostRecord.cost).label("c")).filter(CostRecord.date >= cutoff).group_by(CostRecord.service_name).all():
                g_service.labels(service_name=row.service_name).set(float(row.c))

            # By subscription
            for row in session.query(CostRecord.subscription_id, sqla_func.sum(CostRecord.cost).label("c")).filter(CostRecord.date >= cutoff).group_by(CostRecord.subscription_id).all():
                g_sub.labels(subscription_id=row.subscription_id).set(float(row.c))

            # Active alerts
            alert_count = session.query(sqla_func.count(CostAlert.id)).filter(CostAlert.status == "active").scalar() or 0
            g_alerts.set(alert_count)

            # Pending recommendations & savings
            rec_count = session.query(sqla_func.count(AIRecommendation.id)).filter(AIRecommendation.status == "pending").scalar() or 0
            g_recommendations.set(rec_count)
            savings = float(session.query(sqla_func.sum(AIRecommendation.potential_savings)).filter(AIRecommendation.status.in_(["pending", "approved"])).scalar() or 0)
            g_potential_savings.set(savings)

    except Exception:
        logger.exception("Error collecting Prometheus metrics")

    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


# ── Backward-compatible aliases ──
# The old API served on /api/costs/summary etc. (no v1).
# Keep those working by redirecting.


@app.get("/api/costs/summary", include_in_schema=False)
def legacy_cost_summary():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/api/v1/costs/summary")


@app.get("/api/recommendations", include_in_schema=False)
def legacy_recommendations():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/api/v1/recommendations")


# ── Dashboard legacy routes ──
# The static HTML dashboards (dashboard.html, dashboard_interactive.html)
# call /costs, /stats, /budgets directly. Wire those to real data.

from fastapi import Depends, Query
from sqlalchemy.orm import Session as _Session
from src.common.database import get_session as _get_session


@app.get("/costs", tags=["Dashboard Legacy"], include_in_schema=False)
def dashboard_costs(
    days: int = Query(30, ge=1, le=365),
    db: _Session = Depends(_get_session),
):
    """Return cost data in the shape the dashboard HTML expects."""
    from datetime import timedelta
    from sqlalchemy import func as sqla_func, desc

    from src.models import CostRecord

    end = datetime.utcnow()
    start = end - timedelta(days=days)

    total_cost = float(
        db.query(sqla_func.sum(CostRecord.cost))
        .filter(CostRecord.date >= start)
        .scalar() or 0
    )

    services_q = (
        db.query(
            CostRecord.service_name,
            sqla_func.sum(CostRecord.cost).label("total_cost"),
            sqla_func.count(CostRecord.id).label("record_count"),
        )
        .filter(CostRecord.date >= start)
        .group_by(CostRecord.service_name)
        .order_by(desc("total_cost"))
        .all()
    )

    services = [
        {
            "service_name": r.service_name,
            "total_cost": float(r.total_cost),
            "record_count": r.record_count,
        }
        for r in services_q
    ]

    return {
        "total_cost": total_cost,
        "count": len(services),
        "services": services,
    }


@app.post("/costs", tags=["Dashboard Legacy"], include_in_schema=False)
def dashboard_add_cost(body: dict, db: _Session = Depends(_get_session)):
    """Add a cost record from the interactive dashboard."""
    from decimal import Decimal
    from src.models import CostRecord

    record = CostRecord(
        date=datetime.fromisoformat(body["usage_date"]) if body.get("usage_date") else datetime.utcnow(),
        subscription_id=body.get("subscription_id", "manual-entry"),
        resource_group=body.get("resource_group", "dashboard"),
        resource_id=body.get("resource_id", "manual"),
        resource_name=body.get("resource_id", "manual").split("/")[-1] if body.get("resource_id") else "manual",
        service_name=body.get("service_name", "Manual Entry"),
        resource_type=body.get("resource_type", "Manual"),
        region=body.get("region", "Unknown"),
        cost=Decimal(str(body.get("cost", 0))),
    )
    db.add(record)
    db.commit()
    return {"message": "Cost record added", "id": record.id}


@app.get("/stats", tags=["Dashboard Legacy"], include_in_schema=False)
def dashboard_stats(
    days: int = Query(30, ge=1, le=365),
    db: _Session = Depends(_get_session),
):
    """Return stats in the shape the interactive dashboard expects."""
    from datetime import timedelta
    from sqlalchemy import func as sqla_func, cast, Date

    from src.models import CostRecord

    end = datetime.utcnow()
    start = end - timedelta(days=days)

    total_records = db.query(sqla_func.count(CostRecord.id)).filter(CostRecord.date >= start).scalar() or 0
    total_cost = float(db.query(sqla_func.sum(CostRecord.cost)).filter(CostRecord.date >= start).scalar() or 0)
    avg_cost = float(db.query(sqla_func.avg(CostRecord.cost)).filter(CostRecord.date >= start).scalar() or 0)
    max_cost = float(db.query(sqla_func.max(CostRecord.cost)).filter(CostRecord.date >= start).scalar() or 0)

    # Daily costs for trend chart
    daily_rows = (
        db.query(
            cast(CostRecord.date, Date).label("day"),
            sqla_func.sum(CostRecord.cost).label("cost"),
        )
        .filter(CostRecord.date >= start)
        .group_by("day")
        .order_by(cast(CostRecord.date, Date).desc())
        .limit(30)
        .all()
    )

    daily_costs = [{"date": str(r.day), "cost": float(r.cost)} for r in daily_rows]

    return {
        "summary": {
            "total_records": total_records,
            "total_cost": round(total_cost, 2),
            "avg_cost": round(avg_cost, 2),
            "max_cost": round(max_cost, 2),
        },
        "daily_costs": daily_costs,
    }


@app.get("/budgets", tags=["Dashboard Legacy"], include_in_schema=False)
def dashboard_budgets(db: _Session = Depends(_get_session)):
    """Return budgets in the shape the interactive dashboard expects."""
    from src.models import CostBudget

    budgets = db.query(CostBudget).order_by(CostBudget.created_at.desc()).all()
    result = []
    for b in budgets:
        amount = float(b.amount or 0)
        spend = float(b.current_spend or 0)
        utilization = (spend / amount * 100) if amount > 0 else 0
        result.append({
            "id": b.id,
            "budget_id": b.budget_id,
            "name": b.name,
            "amount": amount,
            "current_spend": spend,
            "utilization": round(utilization, 1),
            "is_active": b.status == "active",
            "status": b.status,
        })

    return {"budgets": result}


@app.post("/budgets", tags=["Dashboard Legacy"], include_in_schema=False)
def dashboard_create_budget(body: dict, db: _Session = Depends(_get_session)):
    """Create a budget from the interactive dashboard."""
    import uuid
    from decimal import Decimal
    from src.models import CostBudget

    now = datetime.utcnow()
    budget = CostBudget(
        budget_id=str(uuid.uuid4()),
        name=body["name"],
        subscription_id=body.get("subscription_id", "default"),
        amount=Decimal(str(body["amount"])),
        time_grain="Monthly",
        start_date=now.replace(day=1),
        end_date=now.replace(month=12, day=31) if now.month <= 12 else now,
        alert_thresholds={"warning": (body.get("threshold_percentage", 75) / 100)},
    )
    db.add(budget)
    db.commit()
    return {"message": "Budget created", "id": budget.id, "budget_id": budget.budget_id}


@app.delete("/budgets/{budget_id}", tags=["Dashboard Legacy"], include_in_schema=False)
def dashboard_delete_budget(budget_id: int, db: _Session = Depends(_get_session)):
    """Delete a budget by primary key ID (used by interactive dashboard)."""
    from src.models import CostBudget

    budget = db.query(CostBudget).filter(CostBudget.id == budget_id).first()
    if not budget:
        from fastapi import HTTPException
        raise HTTPException(404, "Budget not found")
    db.delete(budget)
    db.commit()
    return {"message": "Budget deleted"}


# ── Serve dashboard HTML directly ──


@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    """Serve the main dashboard page."""
    from fastapi.responses import FileResponse
    html_path = Path(__file__).parent.parent / "monitoring" / "api" / "static" / "dashboard.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html")
    from fastapi import HTTPException
    raise HTTPException(404, "Dashboard not found")


@app.get("/dashboard/interactive", include_in_schema=False)
def serve_interactive_dashboard():
    """Serve the interactive dashboard page."""
    from fastapi.responses import FileResponse
    html_path = Path(__file__).parent.parent / "monitoring" / "api" / "static" / "dashboard_interactive.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html")
    from fastapi import HTTPException
    raise HTTPException(404, "Interactive dashboard not found")


@app.get("/recommendation/{recommendation_id}", include_in_schema=False)
def serve_recommendation_action(recommendation_id: str):
    """Serve the recommendation action page (execute/revert workflow)."""
    from fastapi.responses import FileResponse
    html_path = Path(__file__).parent.parent / "monitoring" / "api" / "static" / "recommendation_action.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html")
    from fastapi import HTTPException
    raise HTTPException(404, "Action page not found")


# ── Run directly ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
