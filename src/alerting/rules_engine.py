"""
Alerting Rules Engine

Evaluates cost data against budget thresholds and anomaly conditions
to fire alerts. Runs on a schedule via APScheduler or Celery.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from src.models import CostAlert, CostBudget, CostRecord, Anomaly

logger = logging.getLogger(__name__)


class RulesEngine:
    """
    Evaluates alert rules against live cost data.

    Rule types:
      - budget_threshold: % of budget consumed
      - mom_increase:     month-over-month cost increase exceeds X%
      - anomaly_spike:    cost deviation above Z-score threshold
      - absolute:         cost exceeds absolute dollar amount
    """

    def __init__(self, db: Session, dedup_window_minutes: int = 60):
        self.db = db
        self.dedup_window = timedelta(minutes=dedup_window_minutes)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_all(self) -> List[CostAlert]:
        """Run all rule evaluations and return newly fired alerts."""
        alerts: List[CostAlert] = []
        alerts.extend(self._evaluate_budget_rules())
        alerts.extend(self._evaluate_mom_rules())
        alerts.extend(self._evaluate_anomaly_rules())
        return alerts

    # ------------------------------------------------------------------
    # Budget threshold rules
    # ------------------------------------------------------------------

    def _evaluate_budget_rules(self) -> List[CostAlert]:
        """Check every active budget for threshold breaches."""
        budgets = (
            self.db.query(CostBudget)
            .filter(CostBudget.status == "active")
            .all()
        )
        alerts: List[CostAlert] = []

        for budget in budgets:
            current_spend = self._calculate_current_spend(budget)
            budget.current_spend = current_spend
            utilization = float(current_spend / budget.amount) if budget.amount else 0

            thresholds = budget.alert_thresholds or {
                "warning": 0.75,
                "critical": 0.90,
                "exceeded": 1.0,
            }

            # Fire the *highest* applicable threshold only
            if utilization >= thresholds.get("exceeded", 1.0):
                alert = self._fire_budget_alert(
                    budget, "budget_exceeded", "critical", utilization, current_spend
                )
            elif utilization >= thresholds.get("critical", 0.90):
                alert = self._fire_budget_alert(
                    budget, "budget_critical", "high", utilization, current_spend
                )
            elif utilization >= thresholds.get("warning", 0.75):
                alert = self._fire_budget_alert(
                    budget, "budget_warning", "medium", utilization, current_spend
                )
            else:
                alert = None

            if alert:
                alerts.append(alert)

        self.db.commit()
        return alerts

    def _calculate_current_spend(self, budget: CostBudget) -> float:
        """Sum cost_records for the budget's scope and current period."""
        query = self.db.query(sqla_func.sum(CostRecord.cost)).filter(
            CostRecord.subscription_id == budget.subscription_id,
            CostRecord.date >= budget.start_date,
        )

        if budget.resource_group:
            query = query.filter(CostRecord.resource_group == budget.resource_group)
        if budget.scope_type == "service" and budget.scope_value:
            query = query.filter(CostRecord.service_name == budget.scope_value)

        return float(query.scalar() or 0)

    def _fire_budget_alert(
        self,
        budget: CostBudget,
        alert_type: str,
        severity: str,
        utilization: float,
        current_spend: float,
    ) -> Optional[CostAlert]:
        """Create a budget alert if not already fired within dedup window."""
        if self._is_duplicate(alert_type, budget.subscription_id, budget.budget_id):
            return None

        alert = CostAlert(
            alert_id=str(uuid.uuid4()),
            budget_id=budget.id,
            alert_type=alert_type,
            severity=severity,
            title=f"Budget '{budget.name}': {utilization:.0%} utilised (${current_spend:,.2f} / ${float(budget.amount):,.2f})",
            description=(
                f"Budget '{budget.name}' on subscription {budget.subscription_id} "
                f"has reached {utilization:.1%} utilisation. "
                f"Current spend: ${current_spend:,.2f}, Limit: ${float(budget.amount):,.2f}."
            ),
            subscription_id=budget.subscription_id,
            resource_group=budget.resource_group,
            threshold_value=float(budget.amount),
            current_value=current_spend,
            threshold_percentage=utilization * 100,
            notification_channels=budget.notification_channels or [],
            context={
                "budget_id": budget.budget_id,
                "budget_name": budget.name,
                "time_grain": budget.time_grain,
                "scope_type": budget.scope_type,
            },
        )
        self.db.add(alert)
        logger.info("Fired %s alert for budget '%s'", alert_type, budget.name)
        return alert

    # ------------------------------------------------------------------
    # Month-over-month increase rules
    # ------------------------------------------------------------------

    def _evaluate_mom_rules(self, threshold_pct: float = 25.0) -> List[CostAlert]:
        """Fire alerts when month-over-month cost increase exceeds threshold."""
        now = datetime.utcnow()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        prev_month_end = current_month_start - timedelta(seconds=1)

        # per-subscription
        subs = (
            self.db.query(CostRecord.subscription_id)
            .distinct()
            .all()
        )

        alerts: List[CostAlert] = []
        for (sub_id,) in subs:
            current = float(
                self.db.query(sqla_func.sum(CostRecord.cost))
                .filter(
                    CostRecord.subscription_id == sub_id,
                    CostRecord.date >= current_month_start,
                )
                .scalar()
                or 0
            )
            previous = float(
                self.db.query(sqla_func.sum(CostRecord.cost))
                .filter(
                    CostRecord.subscription_id == sub_id,
                    CostRecord.date >= prev_month_start,
                    CostRecord.date <= prev_month_end,
                )
                .scalar()
                or 0
            )

            if previous <= 0:
                continue

            pct_change = ((current - previous) / previous) * 100
            if pct_change >= threshold_pct:
                if self._is_duplicate("mom_increase", sub_id):
                    continue
                alert = CostAlert(
                    alert_id=str(uuid.uuid4()),
                    alert_type="mom_increase",
                    severity="high" if pct_change > 50 else "medium",
                    title=f"Month-over-month cost increase: {pct_change:+.1f}% for {sub_id}",
                    description=(
                        f"Subscription {sub_id} costs rose from ${previous:,.2f} last month "
                        f"to ${current:,.2f} this month ({pct_change:+.1f}%)."
                    ),
                    subscription_id=sub_id,
                    threshold_value=threshold_pct,
                    current_value=pct_change,
                    threshold_percentage=pct_change,
                    context={
                        "previous_month_cost": previous,
                        "current_month_cost": current,
                    },
                )
                self.db.add(alert)
                alerts.append(alert)

        self.db.commit()
        return alerts

    # ------------------------------------------------------------------
    # Anomaly-based rules
    # ------------------------------------------------------------------

    def _evaluate_anomaly_rules(self) -> List[CostAlert]:
        """Convert high-severity open anomalies into alerts."""
        recent_anomalies = (
            self.db.query(Anomaly)
            .filter(
                Anomaly.status == "open",
                Anomaly.severity.in_(["high", "critical"]),
                Anomaly.detected_at >= datetime.utcnow() - timedelta(hours=24),
            )
            .all()
        )

        alerts: List[CostAlert] = []
        for anomaly in recent_anomalies:
            if self._is_duplicate("anomaly_spike", anomaly.subscription_id, str(anomaly.id)):
                continue

            alert = CostAlert(
                alert_id=str(uuid.uuid4()),
                alert_type="anomaly_spike",
                severity=anomaly.severity,
                title=f"Cost anomaly detected: {anomaly.service_name} ({anomaly.deviation_percentage:+.1f}%)",
                description=(
                    f"Anomaly in {anomaly.service_name} on subscription {anomaly.subscription_id}. "
                    f"Expected ${float(anomaly.expected_cost):,.2f}, actual ${float(anomaly.actual_cost):,.2f} "
                    f"(deviation {anomaly.deviation_percentage:+.1f}%)."
                ),
                subscription_id=anomaly.subscription_id,
                service_name=anomaly.service_name,
                threshold_value=float(anomaly.expected_cost),
                current_value=float(anomaly.actual_cost),
                threshold_percentage=anomaly.deviation_percentage,
                context={
                    "anomaly_id": anomaly.id,
                    "detection_method": anomaly.detection_method,
                    "confidence_score": anomaly.confidence_score,
                },
            )
            self.db.add(alert)
            alerts.append(alert)

        self.db.commit()
        return alerts

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _is_duplicate(
        self,
        alert_type: str,
        subscription_id: str,
        extra_key: Optional[str] = None,
    ) -> bool:
        """Check if the same alert was already fired within the dedup window."""
        cutoff = datetime.utcnow() - self.dedup_window
        query = (
            self.db.query(CostAlert)
            .filter(
                CostAlert.alert_type == alert_type,
                CostAlert.subscription_id == subscription_id,
                CostAlert.fired_at >= cutoff,
                CostAlert.status.in_(["active", "acknowledged"]),
            )
        )
        if extra_key:
            query = query.filter(
                CostAlert.context["budget_id"].astext == extra_key
            )
        return query.first() is not None
