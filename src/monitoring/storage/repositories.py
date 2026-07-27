"""
Repository Layer (Data Access Layer)

Provides CRUD operations and specialised queries for all domain models.
Follows the Repository pattern — keeps SQL/ORM details out of service
and API layers.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Generic, List, Optional, Tuple, Type, TypeVar

from sqlalchemy import func as sqla_func, desc, and_, or_
from sqlalchemy.orm import Session

from src.common.database import Base
from src.models import (
    Anomaly,
    CostAggregation,
    CostAlert,
    CostBudget,
    CostForecast,
    CostRecord,
    ResourceMetadata,
    AIRecommendation,
    ArchitectureReview,
    SparkJobAnalysis,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)


# =========================================================================
# Generic base repository
# =========================================================================


class BaseRepository(Generic[T]):
    """Generic CRUD repository for any SQLAlchemy model."""

    model: Type[T]

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, record_id: int) -> Optional[T]:
        return self.db.query(self.model).get(record_id)

    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        return self.db.query(self.model).limit(limit).offset(offset).all()

    def count(self) -> int:
        return self.db.query(sqla_func.count(self.model.id)).scalar() or 0

    def create(self, obj: T) -> T:
        self.db.add(obj)
        self.db.flush()
        return obj

    def create_many(self, objects: List[T]) -> List[T]:
        self.db.add_all(objects)
        self.db.flush()
        return objects

    def update(self, obj: T, **kwargs) -> T:
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: T) -> None:
        self.db.delete(obj)
        self.db.flush()

    def delete_by_id(self, record_id: int) -> bool:
        obj = self.get_by_id(record_id)
        if obj:
            self.delete(obj)
            return True
        return False

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


# =========================================================================
# Cost Record repository
# =========================================================================


class CostRecordRepository(BaseRepository[CostRecord]):
    model = CostRecord

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        subscription_id: Optional[str] = None,
        service_name: Optional[str] = None,
        resource_group: Optional[str] = None,
        limit: int = 1000,
    ) -> List[CostRecord]:
        """Query cost records by date range with optional filters."""
        query = self.db.query(CostRecord).filter(
            CostRecord.date >= start_date,
            CostRecord.date <= end_date,
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)
        if service_name:
            query = query.filter(CostRecord.service_name == service_name)
        if resource_group:
            query = query.filter(CostRecord.resource_group == resource_group)
        return query.order_by(CostRecord.date.desc()).limit(limit).all()

    def get_daily_totals(
        self,
        start_date: datetime,
        end_date: datetime,
        subscription_id: Optional[str] = None,
    ) -> List[Tuple[datetime, float]]:
        """Return daily cost totals."""
        query = (
            self.db.query(
                sqla_func.date(CostRecord.date).label("day"),
                sqla_func.sum(CostRecord.cost).label("total"),
            )
            .filter(CostRecord.date >= start_date, CostRecord.date <= end_date)
            .group_by(sqla_func.date(CostRecord.date))
            .order_by(sqla_func.date(CostRecord.date))
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)
        return [(row.day, float(row.total)) for row in query.all()]

    def get_cost_by_service(
        self,
        start_date: datetime,
        end_date: datetime,
        subscription_id: Optional[str] = None,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Breakdown cost by service."""
        query = (
            self.db.query(
                CostRecord.service_name,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("resource_count"),
            )
            .filter(CostRecord.date >= start_date, CostRecord.date <= end_date)
            .group_by(CostRecord.service_name)
            .order_by(desc(sqla_func.sum(CostRecord.cost)))
            .limit(top_n)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)
        return [
            {"service_name": r.service_name, "total_cost": float(r.total_cost), "resource_count": r.resource_count}
            for r in query.all()
        ]

    def get_total_cost(
        self,
        start_date: datetime,
        end_date: datetime,
        subscription_id: Optional[str] = None,
    ) -> float:
        query = self.db.query(sqla_func.sum(CostRecord.cost)).filter(
            CostRecord.date >= start_date, CostRecord.date <= end_date,
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)
        return float(query.scalar() or 0)

    def get_distinct_subscriptions(self) -> List[str]:
        rows = self.db.query(CostRecord.subscription_id).distinct().all()
        return [r[0] for r in rows]

    def upsert_records(self, records: List[CostRecord]) -> int:
        """Insert records, skipping duplicates by (date, subscription_id, resource_id)."""
        inserted = 0
        for rec in records:
            exists = (
                self.db.query(CostRecord.id)
                .filter(
                    CostRecord.date == rec.date,
                    CostRecord.subscription_id == rec.subscription_id,
                    CostRecord.resource_id == rec.resource_id,
                )
                .first()
            )
            if not exists:
                self.db.add(rec)
                inserted += 1
        self.db.flush()
        logger.info("Upserted %d / %d cost records", inserted, len(records))
        return inserted


# =========================================================================
# Cost Aggregation repository
# =========================================================================


class CostAggregationRepository(BaseRepository[CostAggregation]):
    model = CostAggregation

    def get_by_dimension(
        self,
        dimension: str,
        aggregation_type: str = "daily",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        subscription_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[CostAggregation]:
        query = self.db.query(CostAggregation).filter(
            CostAggregation.dimension == dimension,
            CostAggregation.aggregation_type == aggregation_type,
        )
        if start_date:
            query = query.filter(CostAggregation.date >= start_date)
        if end_date:
            query = query.filter(CostAggregation.date <= end_date)
        if subscription_id:
            query = query.filter(CostAggregation.subscription_id == subscription_id)
        return query.order_by(CostAggregation.date.desc()).limit(limit).all()

    def upsert_aggregation(self, agg: CostAggregation) -> CostAggregation:
        """Insert or update an aggregation row (upsert on unique constraint)."""
        existing = (
            self.db.query(CostAggregation)
            .filter(
                CostAggregation.date == agg.date,
                CostAggregation.aggregation_type == agg.aggregation_type,
                CostAggregation.dimension == agg.dimension,
                CostAggregation.dimension_value == agg.dimension_value,
                CostAggregation.subscription_id == agg.subscription_id,
            )
            .first()
        )
        if existing:
            existing.total_cost = agg.total_cost
            existing.resource_count = agg.resource_count
            self.db.flush()
            return existing
        else:
            self.db.add(agg)
            self.db.flush()
            return agg


# =========================================================================
# Budget repository
# =========================================================================


class CostBudgetRepository(BaseRepository[CostBudget]):
    model = CostBudget

    def get_by_budget_id(self, budget_id: str) -> Optional[CostBudget]:
        return self.db.query(CostBudget).filter(CostBudget.budget_id == budget_id).first()

    def get_active_budgets(self, subscription_id: Optional[str] = None) -> List[CostBudget]:
        query = self.db.query(CostBudget).filter(CostBudget.status == "active")
        if subscription_id:
            query = query.filter(CostBudget.subscription_id == subscription_id)
        return query.all()

    def update_spend(self, budget_id: str, current_spend: float, forecasted_spend: Optional[float] = None) -> Optional[CostBudget]:
        budget = self.get_by_budget_id(budget_id)
        if not budget:
            return None
        budget.current_spend = Decimal(str(current_spend))
        if forecasted_spend is not None:
            budget.forecasted_spend = Decimal(str(forecasted_spend))
        if current_spend >= float(budget.amount):
            budget.status = "exceeded"
        self.db.flush()
        return budget


# =========================================================================
# Alert repository
# =========================================================================


class CostAlertRepository(BaseRepository[CostAlert]):
    model = CostAlert

    def get_by_alert_id(self, alert_id: str) -> Optional[CostAlert]:
        return self.db.query(CostAlert).filter(CostAlert.alert_id == alert_id).first()

    def get_active_alerts(
        self,
        subscription_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[CostAlert]:
        query = self.db.query(CostAlert).filter(CostAlert.status == "active")
        if subscription_id:
            query = query.filter(CostAlert.subscription_id == subscription_id)
        if severity:
            query = query.filter(CostAlert.severity == severity)
        return query.order_by(CostAlert.fired_at.desc()).limit(limit).all()

    def get_alerts_by_status(self, status: str, limit: int = 100) -> List[CostAlert]:
        return (
            self.db.query(CostAlert)
            .filter(CostAlert.status == status)
            .order_by(CostAlert.fired_at.desc())
            .limit(limit)
            .all()
        )

    def acknowledge(self, alert_id: str, acknowledged_by: str) -> Optional[CostAlert]:
        alert = self.get_by_alert_id(alert_id)
        if alert:
            alert.status = "acknowledged"
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc)
            self.db.flush()
        return alert

    def resolve(self, alert_id: str) -> Optional[CostAlert]:
        alert = self.get_by_alert_id(alert_id)
        if alert:
            alert.status = "resolved"
            alert.resolved_at = datetime.now(timezone.utc)
            self.db.flush()
        return alert

    def get_recent_duplicate(
        self,
        alert_type: str,
        subscription_id: str,
        window_minutes: int = 60,
    ) -> Optional[CostAlert]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        return (
            self.db.query(CostAlert)
            .filter(
                CostAlert.alert_type == alert_type,
                CostAlert.subscription_id == subscription_id,
                CostAlert.fired_at >= cutoff,
            )
            .first()
        )

    def alert_counts_by_severity(self) -> Dict[str, int]:
        rows = (
            self.db.query(CostAlert.severity, sqla_func.count(CostAlert.id))
            .filter(CostAlert.status == "active")
            .group_by(CostAlert.severity)
            .all()
        )
        return {sev: cnt for sev, cnt in rows}


# =========================================================================
# Anomaly repository
# =========================================================================


class AnomalyRepository(BaseRepository[Anomaly]):
    model = Anomaly

    def get_open_anomalies(
        self,
        subscription_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Anomaly]:
        query = self.db.query(Anomaly).filter(Anomaly.status == "open")
        if subscription_id:
            query = query.filter(Anomaly.subscription_id == subscription_id)
        if severity:
            query = query.filter(Anomaly.severity == severity)
        return query.order_by(Anomaly.detected_at.desc()).limit(limit).all()

    def resolve(self, anomaly_id: int, resolved_by: str, notes: Optional[str] = None) -> Optional[Anomaly]:
        anomaly = self.get_by_id(anomaly_id)
        if anomaly:
            anomaly.status = "resolved"
            anomaly.resolved_at = datetime.now(timezone.utc)
            anomaly.resolved_by = resolved_by
            if notes:
                anomaly.resolution_notes = notes
            self.db.flush()
        return anomaly

    def mark_false_positive(self, anomaly_id: int, resolved_by: str) -> Optional[Anomaly]:
        anomaly = self.get_by_id(anomaly_id)
        if anomaly:
            anomaly.status = "false_positive"
            anomaly.resolved_at = datetime.now(timezone.utc)
            anomaly.resolved_by = resolved_by
            self.db.flush()
        return anomaly

    def get_by_resource(self, resource_id: str, limit: int = 50) -> List[Anomaly]:
        return (
            self.db.query(Anomaly)
            .filter(Anomaly.resource_id == resource_id)
            .order_by(Anomaly.detected_at.desc())
            .limit(limit)
            .all()
        )


# =========================================================================
# Forecast repository
# =========================================================================


class CostForecastRepository(BaseRepository[CostForecast]):
    model = CostForecast

    def get_latest_forecasts(
        self,
        subscription_id: Optional[str] = None,
        grain: Optional[str] = None,
        limit: int = 30,
    ) -> List[CostForecast]:
        query = self.db.query(CostForecast)
        if subscription_id:
            query = query.filter(CostForecast.subscription_id == subscription_id)
        if grain:
            query = query.filter(CostForecast.grain == grain)
        return query.order_by(CostForecast.target_date.desc()).limit(limit).all()

    def backfill_actuals(
        self,
        subscription_id: str,
        target_date: datetime,
        actual_cost: float,
    ) -> int:
        """Set actual_cost and compute accuracy for matching forecasts."""
        forecasts = (
            self.db.query(CostForecast)
            .filter(
                CostForecast.subscription_id == subscription_id,
                sqla_func.date(CostForecast.target_date) == target_date.date(),
                CostForecast.actual_cost.is_(None),
            )
            .all()
        )
        for f in forecasts:
            f.actual_cost = Decimal(str(actual_cost))
            if float(f.forecasted_cost) > 0:
                error = abs(actual_cost - float(f.forecasted_cost))
                f.forecast_accuracy = round(1.0 - (error / float(f.forecasted_cost)), 4)
        self.db.flush()
        return len(forecasts)


# =========================================================================
# Resource Metadata repository
# =========================================================================


class ResourceMetadataRepository(BaseRepository[ResourceMetadata]):
    model = ResourceMetadata

    def get_by_resource_id(self, resource_id: str) -> Optional[ResourceMetadata]:
        return self.db.query(ResourceMetadata).filter(ResourceMetadata.resource_id == resource_id).first()

    def upsert(self, resource: ResourceMetadata) -> ResourceMetadata:
        existing = self.get_by_resource_id(resource.resource_id)
        if existing:
            existing.resource_name = resource.resource_name
            existing.resource_type = resource.resource_type
            existing.location = resource.location
            existing.sku = resource.sku
            existing.tags = resource.tags
            existing.properties = resource.properties
            existing.status = resource.status
            existing.last_seen = resource.last_seen
            self.db.flush()
            return existing
        self.db.add(resource)
        self.db.flush()
        return resource

    def get_idle_resources(self, idle_days: int = 7) -> List[ResourceMetadata]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=idle_days)
        return (
            self.db.query(ResourceMetadata)
            .filter(
                ResourceMetadata.last_seen < cutoff,
                ResourceMetadata.status.in_(["Running", "Active"]),
            )
            .all()
        )

    def get_by_type(self, resource_type: str, subscription_id: Optional[str] = None) -> List[ResourceMetadata]:
        query = self.db.query(ResourceMetadata).filter(ResourceMetadata.resource_type == resource_type)
        if subscription_id:
            query = query.filter(ResourceMetadata.subscription_id == subscription_id)
        return query.all()


# =========================================================================
# AI Recommendation repository
# =========================================================================


class AIRecommendationRepository(BaseRepository[AIRecommendation]):
    model = AIRecommendation

    def get_by_recommendation_id(self, recommendation_id: str) -> Optional[AIRecommendation]:
        return (
            self.db.query(AIRecommendation)
            .filter(AIRecommendation.recommendation_id == recommendation_id)
            .first()
        )

    def get_pending(
        self,
        subscription_id: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
    ) -> List[AIRecommendation]:
        query = self.db.query(AIRecommendation).filter(AIRecommendation.status == "pending")
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)
        if category:
            query = query.filter(AIRecommendation.category == category)
        if priority:
            query = query.filter(AIRecommendation.priority == priority)
        return query.order_by(desc(AIRecommendation.potential_savings)).limit(limit).all()

    def get_total_potential_savings(self, subscription_id: Optional[str] = None) -> float:
        query = self.db.query(sqla_func.sum(AIRecommendation.potential_savings)).filter(
            AIRecommendation.status.in_(["pending", "approved"])
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)
        return float(query.scalar() or 0)

    def update_status(self, recommendation_id: str, status: str, **kwargs) -> Optional[AIRecommendation]:
        rec = self.get_by_recommendation_id(recommendation_id)
        if not rec:
            return None
        rec.status = status
        if status == "approved":
            rec.approved_at = datetime.now(timezone.utc)
            rec.approved_by = kwargs.get("approved_by")
        elif status == "implemented":
            rec.implemented_at = datetime.now(timezone.utc)
        for k, v in kwargs.items():
            if hasattr(rec, k) and k not in ("approved_at", "implemented_at", "approved_by"):
                setattr(rec, k, v)
        self.db.flush()
        return rec

    def savings_by_category(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(
                AIRecommendation.category,
                sqla_func.sum(AIRecommendation.potential_savings).label("total_savings"),
                sqla_func.count(AIRecommendation.id).label("count"),
            )
            .filter(AIRecommendation.status.in_(["pending", "approved"]))
            .group_by(AIRecommendation.category)
            .order_by(desc(sqla_func.sum(AIRecommendation.potential_savings)))
            .all()
        )
        return [
            {"category": r.category, "total_savings": float(r.total_savings or 0), "count": r.count}
            for r in rows
        ]


# =========================================================================
# Architecture Review repository
# =========================================================================


class ArchitectureReviewRepository(BaseRepository[ArchitectureReview]):
    model = ArchitectureReview

    def get_by_review_id(self, review_id: str) -> Optional[ArchitectureReview]:
        return self.db.query(ArchitectureReview).filter(ArchitectureReview.review_id == review_id).first()

    def get_recent(self, limit: int = 10) -> List[ArchitectureReview]:
        return (
            self.db.query(ArchitectureReview)
            .order_by(ArchitectureReview.created_at.desc())
            .limit(limit)
            .all()
        )


# =========================================================================
# Spark Job Analysis repository
# =========================================================================


class SparkJobAnalysisRepository(BaseRepository[SparkJobAnalysis]):
    model = SparkJobAnalysis

    def get_by_job_id(self, job_id: str) -> List[SparkJobAnalysis]:
        return (
            self.db.query(SparkJobAnalysis)
            .filter(SparkJobAnalysis.job_id == job_id)
            .order_by(SparkJobAnalysis.run_date.desc())
            .all()
        )

    def get_inefficient_jobs(self, score_threshold: float = 50.0, limit: int = 20) -> List[SparkJobAnalysis]:
        return (
            self.db.query(SparkJobAnalysis)
            .filter(SparkJobAnalysis.overall_score < score_threshold)
            .order_by(SparkJobAnalysis.total_cost.desc())
            .limit(limit)
            .all()
        )
