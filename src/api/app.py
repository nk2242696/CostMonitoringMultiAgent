"""Canonical FastAPI entry point for Azure cost monitoring."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest
from sqlalchemy import func, text

from src.api.exceptions import register_exception_handlers
from src.api.middleware import register_middleware
from src.api.routers import agents, alerts, chat, costs, forecasts, recommendations, spark
from src.common.config import get_config
from src.common.database import close_db, get_database
from src.models import AIRecommendation, AgentRun, CostAlert, CostRecord

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage process resources; Alembic owns schema migrations."""
    logger.info("Azure Cost Monitoring API starting")
    runtime_config = get_config()  # Fail fast on invalid application configuration.
    checkpoint_manager = None
    if runtime_config.agents.agent_runtime_enabled:
        from src.agents.checkpoints import AgentCheckpointManager

        checkpoint_manager = AgentCheckpointManager(runtime_config.database.url)
        app.state.agent_checkpointer = await checkpoint_manager.start()
    else:
        app.state.agent_checkpointer = None
    yield
    if checkpoint_manager is not None:
        await checkpoint_manager.close()
    close_db()
    logger.info("Azure Cost Monitoring API stopped")


config = get_config()
app = FastAPI(
    title=config.api.title,
    description=config.api.description,
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=bool(config.api.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
register_middleware(app, enable_rate_limit=True, rate_limit_capacity=120)
register_exception_handlers(app)

app.include_router(costs.router)
app.include_router(alerts.router)
app.include_router(forecasts.router)
app.include_router(recommendations.router)
app.include_router(spark.router)
app.include_router(chat.router)
app.include_router(agents.router)


@app.get("/health", tags=["Health"])
def health():
    """Return safe component status without exposing configuration secrets."""
    result = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "agent_runtime": "enabled" if config.agents.agent_runtime_enabled else "disabled",
    }
    try:
        with get_database().get_session() as session:
            session.execute(text("SELECT 1"))
        result["database"] = "connected"
    except Exception:
        logger.exception("Database health check failed")
        result["status"] = "degraded"
        result["database"] = "unavailable"
    return result


@app.get("/health/ready", tags=["Health"])
def readiness():
    """Report readiness only after the migrated database is queryable."""
    with get_database().get_session() as session:
        session.execute(text("SELECT 1"))
        session.execute(text("SELECT version_num FROM alembic_version"))
    return {"status": "ready", "database": "migrated"}


@app.get("/health/live", tags=["Health"])
def liveness():
    return {"status": "alive"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Build a fresh registry so repeated scrapes do not duplicate collectors."""
    registry = CollectorRegistry()
    total_cost = Gauge("azure_total_cost", "Total Azure cost (last 30d)", registry=registry)
    by_service = Gauge(
        "azure_cost_by_service", "Cost by service", ["service_name"], registry=registry
    )
    by_subscription = Gauge(
        "azure_cost_by_subscription",
        "Cost by subscription",
        ["subscription_id"],
        registry=registry,
    )
    records = Gauge("azure_cost_records_total", "Total cost records", registry=registry)
    active_alerts = Gauge("azure_active_alerts", "Active alert count", registry=registry)
    pending_recommendations = Gauge(
        "azure_pending_recommendations", "Pending recommendation count", registry=registry
    )
    potential_savings = Gauge(
        "azure_potential_savings", "Potential savings", registry=registry
    )
    agent_runs = Gauge(
        "finops_agent_runs", "Durable agent runs", ["workflow", "status"], registry=registry
    )
    agent_model_calls = Gauge(
        "finops_agent_model_calls", "Persisted agent model calls", registry=registry
    )
    agent_tool_calls = Gauge(
        "finops_agent_tool_calls", "Persisted agent tool calls", registry=registry
    )

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        with get_database().get_session() as session:
            total_cost.set(
                float(
                    session.query(func.sum(CostRecord.cost))
                    .filter(CostRecord.date >= cutoff)
                    .scalar()
                    or 0
                )
            )
            records.set(session.query(func.count(CostRecord.id)).scalar() or 0)

            service_rows = (
                session.query(CostRecord.service_name, func.sum(CostRecord.cost).label("cost"))
                .filter(CostRecord.date >= cutoff)
                .group_by(CostRecord.service_name)
                .all()
            )
            for row in service_rows:
                by_service.labels(service_name=row.service_name).set(float(row.cost))

            subscription_rows = (
                session.query(
                    CostRecord.subscription_id, func.sum(CostRecord.cost).label("cost")
                )
                .filter(CostRecord.date >= cutoff)
                .group_by(CostRecord.subscription_id)
                .all()
            )
            for row in subscription_rows:
                by_subscription.labels(subscription_id=row.subscription_id).set(float(row.cost))

            active_alerts.set(
                session.query(func.count(CostAlert.id))
                .filter(CostAlert.status == "active")
                .scalar()
                or 0
            )
            pending_recommendations.set(
                session.query(func.count(AIRecommendation.id))
                .filter(AIRecommendation.status == "pending")
                .scalar()
                or 0
            )
            potential_savings.set(
                float(
                    session.query(func.sum(AIRecommendation.potential_savings))
                    .filter(AIRecommendation.status.in_(["pending", "approved"]))
                    .scalar()
                    or 0
                )
            )
            run_rows = session.query(
                AgentRun.workflow_kind,
                AgentRun.status,
                func.count(AgentRun.id).label("count"),
            ).group_by(AgentRun.workflow_kind, AgentRun.status).all()
            for row in run_rows:
                agent_runs.labels(
                    workflow=row.workflow_kind, status=row.status
                ).set(row.count)
            usage_rows = session.query(AgentRun.usage).all()
            agent_model_calls.set(sum(int((row.usage or {}).get("model_calls", 0)) for row in usage_rows))
            agent_tool_calls.set(sum(int((row.usage or {}).get("tool_calls", 0)) for row in usage_rows))
    except Exception:
        logger.exception("Prometheus metric collection failed")

    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
