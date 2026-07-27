"""
Background Scheduler

Runs periodic tasks using APScheduler:
  - Cost data collection
  - Alert evaluation
  - Forecasting
  - Recommendation generation
"""

import logging
from datetime import datetime

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


def start_scheduler():
    """Start the background scheduler with all periodic jobs."""
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
        CronTrigger.from_crontab("0 3 * * 0"),
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
