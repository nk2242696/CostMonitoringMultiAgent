"""
CLI Entry Point for the Azure Cost Optimization Agent

Replaces the ~20 one-off root-level scripts with a single CLI.

Usage:
    python -m src.cli collect               -- collect cost data from Azure
    python -m src.cli alerts evaluate       -- evaluate alert rules now
    python -m src.cli forecast              -- run forecasting engine
    python -m src.cli recommend             -- generate Tier-1 recommendations
    python -m src.cli serve                 -- start the FastAPI server
    python -m src.cli scheduler             -- start the background scheduler
    python -m src.cli db init               -- create database tables
    python -m src.cli spark analyse --run-id <ID>  -- analyse a Spark job
"""

import argparse
import logging
import signal
import sys
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cli")


def cmd_serve(args):
    """Start the FastAPI application."""
    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def cmd_collect(args):
    """Collect cost data from Azure subscriptions."""
    from src.collection.cost_collector import run_collection
    subs = args.subscriptions.split(",") if args.subscriptions else None
    run_collection(subscription_ids=subs, days=args.days)


def cmd_discover_subscriptions(args):
    """List Azure subscriptions available to the configured identity."""
    from src.collection.cost_collector import CostCollector

    subscriptions = CostCollector().discover_subscriptions()
    for subscription in subscriptions:
        print(f"{subscription['subscription_id']}\t{subscription['display_name']}\t{subscription['state']}")


def cmd_config_validate(args):
    """Load and validate application and AI configuration."""
    from src.common.config import get_config
    from src.integrations.llm.client import LLMSettings

    config = get_config()
    llm = LLMSettings.from_env()
    llm.validate()
    print(
        f"Configuration valid: environment={config.environment}, "
        f"database={config.database.host}/{config.database.database}, "
        f"llm_provider={llm.provider}"
    )


def cmd_alerts_evaluate(args):
    """Run alert rule evaluation and send notifications."""
    from src.common.database import get_database
    from src.common.config import get_config
    from src.alerting.rules_engine import RulesEngine
    from src.alerting.notifications import NotificationService

    db = get_database()
    config = get_config()
    with db.get_session() as session:
        engine = RulesEngine(session)
        alerts = engine.evaluate_all()
        if alerts:
            notifier = NotificationService(config.alerting.notification_channels)
            for alert in alerts:
                notifier.notify(alert)
                alert.notification_sent = True
            session.commit()
        print(f"✅ {len(alerts)} alert(s) fired and notified.")


def cmd_forecast(args):
    """Run cost forecasting."""
    from src.common.database import get_database
    from src.forecasting.engine import ForecastingEngine

    db = get_database()
    with db.get_session() as session:
        engine = ForecastingEngine(session, horizon_days=args.horizon)
        subs = args.subscriptions.split(",") if args.subscriptions else None
        count = engine.forecast_all(subscription_ids=subs)
        engine.backfill_actuals()
    print(f"✅ Generated {count} forecast rows.")


def cmd_recommend(args):
    """Generate Tier-1 reference architecture recommendations."""
    from src.common.database import get_database
    from src.recommendations.architecture_reviewer import ArchitectureRecommender
    from src.models import CostRecord
    from sqlalchemy import func as sqla_func, desc

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
    print(f"✅ Generated {len(recs)} Tier-1 recommendations across {len(svc_list)} services.")


def cmd_spark_analyse(args):
    """Analyse a Spark/Databricks job."""
    from src.common.database import get_database
    from src.recommendations.spark_analyzer.cost_correlator import SparkCostAnalyser

    db = get_database()
    with db.get_session() as session:
        analyser = SparkCostAnalyser(session)

        if args.plan_file:
            with open(args.plan_file) as f:
                plan = f.read()
            code = ""
            if args.code_file:
                with open(args.code_file) as f:
                    code = f.read()
            result = analyser.analyse_job(physical_plan=plan, code=code)
        else:
            result = analyser.analyse_job(job_id=args.job_id, run_id=args.run_id)

    print(f"\n🔍 Analysis Score: {result['score']}/100")
    print(f"   Issues found: {result['issues_found']}")
    for issue in result["issues"]:
        print(f"   [{issue['severity'].upper()}] {issue['title']}")
        print(f"     → {issue['suggestion'][:120]}")


def cmd_db_init(args):
    """Create all database tables."""
    from src.common.database import get_database
    from src.models import Base

    db = get_database()
    Base.metadata.create_all(bind=db.get_engine())
    print("✅ Database tables created.")


def cmd_scheduler(args):
    """Run scheduled jobs as a dedicated foreground worker."""
    from src.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    stopped = threading.Event()

    def request_shutdown(signum, frame):
        logger.info("Worker received signal %s; shutting down", signum)
        stopped.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    print("Background worker running. Press Ctrl+C to stop.")
    try:
        stopped.wait()
    finally:
        stop_scheduler()


def main():
    parser = argparse.ArgumentParser(
        prog="cost-agent",
        description="Azure Cost Optimization Agent CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # serve
    p = sub.add_parser("serve", help="Start the API server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    # collect
    p = sub.add_parser("collect", help="Collect cost data from Azure")
    p.add_argument("--subscriptions", help="Comma-separated subscription IDs")
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(func=cmd_collect)

    # discover subscriptions
    p = sub.add_parser("discover-subscriptions", help="List accessible Azure subscriptions")
    p.set_defaults(func=cmd_discover_subscriptions)

    # configuration
    p = sub.add_parser("config", help="Configuration operations")
    config_sub = p.add_subparsers(dest="config_command")
    pv = config_sub.add_parser("validate", help="Validate application configuration")
    pv.set_defaults(func=cmd_config_validate)

    # alerts
    p = sub.add_parser("alerts", help="Alert operations")
    alerts_sub = p.add_subparsers(dest="alerts_command")
    pe = alerts_sub.add_parser("evaluate", help="Evaluate alert rules now")
    pe.set_defaults(func=cmd_alerts_evaluate)

    # forecast
    p = sub.add_parser("forecast", help="Run cost forecasting")
    p.add_argument("--subscriptions", help="Comma-separated subscription IDs")
    p.add_argument("--horizon", type=int, default=90)
    p.set_defaults(func=cmd_forecast)

    # recommend
    p = sub.add_parser("recommend", help="Generate Tier-1 recommendations")
    p.set_defaults(func=cmd_recommend)

    # spark
    p = sub.add_parser("spark", help="Spark/Databricks analysis")
    spark_sub = p.add_subparsers(dest="spark_command")
    pa = spark_sub.add_parser("analyse", help="Analyse a Spark job")
    pa.add_argument("--job-id", help="Databricks job ID")
    pa.add_argument("--run-id", help="Databricks run ID")
    pa.add_argument("--plan-file", help="Path to Spark physical plan text file (offline mode)")
    pa.add_argument("--code-file", help="Path to PySpark code file (offline mode)")
    pa.set_defaults(func=cmd_spark_analyse)

    # db
    p = sub.add_parser("db", help="Database operations")
    db_sub = p.add_subparsers(dest="db_command")
    pi = db_sub.add_parser("init", help="Create database tables")
    pi.set_defaults(func=cmd_db_init)

    # scheduler
    p = sub.add_parser("scheduler", help="Start the background worker")
    p.set_defaults(func=cmd_scheduler)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
