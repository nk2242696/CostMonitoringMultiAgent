"""
Savings Calculator

Aggregates potential and realised savings from all recommendation
sources and provides summary metrics, ROI projections, and
implementation tracking.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from src.models import AIRecommendation

logger = logging.getLogger(__name__)


class SavingsCalculator:
    """
    Calculate and track cost savings across all recommendation tiers.

    Provides:
    - Total potential savings (pending + approved)
    - Realised savings (implemented)
    - Savings by category, tier, and priority
    - ROI projections (annual)
    - Implementation progress tracking
    - Executive summary for reporting
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------

    def total_savings_summary(
        self,
        subscription_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive savings summary across all recommendations.
        """
        base_query = self.db.query(AIRecommendation)
        if subscription_id:
            base_query = base_query.filter(AIRecommendation.subscription_id == subscription_id)

        # Potential savings (pending + approved)
        potential = self._sum_savings(base_query, ["pending", "approved"])
        # Realised savings (implemented)
        realised = self._sum_savings(base_query, ["implemented"])
        # Dismissed / rejected
        dismissed = self._sum_savings(base_query, ["dismissed", "rejected"])

        total_potential = potential + realised
        realisation_rate = (realised / total_potential * 100) if total_potential > 0 else 0

        # Counts
        counts = self._status_counts(base_query)

        return {
            "potential_monthly_savings": round(potential, 2),
            "realised_monthly_savings": round(realised, 2),
            "dismissed_savings": round(dismissed, 2),
            "total_identified_savings": round(total_potential, 2),
            "annual_potential_savings": round(potential * 12, 2),
            "annual_realised_savings": round(realised * 12, 2),
            "realisation_rate_pct": round(realisation_rate, 2),
            "recommendation_counts": counts,
            "currency": "USD",
        }

    # ------------------------------------------------------------------
    # Breakdowns
    # ------------------------------------------------------------------

    def savings_by_category(
        self,
        subscription_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Savings broken down by category (compute, storage, etc.)."""
        query = (
            self.db.query(
                AIRecommendation.category,
                sqla_func.sum(AIRecommendation.potential_savings).label("potential"),
                sqla_func.count(AIRecommendation.id).label("count"),
                sqla_func.avg(AIRecommendation.confidence_score).label("avg_confidence"),
            )
            .filter(AIRecommendation.status.in_(["pending", "approved", "implemented"]))
            .group_by(AIRecommendation.category)
            .order_by(sqla_func.sum(AIRecommendation.potential_savings).desc())
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)

        return [
            {
                "category": row.category or "uncategorized",
                "potential_savings": float(row.potential or 0),
                "recommendation_count": row.count,
                "avg_confidence": round(float(row.avg_confidence or 0), 2),
                "annual_projection": round(float(row.potential or 0) * 12, 2),
            }
            for row in query.all()
        ]

    def savings_by_tier(
        self,
        subscription_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Savings broken down by recommendation tier (1, 2, 3)."""
        tier_names = {1: "Architecture Review", 2: "Automation", 3: "Spark Analysis"}

        query = (
            self.db.query(
                AIRecommendation.tier,
                sqla_func.sum(AIRecommendation.potential_savings).label("potential"),
                sqla_func.count(AIRecommendation.id).label("count"),
            )
            .filter(AIRecommendation.status.in_(["pending", "approved", "implemented"]))
            .group_by(AIRecommendation.tier)
            .order_by(AIRecommendation.tier)
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)

        return [
            {
                "tier": row.tier,
                "tier_name": tier_names.get(row.tier, f"Tier {row.tier}"),
                "potential_savings": float(row.potential or 0),
                "recommendation_count": row.count,
            }
            for row in query.all()
        ]

    def savings_by_priority(
        self,
        subscription_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Savings broken down by priority level."""
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        query = (
            self.db.query(
                AIRecommendation.priority,
                sqla_func.sum(AIRecommendation.potential_savings).label("potential"),
                sqla_func.count(AIRecommendation.id).label("count"),
                sqla_func.avg(AIRecommendation.savings_percentage).label("avg_savings_pct"),
            )
            .filter(AIRecommendation.status.in_(["pending", "approved"]))
            .group_by(AIRecommendation.priority)
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)

        results = [
            {
                "priority": row.priority or "unknown",
                "potential_savings": float(row.potential or 0),
                "recommendation_count": row.count,
                "avg_savings_percentage": round(float(row.avg_savings_pct or 0), 2),
            }
            for row in query.all()
        ]

        # Sort by priority order
        results.sort(key=lambda x: priority_order.get(x["priority"], 99))
        return results

    def savings_by_effort(
        self,
        subscription_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Savings broken down by implementation effort."""
        query = (
            self.db.query(
                AIRecommendation.implementation_effort,
                sqla_func.sum(AIRecommendation.potential_savings).label("potential"),
                sqla_func.count(AIRecommendation.id).label("count"),
            )
            .filter(AIRecommendation.status.in_(["pending", "approved"]))
            .group_by(AIRecommendation.implementation_effort)
            .order_by(sqla_func.sum(AIRecommendation.potential_savings).desc())
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)

        return [
            {
                "effort": row.implementation_effort or "unknown",
                "potential_savings": float(row.potential or 0),
                "recommendation_count": row.count,
            }
            for row in query.all()
        ]

    # ------------------------------------------------------------------
    # ROI projections
    # ------------------------------------------------------------------

    def roi_projection(
        self,
        subscription_id: Optional[str] = None,
        implementation_cost_per_hour: float = 75.0,
    ) -> Dict[str, Any]:
        """
        Calculate ROI projections including implementation labour cost.
        """
        effort_hours = {"minutes": 0.5, "hours": 4, "days": 16, "weeks": 40}

        query = self.db.query(AIRecommendation).filter(
            AIRecommendation.status.in_(["pending", "approved"])
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)

        recs = query.all()
        if not recs:
            return {
                "total_monthly_savings": 0,
                "implementation_cost": 0,
                "payback_period_months": None,
                "annual_roi_pct": None,
                "recommendation_count": 0,
            }

        total_monthly_savings = sum(float(r.potential_savings or 0) for r in recs)
        total_impl_hours = sum(
            effort_hours.get(r.implementation_effort or "hours", 4) for r in recs
        )
        total_impl_cost = total_impl_hours * implementation_cost_per_hour

        annual_savings = total_monthly_savings * 12
        payback_months = (total_impl_cost / total_monthly_savings) if total_monthly_savings > 0 else None
        annual_roi = ((annual_savings - total_impl_cost) / total_impl_cost * 100) if total_impl_cost > 0 else None

        return {
            "total_monthly_savings": round(total_monthly_savings, 2),
            "total_annual_savings": round(annual_savings, 2),
            "implementation_cost": round(total_impl_cost, 2),
            "implementation_hours": round(total_impl_hours, 1),
            "payback_period_months": round(payback_months, 1) if payback_months else None,
            "annual_roi_pct": round(annual_roi, 1) if annual_roi else None,
            "recommendation_count": len(recs),
            "cost_per_hour_assumed": implementation_cost_per_hour,
        }

    # ------------------------------------------------------------------
    # Quick wins
    # ------------------------------------------------------------------

    def quick_wins(
        self,
        subscription_id: Optional[str] = None,
        max_effort: str = "hours",
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Return top-N recommendations that are easy to implement
        with high savings (best ROI).
        """
        effort_filter = ["minutes"]
        if max_effort in ("hours", "days", "weeks"):
            effort_filter.append("hours")
        if max_effort in ("days", "weeks"):
            effort_filter.append("days")

        query = (
            self.db.query(AIRecommendation)
            .filter(
                AIRecommendation.status == "pending",
                AIRecommendation.implementation_effort.in_(effort_filter),
            )
            .order_by(AIRecommendation.potential_savings.desc())
            .limit(top_n)
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)

        return [
            {
                "recommendation_id": r.recommendation_id,
                "title": r.title,
                "category": r.category,
                "potential_savings": float(r.potential_savings or 0),
                "savings_percentage": float(r.savings_percentage or 0),
                "effort": r.implementation_effort,
                "priority": r.priority,
                "confidence": float(r.confidence_score or 0),
            }
            for r in query.all()
        ]

    # ------------------------------------------------------------------
    # Executive summary
    # ------------------------------------------------------------------

    def executive_summary(
        self,
        subscription_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an executive-level savings report suitable for
        management dashboards.
        """
        summary = self.total_savings_summary(subscription_id)
        by_category = self.savings_by_category(subscription_id)
        by_priority = self.savings_by_priority(subscription_id)
        roi = self.roi_projection(subscription_id)
        wins = self.quick_wins(subscription_id, top_n=5)

        return {
            "overview": {
                "monthly_opportunity": summary["potential_monthly_savings"],
                "annual_opportunity": summary["annual_potential_savings"],
                "realised_savings": summary["realised_monthly_savings"],
                "realisation_rate": summary["realisation_rate_pct"],
            },
            "breakdown_by_category": by_category,
            "breakdown_by_priority": by_priority,
            "roi_projection": roi,
            "quick_wins": wins,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------

    def implementation_progress(
        self,
        subscription_id: Optional[str] = None,
        days: int = 90,
    ) -> Dict[str, Any]:
        """Track implementation progress over time."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = self.db.query(AIRecommendation).filter(
            AIRecommendation.created_at >= cutoff,
        )
        if subscription_id:
            query = query.filter(AIRecommendation.subscription_id == subscription_id)

        recs = query.all()
        total = len(recs)
        implemented = sum(1 for r in recs if r.status == "implemented")
        approved = sum(1 for r in recs if r.status == "approved")
        pending = sum(1 for r in recs if r.status == "pending")
        dismissed = sum(1 for r in recs if r.status in ("dismissed", "rejected"))

        return {
            "period_days": days,
            "total_recommendations": total,
            "implemented": implemented,
            "approved": approved,
            "pending": pending,
            "dismissed": dismissed,
            "implementation_rate_pct": round(implemented / total * 100, 2) if total else 0,
            "total_savings_implemented": self._sum_savings_list(
                [r for r in recs if r.status == "implemented"]
            ),
            "total_savings_pending": self._sum_savings_list(
                [r for r in recs if r.status in ("pending", "approved")]
            ),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sum_savings(self, base_query, statuses: List[str]) -> float:
        """Sum potential_savings for given statuses."""
        result = (
            base_query.with_entities(sqla_func.sum(AIRecommendation.potential_savings))
            .filter(AIRecommendation.status.in_(statuses))
            .scalar()
        )
        return float(result or 0)

    def _status_counts(self, base_query) -> Dict[str, int]:
        """Count recommendations by status."""
        rows = (
            base_query.with_entities(
                AIRecommendation.status,
                sqla_func.count(AIRecommendation.id),
            )
            .group_by(AIRecommendation.status)
            .all()
        )
        return {status: count for status, count in rows}

    @staticmethod
    def _sum_savings_list(recs: List[AIRecommendation]) -> float:
        return round(sum(float(r.potential_savings or 0) for r in recs), 2)
