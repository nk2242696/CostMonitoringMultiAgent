"""Unit tests for the Repository Layer."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.conftest import (
    make_alert,
    make_anomaly,
    make_budget,
    make_cost_record,
    make_recommendation,
)
from src.monitoring.storage.repositories import (
    AnomalyRepository,
    CostAlertRepository,
    CostBudgetRepository,
    CostForecastRepository,
    CostRecordRepository,
    AIRecommendationRepository,
    AgentArtifactRepository,
    AgentEventRepository,
    AgentMessageRepository,
    AgentRunRepository,
)
from src.models import AgentArtifact, AgentEvent, AgentMessageRecord, AgentRun


class TestCostRecordRepository:
    """Tests for CostRecordRepository."""

    def test_create_and_get(self, db_session):
        repo = CostRecordRepository(db_session)
        record = make_cost_record(cost=42.50)
        repo.create(record)
        db_session.flush()

        assert record.id is not None

    def test_get_by_date_range(self, db_session):
        repo = CostRecordRepository(db_session)
        now = datetime.now(timezone.utc)

        for i in range(5):
            repo.create(make_cost_record(date=now - timedelta(days=i), cost=10 + i))
        db_session.flush()

        results = repo.get_by_date_range(now - timedelta(days=3), now)
        assert len(results) >= 3

    def test_get_total_cost(self, db_session):
        repo = CostRecordRepository(db_session)
        now = datetime.now(timezone.utc)

        repo.create(make_cost_record(date=now, cost=100.0))
        repo.create(make_cost_record(date=now, cost=50.0, resource_name="vm-2",
                                      resource_id="/sub/rg/vm-2"))
        db_session.flush()

        total = repo.get_total_cost(now - timedelta(hours=1), now + timedelta(hours=1))
        assert total >= 150.0

    def test_count(self, db_session):
        repo = CostRecordRepository(db_session)
        assert repo.count() == 0

        repo.create(make_cost_record())
        db_session.flush()
        assert repo.count() == 1


class TestCostBudgetRepository:
    """Tests for CostBudgetRepository."""

    def test_create_and_get(self, db_session):
        repo = CostBudgetRepository(db_session)
        budget = make_budget(name="Monthly Cloud Budget", amount=5000.0)
        repo.create(budget)
        db_session.flush()

        result = repo.get_by_budget_id(budget.budget_id)
        assert result is not None
        assert result.name == "Monthly Cloud Budget"
        assert float(result.amount) == 5000.0

    def test_get_active_budgets(self, db_session):
        repo = CostBudgetRepository(db_session)
        repo.create(make_budget(name="Active", status="active"))
        repo.create(make_budget(name="Exceeded", status="exceeded"))
        db_session.flush()

        active = repo.get_active_budgets()
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_update_spend(self, db_session):
        repo = CostBudgetRepository(db_session)
        budget = make_budget(amount=1000.0)
        repo.create(budget)
        db_session.flush()

        repo.update_spend(budget.budget_id, 800.0)
        assert float(budget.current_spend) == 800.0
        assert budget.status == "active"

        repo.update_spend(budget.budget_id, 1100.0)
        assert budget.status == "exceeded"


class TestCostAlertRepository:
    """Tests for CostAlertRepository."""

    def test_create_and_get(self, db_session):
        repo = CostAlertRepository(db_session)
        alert = make_alert(alert_type="budget_warning", severity="medium")
        repo.create(alert)
        db_session.flush()

        result = repo.get_by_alert_id(alert.alert_id)
        assert result is not None
        assert result.alert_type == "budget_warning"

    def test_acknowledge(self, db_session):
        repo = CostAlertRepository(db_session)
        alert = make_alert()
        repo.create(alert)
        db_session.flush()

        repo.acknowledge(alert.alert_id, "admin@example.com")
        assert alert.status == "acknowledged"
        assert alert.acknowledged_by == "admin@example.com"
        assert alert.acknowledged_at is not None

    def test_resolve(self, db_session):
        repo = CostAlertRepository(db_session)
        alert = make_alert()
        repo.create(alert)
        db_session.flush()

        repo.resolve(alert.alert_id)
        assert alert.status == "resolved"
        assert alert.resolved_at is not None

    def test_active_alerts_filter(self, db_session):
        repo = CostAlertRepository(db_session)
        repo.create(make_alert(status="active", severity="high"))
        repo.create(make_alert(status="active", severity="low"))
        repo.create(make_alert(status="resolved", severity="high"))
        db_session.flush()

        active = repo.get_active_alerts()
        assert len(active) == 2

        high_only = repo.get_active_alerts(severity="high")
        assert len(high_only) == 1


class TestAnomalyRepository:
    """Tests for AnomalyRepository."""

    def test_create_and_get_open(self, db_session):
        repo = AnomalyRepository(db_session)
        repo.create(make_anomaly(status="open", severity="high"))
        repo.create(make_anomaly(status="resolved", severity="high"))
        db_session.flush()

        open_anomalies = repo.get_open_anomalies()
        assert len(open_anomalies) == 1

    def test_resolve_anomaly(self, db_session):
        repo = AnomalyRepository(db_session)
        anomaly = make_anomaly()
        repo.create(anomaly)
        db_session.flush()

        repo.resolve(anomaly.id, "admin", notes="False alarm")
        assert anomaly.status == "resolved"
        assert anomaly.resolution_notes == "False alarm"

    def test_mark_false_positive(self, db_session):
        repo = AnomalyRepository(db_session)
        anomaly = make_anomaly()
        repo.create(anomaly)
        db_session.flush()

        repo.mark_false_positive(anomaly.id, "admin")
        assert anomaly.status == "false_positive"


class TestAIRecommendationRepository:
    """Tests for AIRecommendationRepository."""

    def test_get_pending(self, db_session):
        repo = AIRecommendationRepository(db_session)
        repo.create(make_recommendation(savings=100.0, status="pending"))
        repo.create(make_recommendation(savings=200.0, status="pending"))
        repo.create(make_recommendation(savings=300.0, status="implemented"))
        db_session.flush()

        pending = repo.get_pending()
        assert len(pending) == 2

    def test_total_potential_savings(self, db_session):
        repo = AIRecommendationRepository(db_session)
        repo.create(make_recommendation(savings=100.0, status="pending"))
        repo.create(make_recommendation(savings=200.0, status="approved"))
        repo.create(make_recommendation(savings=500.0, status="implemented"))
        db_session.flush()

        total = repo.get_total_potential_savings()
        assert total == 300.0  # Only pending + approved

    def test_update_status(self, db_session):
        repo = AIRecommendationRepository(db_session)
        rec = make_recommendation()
        repo.create(rec)
        db_session.flush()

        repo.update_status(rec.recommendation_id, "approved", approved_by="manager")
        assert rec.status == "approved"
        assert rec.approved_at is not None


class TestAgentRepositories:
    def test_run_lookup_is_actor_scoped(self, db_session):
        repo = AgentRunRepository(db_session)
        run = repo.create(AgentRun(
            run_id="run-1", thread_id="thread-1", workflow_kind="chat",
            actor_id="actor-a", status="completed",
        ))
        db_session.flush()

        assert repo.get_for_actor("run-1", "actor-a") is run
        assert repo.get_for_actor("run-1", "actor-b") is None

    def test_events_messages_and_artifacts_are_bounded(self, db_session):
        run = AgentRunRepository(db_session).create(AgentRun(
            run_id="run-2", thread_id="thread-2", workflow_kind="chat",
            actor_id="actor-a", status="completed",
        ))
        db_session.flush()
        AgentEventRepository(db_session).create(AgentEvent(
            event_id="event-1", agent_run_id=run.id, event_type="tool",
            node_name="cost_analyst", status="completed", details={"tool": "cost_summary"},
        ))
        AgentMessageRepository(db_session).create(AgentMessageRecord(
            message_id="message-1", agent_run_id=run.id, thread_id="thread-2",
            actor_id="actor-a", role="user", content="Review costs",
        ))
        AgentArtifactRepository(db_session).create(AgentArtifact(
            artifact_id="artifact-1", agent_run_id=run.id, artifact_type="proposal",
            payload={"title": "Review sizing"}, requires_human_approval=True,
        ))
        db_session.flush()

        assert len(AgentEventRepository(db_session).list_for_run(run.id)) == 1
        assert len(AgentMessageRepository(db_session).get_thread_history(
            "thread-2", "actor-a"
        )) == 1
        artifacts = AgentArtifactRepository(db_session).list_for_run(run.id)
        assert len(artifacts) == 1
        assert artifacts[0].requires_human_approval is True
