"""Unit tests for the Escalation Handler."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_alert
from src.alerting.escalation_handler import (
    EscalationHandler,
    EscalationPolicy,
    SEVERITY_ORDER,
)


class TestEscalationPolicy:
    """Tests for EscalationPolicy configuration."""

    def setup_method(self):
        self.policy = EscalationPolicy()

    def test_default_levels(self):
        assert len(self.policy.levels) == 4

    def test_get_level(self):
        level = self.policy.get_level(1)
        assert level is not None
        assert level["delay_minutes"] == 30

    def test_get_next_level(self):
        next_level = self.policy.get_next_level(1)
        assert next_level is not None
        assert next_level["level"] == 2

    def test_no_level_past_max(self):
        assert self.policy.get_next_level(4) is None

    def test_should_escalate_within_window(self):
        """Alert fired recently should NOT be escalated yet."""
        alert = make_alert()
        alert.fired_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert not self.policy.should_escalate(alert, 1)

    def test_should_escalate_past_window(self):
        """Alert fired long ago should be escalated."""
        alert = make_alert()
        alert.fired_at = datetime.now(timezone.utc) - timedelta(minutes=90)
        assert self.policy.should_escalate(alert, 1)

    def test_no_escalate_resolved(self):
        alert = make_alert(status="resolved")
        alert.fired_at = datetime.now(timezone.utc) - timedelta(hours=5)
        assert not self.policy.should_escalate(alert, 1)

    def test_should_auto_resolve(self):
        alert = make_alert()
        alert.fired_at = datetime.now(timezone.utc) - timedelta(hours=80)
        assert self.policy.should_auto_resolve(alert)

    def test_should_not_auto_resolve_recent(self):
        alert = make_alert()
        alert.fired_at = datetime.now(timezone.utc) - timedelta(hours=10)
        assert not self.policy.should_auto_resolve(alert)


class TestSeverityPromotion:
    """Test severity promotion logic."""

    def test_promote_low_to_medium(self):
        assert EscalationHandler._promote_severity("low") == "medium"

    def test_promote_medium_to_high(self):
        assert EscalationHandler._promote_severity("medium") == "high"

    def test_promote_high_to_critical(self):
        assert EscalationHandler._promote_severity("high") == "critical"

    def test_promote_critical_stays(self):
        assert EscalationHandler._promote_severity("critical") == "critical"


class TestEscalationHandler:
    """Tests for EscalationHandler."""

    @patch("src.alerting.escalation_handler.NotificationService")
    def test_process_escalations_empty(self, mock_notif, db_session):
        handler = EscalationHandler(db_session)
        actions = handler.process_escalations()
        assert actions == []

    @patch("src.alerting.escalation_handler.NotificationService")
    def test_auto_resolve_old_alert(self, mock_notif, db_session):
        alert = make_alert(status="active")
        alert.fired_at = datetime.now(timezone.utc) - timedelta(hours=80)
        db_session.add(alert)
        db_session.flush()

        handler = EscalationHandler(db_session)
        actions = handler.process_escalations()

        assert len(actions) == 1
        assert actions[0]["action"] == "auto_resolved"
        assert alert.status == "resolved"

    @patch("src.alerting.escalation_handler.NotificationService")
    def test_get_escalation_status(self, mock_notif, db_session):
        alert = make_alert()
        db_session.add(alert)
        db_session.flush()

        handler = EscalationHandler(db_session)
        status = handler.get_escalation_status(alert.alert_id)

        assert status is not None
        assert status["current_level"] == 0
        assert status["max_level"] == 4
