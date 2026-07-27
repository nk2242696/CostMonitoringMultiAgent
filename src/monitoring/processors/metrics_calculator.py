"""
Metrics Calculator

Computes KPIs, trends, and summary statistics from cost data.
Supports daily/weekly/monthly aggregation windows and produces
metrics suitable for dashboards and alerts.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from src.models import CostRecord, CostAggregation, CostForecast

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Calculates cost KPIs and trend metrics from stored cost data.

    Provides:
    - Total / average / max / min cost over a window
    - Month-over-month and week-over-week change
    - Cost-per-resource-type / service / subscription breakdowns
    - Trend direction and velocity
    - Top-N resource / service cost rankings
    - Forecast accuracy metrics
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Summary KPIs
    # ------------------------------------------------------------------

    def calculate_summary(
        self,
        subscription_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate summary KPIs for the given scope.

        Returns dict with: total_cost, avg_daily_cost, max_daily_cost,
        min_daily_cost, resource_count, service_count, mom_change, wow_change.
        """
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        query = self.db.query(CostRecord).filter(
            CostRecord.date >= start_date,
            CostRecord.date <= end_date,
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        # Aggregate metrics
        agg = (
            self.db.query(
                sqla_func.sum(CostRecord.cost).label("total"),
                sqla_func.avg(CostRecord.cost).label("avg"),
                sqla_func.max(CostRecord.cost).label("max"),
                sqla_func.min(CostRecord.cost).label("min"),
                sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("resource_count"),
                sqla_func.count(sqla_func.distinct(CostRecord.service_name)).label("service_count"),
            )
            .filter(
                CostRecord.date >= start_date,
                CostRecord.date <= end_date,
            )
        )
        if subscription_id:
            agg = agg.filter(CostRecord.subscription_id == subscription_id)
        result = agg.one()

        total_cost = float(result.total or 0)
        days = max((end_date - start_date).days, 1)

        # Compute daily aggregates
        daily_costs = self._daily_costs(subscription_id, start_date, end_date)
        daily_values = list(daily_costs.values())

        # Period-over-period changes
        mom_change = self._period_change(subscription_id, start_date, end_date, period_days=30)
        wow_change = self._period_change(subscription_id, start_date, end_date, period_days=7)

        return {
            "total_cost": total_cost,
            "avg_daily_cost": total_cost / days,
            "max_daily_cost": max(daily_values) if daily_values else 0,
            "min_daily_cost": min(daily_values) if daily_values else 0,
            "resource_count": result.resource_count or 0,
            "service_count": result.service_count or 0,
            "days_covered": days,
            "mom_change_pct": mom_change,
            "wow_change_pct": wow_change,
            "currency": "USD",
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
        }

    # ------------------------------------------------------------------
    # Breakdowns
    # ------------------------------------------------------------------

    def cost_by_service(
        self,
        subscription_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Top-N services by cost."""
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        query = (
            self.db.query(
                CostRecord.service_name,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("resource_count"),
            )
            .filter(CostRecord.date >= start_date, CostRecord.date <= end_date)
            .group_by(CostRecord.service_name)
            .order_by(sqla_func.sum(CostRecord.cost).desc())
            .limit(top_n)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        total = self._total_cost(subscription_id, start_date, end_date)
        return [
            {
                "service_name": row.service_name,
                "total_cost": float(row.total_cost),
                "percentage": round(float(row.total_cost) / total * 100, 2) if total else 0,
                "resource_count": row.resource_count,
            }
            for row in query.all()
        ]

    def cost_by_resource_group(
        self,
        subscription_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Top-N resource groups by cost."""
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        query = (
            self.db.query(
                CostRecord.resource_group,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("resource_count"),
            )
            .filter(CostRecord.date >= start_date, CostRecord.date <= end_date)
            .group_by(CostRecord.resource_group)
            .order_by(sqla_func.sum(CostRecord.cost).desc())
            .limit(top_n)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        total = self._total_cost(subscription_id, start_date, end_date)
        return [
            {
                "resource_group": row.resource_group,
                "total_cost": float(row.total_cost),
                "percentage": round(float(row.total_cost) / total * 100, 2) if total else 0,
                "resource_count": row.resource_count,
            }
            for row in query.all()
        ]

    def cost_by_resource_type(
        self,
        subscription_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Top-N resource types by cost."""
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        query = (
            self.db.query(
                CostRecord.resource_type,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.count(sqla_func.distinct(CostRecord.resource_id)).label("resource_count"),
            )
            .filter(CostRecord.date >= start_date, CostRecord.date <= end_date)
            .group_by(CostRecord.resource_type)
            .order_by(sqla_func.sum(CostRecord.cost).desc())
            .limit(top_n)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        total = self._total_cost(subscription_id, start_date, end_date)
        return [
            {
                "resource_type": row.resource_type,
                "total_cost": float(row.total_cost),
                "percentage": round(float(row.total_cost) / total * 100, 2) if total else 0,
                "resource_count": row.resource_count,
            }
            for row in query.all()
        ]

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def daily_cost_trend(
        self,
        subscription_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Daily cost trend for the last N days.

        Returns list of {date, total_cost, cost_change, cost_change_pct}.
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        daily = self._daily_costs(subscription_id, start_date, end_date)

        trend: List[Dict[str, Any]] = []
        prev_cost = None
        for date_str in sorted(daily.keys()):
            cost = daily[date_str]
            change = cost - prev_cost if prev_cost is not None else 0
            change_pct = (change / prev_cost * 100) if prev_cost and prev_cost > 0 else 0
            trend.append({
                "date": date_str,
                "total_cost": cost,
                "cost_change": round(change, 2),
                "cost_change_pct": round(change_pct, 2),
            })
            prev_cost = cost

        return trend

    def trend_direction(
        self,
        subscription_id: Optional[str] = None,
        window_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Determine the overall trend direction (increasing/decreasing/stable)
        over the given window using simple linear regression slope.
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=window_days)
        daily = self._daily_costs(subscription_id, start_date, end_date)

        values = [daily[k] for k in sorted(daily.keys())]
        if len(values) < 2:
            return {"direction": "insufficient_data", "slope": 0, "confidence": 0}

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator else 0

        # Normalise slope relative to mean
        relative_slope = slope / y_mean if y_mean else 0

        if relative_slope > 0.02:
            direction = "increasing"
        elif relative_slope < -0.02:
            direction = "decreasing"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "slope": round(slope, 4),
            "relative_slope": round(relative_slope, 4),
            "window_days": window_days,
            "data_points": n,
        }

    # ------------------------------------------------------------------
    # Top-N rankings
    # ------------------------------------------------------------------

    def top_expensive_resources(
        self,
        subscription_id: Optional[str] = None,
        days: int = 30,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return the top-N most expensive individual resources."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.service_name,
                CostRecord.resource_type,
                CostRecord.subscription_id,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
            )
            .filter(CostRecord.date >= start_date, CostRecord.date <= end_date)
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.service_name,
                CostRecord.resource_type,
                CostRecord.subscription_id,
            )
            .order_by(sqla_func.sum(CostRecord.cost).desc())
            .limit(top_n)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        return [
            {
                "resource_id": r.resource_id,
                "resource_name": r.resource_name,
                "service_name": r.service_name,
                "resource_type": r.resource_type,
                "subscription_id": r.subscription_id,
                "total_cost": float(r.total_cost),
            }
            for r in query.all()
        ]

    # ------------------------------------------------------------------
    # Forecast accuracy
    # ------------------------------------------------------------------

    def forecast_accuracy(
        self,
        subscription_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculate forecast accuracy metrics (MAPE, MAE, RMSE) for
        forecasts that now have actual values.
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        query = self.db.query(CostForecast).filter(
            CostForecast.forecast_date >= start_date,
            CostForecast.actual_cost.isnot(None),
        )
        if subscription_id:
            query = query.filter(CostForecast.subscription_id == subscription_id)

        forecasts = query.all()
        if not forecasts:
            return {"mape": None, "mae": None, "rmse": None, "count": 0}

        abs_errors = []
        pct_errors = []
        sq_errors = []

        for f in forecasts:
            actual = float(f.actual_cost)
            predicted = float(f.forecasted_cost)
            error = abs(actual - predicted)
            abs_errors.append(error)
            sq_errors.append(error ** 2)
            if actual > 0:
                pct_errors.append(error / actual * 100)

        n = len(forecasts)
        return {
            "mape": round(sum(pct_errors) / len(pct_errors), 2) if pct_errors else None,
            "mae": round(sum(abs_errors) / n, 2),
            "rmse": round((sum(sq_errors) / n) ** 0.5, 2),
            "count": n,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _daily_costs(
        self,
        subscription_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, float]:
        """Return {date_str: total_cost} dictionary for daily costs."""
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

        return {str(row.day): float(row.total) for row in query.all()}

    def _total_cost(
        self,
        subscription_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        query = self.db.query(sqla_func.sum(CostRecord.cost)).filter(
            CostRecord.date >= start_date,
            CostRecord.date <= end_date,
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)
        return float(query.scalar() or 0)

    def _period_change(
        self,
        subscription_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
        period_days: int,
    ) -> Optional[float]:
        """Calculate percentage change vs the previous period."""
        current = self._total_cost(subscription_id, start_date, end_date)
        prev_end = start_date
        prev_start = prev_end - timedelta(days=period_days)
        previous = self._total_cost(subscription_id, prev_start, prev_end)

        if previous <= 0:
            return None
        return round((current - previous) / previous * 100, 2)
