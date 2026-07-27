"""
Shared test fixtures and configuration.

Provides:
- In-memory SQLite database for tests
- Pre-populated test data factories
- Common assertions
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Force SQLite for tests (before any config loading)
os.environ.setdefault("APP_ENV", "test")

from src.common.database import Base
from src.models import (
    AIRecommendation,
    Anomaly,
    ArchitectureReview,
    CostAggregation,
    CostAlert,
    CostBudget,
    CostForecast,
    CostRecord,
    ResourceMetadata,
)


# =========================================================================
# Database fixtures
# =========================================================================


@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine for the test session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    """Provide a transactional DB session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# =========================================================================
# Data factories
# =========================================================================


def make_cost_record(
    date: datetime = None,
    subscription_id: str = "sub-001",
    resource_group: str = "rg-test",
    resource_name: str = "test-vm",
    service_name: str = "Microsoft.Compute",
    cost: float = 10.0,
    **kwargs,
) -> CostRecord:
    """Create a CostRecord with sensible defaults."""
    return CostRecord(
        date=date or datetime.now(timezone.utc),
        subscription_id=subscription_id,
        subscription_name=kwargs.get("subscription_name", "Test Subscription"),
        resource_group=resource_group,
        resource_id=kwargs.get("resource_id", f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/{service_name}/{resource_name}"),
        resource_name=resource_name,
        service_name=service_name,
        resource_type=kwargs.get("resource_type", "Microsoft.Compute/virtualMachines"),
        region=kwargs.get("region", "East US"),
        cost=Decimal(str(cost)),
        currency=kwargs.get("currency", "USD"),
        tags=kwargs.get("tags", {}),
    )


def make_budget(
    name: str = "Test Budget",
    subscription_id: str = "sub-001",
    amount: float = 1000.0,
    **kwargs,
) -> CostBudget:
    """Create a CostBudget with sensible defaults."""
    now = datetime.now(timezone.utc)
    return CostBudget(
        budget_id=kwargs.get("budget_id", str(uuid.uuid4())),
        name=name,
        subscription_id=subscription_id,
        resource_group=kwargs.get("resource_group"),
        scope_type=kwargs.get("scope_type", "subscription"),
        scope_value=kwargs.get("scope_value"),
        amount=Decimal(str(amount)),
        currency=kwargs.get("currency", "USD"),
        time_grain=kwargs.get("time_grain", "Monthly"),
        start_date=kwargs.get("start_date", now.replace(day=1)),
        end_date=kwargs.get("end_date", now.replace(day=1) + timedelta(days=30)),
        alert_thresholds=kwargs.get("alert_thresholds", {"warning": 0.75, "critical": 0.90, "exceeded": 1.0}),
        notification_channels=kwargs.get("notification_channels", ["email"]),
        status=kwargs.get("status", "active"),
    )


def make_alert(
    alert_type: str = "budget_warning",
    severity: str = "medium",
    subscription_id: str = "sub-001",
    **kwargs,
) -> CostAlert:
    """Create a CostAlert with sensible defaults."""
    return CostAlert(
        alert_id=kwargs.get("alert_id", str(uuid.uuid4())),
        alert_type=alert_type,
        severity=severity,
        title=kwargs.get("title", f"Test {alert_type} alert"),
        description=kwargs.get("description", "Test alert description"),
        subscription_id=subscription_id,
        status=kwargs.get("status", "active"),
        threshold_value=kwargs.get("threshold_value", 1000.0),
        current_value=kwargs.get("current_value", 800.0),
        threshold_percentage=kwargs.get("threshold_percentage", 80.0),
        context=kwargs.get("context", {}),
    )


def make_anomaly(
    subscription_id: str = "sub-001",
    service_name: str = "Microsoft.Compute",
    severity: str = "high",
    **kwargs,
) -> Anomaly:
    """Create an Anomaly with sensible defaults."""
    return Anomaly(
        detected_at=kwargs.get("detected_at", datetime.now(timezone.utc)),
        subscription_id=subscription_id,
        resource_id=kwargs.get("resource_id", "/subscriptions/sub-001/test-resource"),
        resource_name=kwargs.get("resource_name", "test-resource"),
        service_name=service_name,
        anomaly_type=kwargs.get("anomaly_type", "cost_spike"),
        detection_method=kwargs.get("detection_method", "zscore"),
        expected_cost=Decimal(str(kwargs.get("expected_cost", 100.0))),
        actual_cost=Decimal(str(kwargs.get("actual_cost", 300.0))),
        deviation_percentage=kwargs.get("deviation_percentage", 200.0),
        deviation_amount=Decimal(str(kwargs.get("deviation_amount", 200.0))),
        confidence_score=kwargs.get("confidence_score", 0.85),
        severity=severity,
        status=kwargs.get("status", "open"),
        context=kwargs.get("context", {}),
        baseline_data=kwargs.get("baseline_data", {}),
    )


def make_recommendation(
    category: str = "compute",
    title: str = "Test recommendation",
    savings: float = 100.0,
    **kwargs,
) -> AIRecommendation:
    """Create an AIRecommendation with sensible defaults."""
    return AIRecommendation(
        recommendation_id=kwargs.get("recommendation_id", str(uuid.uuid4())),
        tier=kwargs.get("tier", 1),
        source=kwargs.get("source", "rule_based"),
        category=category,
        title=title,
        description=kwargs.get("description", "Test recommendation description"),
        recommendation_text=kwargs.get("recommendation_text", "Implement this change"),
        subscription_id=kwargs.get("subscription_id", "sub-001"),
        resource_id=kwargs.get("resource_id", "/subscriptions/sub-001/test-resource"),
        service_name=kwargs.get("service_name", "Microsoft.Compute"),
        current_cost=Decimal(str(kwargs.get("current_cost", 500.0))),
        potential_savings=Decimal(str(savings)),
        savings_percentage=Decimal(str(kwargs.get("savings_percentage", 20.0))),
        priority=kwargs.get("priority", "medium"),
        confidence_score=Decimal(str(kwargs.get("confidence_score", 0.80))),
        implementation_effort=kwargs.get("implementation_effort", "hours"),
        status=kwargs.get("status", "pending"),
    )


def seed_cost_records(session: Session, days: int = 30, records_per_day: int = 5) -> list:
    """Seed the database with realistic cost records for testing."""
    records = []
    services = ["Microsoft.Compute", "Microsoft.Storage", "Microsoft.Sql", "Microsoft.Web", "Microsoft.Network"]
    base_costs = [15.0, 5.0, 25.0, 8.0, 3.0]

    for day_offset in range(days):
        date = datetime.now(timezone.utc) - timedelta(days=day_offset)
        for i, (service, base_cost) in enumerate(zip(services, base_costs)):
            # Add some variation
            import random
            cost = base_cost * (0.8 + random.random() * 0.4)
            record = make_cost_record(
                date=date,
                service_name=service,
                resource_name=f"{service.split('.')[-1].lower()}-resource-{i}",
                cost=cost,
            )
            records.append(record)

    session.add_all(records)
    session.flush()
    return records
