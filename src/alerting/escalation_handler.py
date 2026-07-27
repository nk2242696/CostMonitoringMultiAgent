"""
Escalation Handler

Manages alert escalation policies — when an alert is not acknowledged
or resolved within a defined SLA window, it is escalated to higher
severity or additional notification channels.

Supports:
- Time-based escalation (e.g., escalate after 30 min, 1 hr, 4 hr)
- Severity promotion (medium → high → critical)
- Multi-tier notification (email first → then Slack → then PagerDuty/Teams)
- On-call rotation integration hooks
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.models import CostAlert
from src.alerting.notifications import NotificationService

logger = logging.getLogger(__name__)


# =========================================================================
# Escalation policy configuration
# =========================================================================


DEFAULT_ESCALATION_POLICY: Dict[str, Any] = {
    "levels": [
        {
            "level": 1,
            "delay_minutes": 30,
            "action": "notify",
            "channels": ["email"],
            "description": "Initial notification to team",
        },
        {
            "level": 2,
            "delay_minutes": 60,
            "action": "escalate_severity",
            "channels": ["email", "slack"],
            "promote_severity": True,
            "description": "Escalate to team lead + Slack",
        },
        {
            "level": 3,
            "delay_minutes": 240,
            "action": "escalate_severity",
            "channels": ["email", "slack", "teams"],
            "promote_severity": True,
            "description": "Escalate to management + all channels",
        },
        {
            "level": 4,
            "delay_minutes": 480,
            "action": "page",
            "channels": ["email", "slack", "teams"],
            "promote_severity": True,
            "description": "Critical page — requires immediate action",
        },
    ],
    "max_escalations": 4,
    "auto_resolve_after_hours": 72,
}

# Severity promotion order
SEVERITY_ORDER = ["low", "medium", "high", "critical"]


class EscalationPolicy:
    """Defines the escalation rules for an alert type or subscription."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or DEFAULT_ESCALATION_POLICY
        self.levels = self.config.get("levels", [])
        self.max_escalations = self.config.get("max_escalations", 4)
        self.auto_resolve_hours = self.config.get("auto_resolve_after_hours", 72)

    def get_level(self, level_number: int) -> Optional[Dict[str, Any]]:
        """Get escalation level configuration."""
        for level in self.levels:
            if level["level"] == level_number:
                return level
        return None

    def get_next_level(self, current_level: int) -> Optional[Dict[str, Any]]:
        """Get the next escalation level after the current one."""
        return self.get_level(current_level + 1)

    def should_escalate(self, alert: CostAlert, current_level: int) -> bool:
        """Check if an alert should be escalated based on time elapsed."""
        if current_level >= self.max_escalations:
            return False
        if alert.status in ("resolved", "acknowledged"):
            return False

        level_config = self.get_level(current_level)
        if not level_config:
            return False

        delay = timedelta(minutes=level_config["delay_minutes"])
        fired_at = alert.fired_at or alert.created_at
        return datetime.now(timezone.utc) >= fired_at + delay

    def should_auto_resolve(self, alert: CostAlert) -> bool:
        """Check if an alert should be auto-resolved after max hours."""
        fired_at = alert.fired_at or alert.created_at
        cutoff = fired_at + timedelta(hours=self.auto_resolve_hours)
        return datetime.now(timezone.utc) >= cutoff


class EscalationHandler:
    """
    Processes alert escalations based on configured policies.

    Usage::

        handler = EscalationHandler(db_session)
        escalated = handler.process_escalations()
    """

    def __init__(
        self,
        db: Session,
        policy: Optional[EscalationPolicy] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        self.db = db
        self.policy = policy or EscalationPolicy()
        self.notification_service = notification_service or NotificationService()
        # Track escalation state in alert context
        self._escalation_key = "escalation"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_escalations(self) -> List[Dict[str, Any]]:
        """
        Check all active/unacknowledged alerts and escalate as needed.

        Returns:
            List of escalation actions taken.
        """
        alerts = self._get_escalatable_alerts()
        actions: List[Dict[str, Any]] = []

        for alert in alerts:
            current_level = self._get_current_level(alert)

            # Check auto-resolve first
            if self.policy.should_auto_resolve(alert):
                self._auto_resolve(alert)
                actions.append({
                    "alert_id": alert.alert_id,
                    "action": "auto_resolved",
                    "reason": f"No action after {self.policy.auto_resolve_hours}h",
                })
                continue

            # Check if escalation is needed
            next_level = current_level + 1
            next_config = self.policy.get_next_level(current_level)
            if not next_config:
                continue

            if self.policy.should_escalate(alert, next_level):
                result = self._escalate(alert, next_config)
                actions.append(result)

        if actions:
            self.db.commit()
            logger.info("Processed %d escalation actions", len(actions))

        return actions

    def escalate_alert(self, alert_id: str, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Manually escalate a specific alert to the next level.
        """
        alert = (
            self.db.query(CostAlert)
            .filter(CostAlert.alert_id == alert_id)
            .first()
        )
        if not alert:
            logger.warning("Alert not found for escalation: %s", alert_id)
            return None

        current_level = self._get_current_level(alert)
        next_config = self.policy.get_next_level(current_level)
        if not next_config:
            logger.info("Alert %s already at max escalation level", alert_id)
            return {"alert_id": alert_id, "action": "max_level_reached"}

        result = self._escalate(alert, next_config, manual_reason=reason)
        self.db.commit()
        return result

    def get_escalation_status(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Get the current escalation status for an alert."""
        alert = (
            self.db.query(CostAlert)
            .filter(CostAlert.alert_id == alert_id)
            .first()
        )
        if not alert:
            return None

        context = alert.context or {}
        escalation = context.get(self._escalation_key, {})

        return {
            "alert_id": alert.alert_id,
            "current_level": escalation.get("level", 0),
            "max_level": self.policy.max_escalations,
            "severity": alert.severity,
            "status": alert.status,
            "escalation_history": escalation.get("history", []),
            "next_escalation_at": self._next_escalation_time(alert),
        }

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _escalate(
        self,
        alert: CostAlert,
        level_config: Dict[str, Any],
        manual_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform the escalation action."""
        new_level = level_config["level"]
        old_severity = alert.severity

        # Promote severity if configured
        if level_config.get("promote_severity"):
            alert.severity = self._promote_severity(alert.severity)

        # Update context with escalation info
        context = alert.context or {}
        escalation = context.get(self._escalation_key, {"level": 0, "history": []})
        escalation["level"] = new_level
        escalation["history"].append({
            "level": new_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_severity": old_severity,
            "new_severity": alert.severity,
            "channels": level_config.get("channels", []),
            "reason": manual_reason or f"Auto-escalated after {level_config['delay_minutes']} minutes",
        })
        context[self._escalation_key] = escalation
        alert.context = context

        # Send notifications on escalation channels
        self._send_escalation_notification(alert, level_config, old_severity)

        logger.info(
            "Escalated alert %s to level %d (severity: %s → %s)",
            alert.alert_id,
            new_level,
            old_severity,
            alert.severity,
        )

        return {
            "alert_id": alert.alert_id,
            "action": "escalated",
            "level": new_level,
            "old_severity": old_severity,
            "new_severity": alert.severity,
            "channels_notified": level_config.get("channels", []),
            "description": level_config.get("description", ""),
        }

    def _auto_resolve(self, alert: CostAlert) -> None:
        """Auto-resolve an alert that has been open too long."""
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)

        context = alert.context or {}
        context["auto_resolved"] = True
        context["auto_resolved_at"] = datetime.now(timezone.utc).isoformat()
        context["auto_resolve_reason"] = f"No action within {self.policy.auto_resolve_hours} hours"
        alert.context = context

        logger.info("Auto-resolved alert %s after %dh inactivity", alert.alert_id, self.policy.auto_resolve_hours)

    def _send_escalation_notification(
        self,
        alert: CostAlert,
        level_config: Dict[str, Any],
        old_severity: str,
    ) -> None:
        """Send escalation notifications through configured channels."""
        channels = level_config.get("channels", [])
        subject = f"[ESCALATED L{level_config['level']}] {alert.title}"
        message = (
            f"Alert has been escalated to Level {level_config['level']}.\n\n"
            f"Title: {alert.title}\n"
            f"Severity: {old_severity} → {alert.severity}\n"
            f"Type: {alert.alert_type}\n"
            f"Subscription: {alert.subscription_id}\n"
            f"Description: {alert.description}\n\n"
            f"Action: {level_config.get('description', 'Review and respond')}\n"
            f"Escalation Policy Level: {level_config['level']} / {self.policy.max_escalations}"
        )

        try:
            self.notification_service.send_notification(
                subject=subject,
                message=message,
                channels=channels,
                severity=alert.severity,
                alert_data={
                    "alert_id": alert.alert_id,
                    "alert_type": alert.alert_type,
                    "escalation_level": level_config["level"],
                },
            )
        except Exception as exc:
            logger.error(
                "Failed to send escalation notification for alert %s: %s",
                alert.alert_id,
                exc,
            )

    def _get_escalatable_alerts(self) -> List[CostAlert]:
        """Get all alerts that are candidates for escalation."""
        return (
            self.db.query(CostAlert)
            .filter(
                CostAlert.status.in_(["active"]),
            )
            .all()
        )

    def _get_current_level(self, alert: CostAlert) -> int:
        """Get the current escalation level from alert context."""
        context = alert.context or {}
        return context.get(self._escalation_key, {}).get("level", 0)

    def _next_escalation_time(self, alert: CostAlert) -> Optional[str]:
        """Calculate when the next escalation will occur."""
        current_level = self._get_current_level(alert)
        next_config = self.policy.get_next_level(current_level)
        if not next_config:
            return None
        if alert.status in ("resolved", "acknowledged"):
            return None

        fired_at = alert.fired_at or alert.created_at
        next_time = fired_at + timedelta(minutes=next_config["delay_minutes"])
        return next_time.isoformat()

    @staticmethod
    def _promote_severity(current: str) -> str:
        """Promote severity to the next level."""
        try:
            idx = SEVERITY_ORDER.index(current)
            if idx < len(SEVERITY_ORDER) - 1:
                return SEVERITY_ORDER[idx + 1]
        except ValueError:
            pass
        return current
