"""
API Dependencies

FastAPI dependency injection providers for database sessions,
repositories, services, and configuration.
"""

import logging
from typing import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.common.database import get_database

logger = logging.getLogger(__name__)


# =========================================================================
# Database session
# =========================================================================


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the duration of a request.
    Auto-commits on success, rolls back on error, and always closes.
    """
    db = get_database()
    session = db.get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# =========================================================================
# Repository factories
# =========================================================================


def get_cost_record_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import CostRecordRepository
    return CostRecordRepository(db)


def get_aggregation_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import CostAggregationRepository
    return CostAggregationRepository(db)


def get_budget_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import CostBudgetRepository
    return CostBudgetRepository(db)


def get_alert_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import CostAlertRepository
    return CostAlertRepository(db)


def get_anomaly_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import AnomalyRepository
    return AnomalyRepository(db)


def get_forecast_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import CostForecastRepository
    return CostForecastRepository(db)


def get_resource_metadata_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import ResourceMetadataRepository
    return ResourceMetadataRepository(db)


def get_recommendation_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import AIRecommendationRepository
    return AIRecommendationRepository(db)


def get_architecture_review_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import ArchitectureReviewRepository
    return ArchitectureReviewRepository(db)


def get_spark_analysis_repo(db: Session = Depends(get_db)):
    from src.monitoring.storage.repositories import SparkJobAnalysisRepository
    return SparkJobAnalysisRepository(db)


# =========================================================================
# Service factories
# =========================================================================


def get_metrics_calculator(db: Session = Depends(get_db)):
    from src.monitoring.processors.metrics_calculator import MetricsCalculator
    return MetricsCalculator(db)


def get_anomaly_detector(db: Session = Depends(get_db)):
    from src.monitoring.processors.anomaly_detector import AnomalyDetector
    return AnomalyDetector(db)


def get_rules_engine(db: Session = Depends(get_db)):
    from src.alerting.rules_engine import RulesEngine
    return RulesEngine(db)


def get_data_normalizer():
    from src.monitoring.processors.data_normalizer import DataNormalizer
    return DataNormalizer()


# =========================================================================
# Request context
# =========================================================================


def get_request_id(request: Request) -> str:
    """Extract request ID set by RequestIdMiddleware."""
    return getattr(request.state, "request_id", "unknown")


def get_api_key_owner(request: Request) -> str:
    """Extract API key owner set by ApiKeyMiddleware."""
    return getattr(request.state, "api_key_owner", "anonymous")
