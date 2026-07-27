"""
Background Scheduler

Runs periodic tasks using APScheduler:
  - Cost data collection
  - Alert evaluation
  - Forecasting
  - Recommendation generation
"""

import logging
import asyncio
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def _run_alert_evaluation():
    """Evaluate all alert rules and send notifications."""
    from src.alerting.rules_engine import RulesEngine
    from src.alerting.notifications import NotificationService
    from src.common.config import get_config
    from src.common.database import get_database

    logger.info("Running scheduled alert evaluation …")
    db = get_database()
    config = get_config()

    with db.get_session() as session:
        engine = RulesEngine(
            session,
            dedup_window_minutes=config.alerting.deduplication_window_minutes,
        )
        alerts = engine.evaluate_all()

        if alerts:
            notifier = NotificationService(config.alerting.notification_channels)
            for alert in alerts:
                notifier.notify(alert)
                alert.notification_sent = True
            session.commit()
            logger.info("Fired and notified %d alerts", len(alerts))


def _run_forecasting():
    """Re-run cost forecasting."""
    from src.common.database import get_database
    from src.forecasting.engine import ForecastingEngine

    logger.info("Running scheduled forecasting …")
    db = get_database()
    with db.get_session() as session:
        engine = ForecastingEngine(session)
        count = engine.forecast_all()
        engine.backfill_actuals()
        logger.info("Forecasting complete: %d rows", count)


def _run_collection():
    """Collect costs from Azure."""
    from src.collection.cost_collector import run_collection

    logger.info("Running scheduled cost collection …")
    run_collection()


def _run_recommendations():
    """Generate Tier-1 recommendations."""
    from src.common.config import get_config

    config = get_config()
    if config.agents.agent_runtime_enabled:
        asyncio.run(_run_agent_review())
        return

    from src.common.database import get_database
    from src.recommendations.architecture_reviewer import ArchitectureRecommender
    from src.models import CostRecord
    from sqlalchemy import func as sqla_func, desc

    logger.info("Running scheduled recommendation generation …")
    db = get_database()
    with db.get_session() as session:
        services = (
            session.query(
                CostRecord.subscription_id,
                CostRecord.service_name,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
            )
            .group_by(CostRecord.subscription_id, CostRecord.service_name)
            .order_by(desc("total_cost"))
            .limit(100)
            .all()
        )
        svc_list = [
            {
                "subscription_id": s.subscription_id,
                "service_name": s.service_name,
                "total_cost": float(s.total_cost),
            }
            for s in services
        ]
        recommender = ArchitectureRecommender(session)
        recs = recommender.analyse_gaps(svc_list)
        logger.info("Generated %d recommendations", len(recs))


async def _run_agent_review():
    """Run one idempotent, read-only agent review for the current ISO week."""
    from src.agents.checkpoints import AgentCheckpointManager
    from src.agents.runtime import AgentRuntime
    from src.common.config import get_config
    from src.common.database import get_database
    from src.models import AgentRun

    config = get_config()
    database = get_database()
    year, week, _ = datetime.now(timezone.utc).isocalendar()
    thread_id = f"scheduled-finops-review-{year}-W{week:02d}"

    with database.get_session() as session:
        existing = session.query(AgentRun).filter(
            AgentRun.thread_id == thread_id,
            AgentRun.workflow_kind == "background_review",
            AgentRun.status.in_(["running", "completed"]),
        ).first()
        if existing is not None:
            logger.info("Skipping duplicate scheduled agent review %s", thread_id)
            return

        checkpoint_manager = AgentCheckpointManager(config.database.url)
        checkpointer = await checkpoint_manager.start()
        try:
            runtime = AgentRuntime(
                session, config.agents, config.workspace, checkpointer=checkpointer
            )
            result = await runtime.run_background_review(
                "Review the last 30 days of Azure costs and cached architecture. "
                "Create evidence-backed proposals requiring human approval; execute nothing.",
                thread_id=thread_id,
                request_id=str(uuid.uuid4()),
            )
            logger.info(
                "Scheduled agent review completed: run=%s evidence=%d",
                result.get("run_id"), len(result.get("evidence", [])),
            )
        finally:
            await checkpoint_manager.close()


def start_scheduler():
    """Start the background scheduler with all periodic jobs."""
    from src.common.config import get_config

    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    # Cost collection: every hour
    _scheduler.add_job(
        _run_collection,
        CronTrigger.from_crontab("0 * * * *"),
        id="cost_collection",
        name="Collect Azure cost data",
        replace_existing=True,
    )

    # Alert evaluation: every 15 minutes
    _scheduler.add_job(
        _run_alert_evaluation,
        CronTrigger.from_crontab("*/15 * * * *"),
        id="alert_evaluation",
        name="Evaluate alert rules",
        replace_existing=True,
    )

    # Forecasting: daily at 02:00 UTC
    _scheduler.add_job(
        _run_forecasting,
        CronTrigger.from_crontab("0 2 * * *"),
        id="forecasting",
        name="Run cost forecasting",
        replace_existing=True,
    )

    # Recommendation generation: weekly Sunday at 03:00 UTC
    _scheduler.add_job(
        _run_recommendations,
        CronTrigger.from_crontab(get_config().agents.agent_background_schedule),
        id="recommendations",
        name="Generate Tier-1 recommendations",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Background scheduler started with %d jobs", len(_scheduler.get_jobs()))


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
