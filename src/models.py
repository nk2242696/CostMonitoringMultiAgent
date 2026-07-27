"""
Unified database models for the Azure Cost Optimization Agent.

Consolidates cost_records (from ORM) and azure_costs (from scripts) into
a single canonical schema. Adds models for alerts, spark job analysis,
and automation workflows.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Use JSON everywhere for cross-database portability (SQLite + PostgreSQL).
# SQLAlchemy's JSON type works on both backends.

from src.common.database import Base


# ---------------------------------------------------------------------------
# Core cost data
# ---------------------------------------------------------------------------

class CostRecord(Base):
    """Time-series cost data collected from Azure Cost Management API."""

    __tablename__ = "cost_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    subscription_id = Column(String(255), nullable=False, index=True)
    subscription_name = Column(String(255))
    resource_group = Column(String(255), nullable=False, index=True)
    resource_id = Column(String(500), nullable=False)
    resource_name = Column(String(255), nullable=False)
    service_name = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(255), nullable=False, index=True)
    region = Column(String(100), nullable=False)
    cost = Column(Numeric(precision=18, scale=6), nullable=False)
    currency = Column(String(10), default="USD")
    tags = Column(JSON, default=dict)
    meter_category = Column(String(255))
    meter_subcategory = Column(String(255))
    meter_name = Column(String(255))
    unit_of_measure = Column(String(100))
    quantity = Column(Numeric(precision=18, scale=6))
    unit_price = Column(Numeric(precision=18, scale=6))
    cost_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_cost_records_date_sub", "date", "subscription_id"),
        Index("ix_cost_records_service_date", "service_name", "date"),
        Index("ix_cost_records_resource_type_date", "resource_type", "date"),
    )

    def __repr__(self) -> str:
        return (
            f"<CostRecord(date={self.date}, sub={self.subscription_id}, "
            f"service={self.service_name}, cost={self.cost})>"
        )


class CostAggregation(Base):
    """Pre-computed cost summaries at different grains."""

    __tablename__ = "cost_aggregations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    aggregation_type = Column(String(50), nullable=False, index=True)  # daily, weekly, monthly
    dimension = Column(String(100), nullable=False, index=True)  # subscription, resource_group, service, resource_type
    dimension_value = Column(String(500), nullable=False, index=True)
    subscription_id = Column(String(100), nullable=False, index=True)
    total_cost = Column(Numeric(precision=18, scale=6), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    resource_count = Column(Integer, default=0)
    extra_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "date", "aggregation_type", "dimension", "dimension_value",
            "subscription_id", name="uq_cost_aggregation",
        ),
        Index("ix_cost_agg_date_type", "date", "aggregation_type"),
        Index("ix_cost_agg_dimension", "dimension", "dimension_value"),
    )


class ResourceMetadata(Base):
    """Cached resource information from Azure Resource Graph."""

    __tablename__ = "resource_metadata"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    resource_id = Column(String(500), unique=True, nullable=False, index=True)
    subscription_id = Column(String(100), nullable=False, index=True)
    resource_group = Column(String(255), index=True)
    resource_name = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=False, index=True)
    location = Column(String(100))
    sku = Column(String(100))
    tags = Column(JSON, default=dict)
    properties = Column(JSON, default=dict)
    status = Column(String(50))  # Running, Stopped, Deallocated
    last_seen = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
    )


# ---------------------------------------------------------------------------
# Budgets & Alerts
# ---------------------------------------------------------------------------

class CostBudget(Base):
    """Budget definitions with thresholds for alerts."""

    __tablename__ = "cost_budgets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    budget_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    subscription_id = Column(String(100), nullable=False, index=True)
    resource_group = Column(String(255), index=True)
    scope_type = Column(String(50), default="subscription")  # subscription, resource_group, service, tag
    scope_value = Column(String(500))
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    time_grain = Column(String(20), nullable=False, default="Monthly")  # Monthly, Quarterly, Annually
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    alert_thresholds = Column(JSON, default=lambda: {"warning": 0.75, "critical": 0.90, "exceeded": 1.0})
    notification_channels = Column(JSON, default=list)  # ["email", "slack", "teams"]
    current_spend = Column(Numeric(precision=18, scale=2), default=0)
    forecasted_spend = Column(Numeric(precision=18, scale=2))
    status = Column(String(50), default="active")  # active, paused, exceeded, completed
    filters = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    alerts = relationship("CostAlert", back_populates="budget", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_cost_budgets_dates", "start_date", "end_date"),
    )


class CostAlert(Base):
    """Alert instances fired when cost thresholds are breached."""

    __tablename__ = "cost_alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    alert_id = Column(String(100), unique=True, nullable=False, index=True)
    budget_id = Column(BigInteger, ForeignKey("cost_budgets.id"), index=True)
    alert_type = Column(String(50), nullable=False)  # budget_warning, budget_critical, budget_exceeded, anomaly_spike, mom_increase
    severity = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical
    title = Column(String(500), nullable=False)
    description = Column(Text)
    subscription_id = Column(String(100), index=True)
    resource_group = Column(String(255))
    service_name = Column(String(255))
    threshold_value = Column(Float)
    current_value = Column(Float)
    threshold_percentage = Column(Float)
    status = Column(String(50), default="active")  # active, acknowledged, resolved, suppressed
    notification_sent = Column(Boolean, default=False)
    notification_channels = Column(JSON, default=list)  # channels notified
    acknowledged_by = Column(String(255))
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    context = Column(JSON, default=dict)
    fired_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    budget = relationship("CostBudget", back_populates="alerts")

    __table_args__ = (
        Index("ix_cost_alerts_status", "status"),
        Index("ix_cost_alerts_severity", "severity"),
        Index("ix_cost_alerts_fired", "fired_at"),
    )


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

class Anomaly(Base):
    """Detected cost anomalies."""

    __tablename__ = "anomalies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    subscription_id = Column(String(100), nullable=False, index=True)
    resource_group = Column(String(255), index=True)
    resource_id = Column(String(500), index=True)
    resource_name = Column(String(255))
    service_name = Column(String(100), index=True)
    anomaly_type = Column(String(50), nullable=False)  # cost_spike, unusual_usage, resource_behavior
    detection_method = Column(String(50), nullable=False)  # zscore, iqr, isolation_forest
    expected_cost = Column(Numeric(precision=18, scale=6), nullable=False)
    actual_cost = Column(Numeric(precision=18, scale=6), nullable=False)
    deviation_percentage = Column(Float, nullable=False)
    deviation_amount = Column(Numeric(precision=18, scale=6), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    confidence_score = Column(Float)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    status = Column(String(50), default="open")  # open, investigating, resolved, false_positive
    context = Column(JSON, default=dict)
    baseline_data = Column(JSON, default=dict)
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_anomalies_status", "status"),
        Index("ix_anomalies_severity", "severity"),
        Index("ix_anomalies_resource", "resource_id", "detected_at"),
    )


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------

class CostForecast(Base):
    """Cost forecasts at multiple grains."""

    __tablename__ = "cost_forecasts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    forecast_date = Column(DateTime(timezone=True), nullable=False, index=True)
    target_date = Column(DateTime(timezone=True), nullable=False)
    subscription_id = Column(String(100), nullable=False, index=True)
    grain = Column(String(50), nullable=False, default="subscription")  # subscription, service, resource_type
    grain_value = Column(String(500))  # e.g. "Microsoft.Compute" for service grain
    forecast_period = Column(String(20), nullable=False, default="monthly")  # daily, weekly, monthly
    forecasted_cost = Column(Numeric(precision=18, scale=6), nullable=False)
    lower_bound = Column(Numeric(precision=18, scale=6))
    upper_bound = Column(Numeric(precision=18, scale=6))
    currency = Column(String(10), nullable=False, default="USD")
    confidence_level = Column(Float, default=0.95)
    model_used = Column(String(50))  # prophet, linear_regression, moving_average
    model_parameters = Column(JSON, default=dict)
    actual_cost = Column(Numeric(precision=18, scale=6))  # filled once known
    forecast_accuracy = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_cost_forecasts_target", "target_date"),
        Index("ix_cost_forecasts_grain", "grain", "grain_value"),
        Index("ix_cost_forecasts_sub_target", "subscription_id", "target_date"),
    )


# ---------------------------------------------------------------------------
# AI Recommendations (all 3 tiers)
# ---------------------------------------------------------------------------

class AIRecommendation(Base):
    """AI-generated cost optimization recommendations across all tiers."""

    __tablename__ = "ai_recommendations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    recommendation_id = Column(String(100), unique=True, nullable=False, index=True)
    tier = Column(Integer, nullable=False, default=1)  # 1=architecture, 2=automation, 3=spark
    source = Column(String(50), nullable=False)  # azure_advisor, waf, ai_engine, spark_analyzer, rule_based
    category = Column(String(50), nullable=False)  # compute, storage, database, network, spark, architecture
    title = Column(String(500), nullable=False)
    description = Column(Text)
    recommendation_text = Column(Text, nullable=False)
    subscription_id = Column(String(255), index=True)
    resource_id = Column(String(500))
    service_name = Column(String(255), index=True)
    resource_type = Column(String(255))
    current_cost = Column(Numeric(precision=18, scale=2))
    potential_savings = Column(Numeric(precision=18, scale=2))
    savings_percentage = Column(Numeric(precision=5, scale=2))
    priority = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical
    confidence_score = Column(Numeric(precision=3, scale=2))
    implementation_effort = Column(String(50))  # minutes, hours, days
    action_items = Column(JSON, default=list)
    status = Column(String(50), default="pending")  # pending, approved, rejected, implemented, dismissed
    automation_script = Column(Text)  # tier 2: generated script
    automation_type = Column(String(50))  # azure_cli, powershell, terraform, python
    approved_by = Column(String(255))
    approved_at = Column(DateTime(timezone=True))
    implemented_at = Column(DateTime(timezone=True))
    implementation_result = Column(JSON, default=dict)
    notes = Column(Text)
    rec_metadata = Column("metadata", JSON, default=dict)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_ai_rec_tier", "tier"),
        Index("ix_ai_rec_status", "status"),
        Index("ix_ai_rec_priority", "priority"),
        Index("ix_ai_rec_service", "service_name"),
    )


# ---------------------------------------------------------------------------
# Tier 3: Spark / Databricks Job Analysis
# ---------------------------------------------------------------------------

class SparkJobAnalysis(Base):
    """Analysis results for Spark/Databricks jobs."""

    __tablename__ = "spark_job_analyses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(255), nullable=False, index=True)
    job_name = Column(String(500))
    workspace_url = Column(String(500))
    cluster_id = Column(String(255))
    cluster_type = Column(String(100))  # job_cluster, interactive, all_purpose
    run_id = Column(String(255), index=True)
    run_date = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Integer)
    dbu_cost = Column(Numeric(precision=12, scale=4))
    compute_cost = Column(Numeric(precision=12, scale=4))
    total_cost = Column(Numeric(precision=12, scale=4))
    executor_count = Column(Integer)
    driver_node_type = Column(String(100))
    worker_node_type = Column(String(100))
    spark_version = Column(String(50))

    # Execution plan analysis
    physical_plan = Column(Text)
    logical_plan = Column(Text)
    plan_issues = Column(JSON, default=list)  # detected anti-patterns
    shuffle_bytes_read = Column(BigInteger, default=0)
    shuffle_bytes_written = Column(BigInteger, default=0)
    spill_bytes_disk = Column(BigInteger, default=0)
    spill_bytes_memory = Column(BigInteger, default=0)
    stages_info = Column(JSON, default=list)
    skewed_partitions = Column(JSON, default=list)

    # Code analysis
    notebook_path = Column(String(500))
    code_snippet = Column(Text)
    code_suggestions = Column(JSON, default=list)

    # AI recommendations linked
    recommendations = Column(JSON, default=list)  # recommendation_ids
    overall_score = Column(Float)  # 0-100 efficiency score
    status = Column(String(50), default="analyzed")  # pending, analyzed, optimized
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_spark_job_run", "job_id", "run_id"),
        Index("ix_spark_job_date", "run_date"),
    )


# ---------------------------------------------------------------------------
# Architecture Reviews
# ---------------------------------------------------------------------------

class ArchitectureReview(Base):
    """Architecture review sessions (Tier 1)."""

    __tablename__ = "architecture_reviews"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    review_id = Column(String(100), unique=True, nullable=False, index=True)
    problem_statement = Column(Text, nullable=False)
    proposal = Column(Text)
    review_assessment = Column(Text)
    decision = Column(Text)
    summary = Column(Text)
    decision_status = Column(String(50))  # approved, approved_with_changes, rejected
    files = Column(JSON, default=dict)
    waf_principles_applied = Column(JSON, default=list)
    estimated_monthly_cost = Column(Numeric(precision=12, scale=2))
    estimated_savings = Column(Numeric(precision=12, scale=2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Durable multi-agent runs and audit records
# ---------------------------------------------------------------------------

class AgentRun(Base):
    """Actor-scoped execution record independent of LangGraph internals."""

    __tablename__ = "agent_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    thread_id = Column(String(100), nullable=False, index=True)
    workflow_kind = Column(String(50), nullable=False)
    actor_id = Column(String(255), nullable=False, index=True)
    request_id = Column(String(100), index=True)
    scope = Column(JSON, default=dict)
    status = Column(String(50), nullable=False, default="queued", index=True)
    model = Column(String(255))
    personas = Column(JSON, default=list)
    usage = Column(JSON, default=dict)
    latency_ms = Column(Integer)
    error_category = Column(String(100))
    safe_error = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    events = relationship("AgentEvent", back_populates="run", cascade="all, delete-orphan")
    messages = relationship("AgentMessageRecord", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("AgentArtifact", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_agent_runs_actor_created", "actor_id", "created_at"),)


class AgentEvent(Base):
    """Append-only sanitized audit event for node, model, and tool activity."""

    __tablename__ = "agent_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    agent_run_id = Column(BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    node_name = Column(String(100))
    persona = Column(String(100))
    prompt_id = Column(String(100))
    prompt_version = Column(String(30))
    status = Column(String(50), nullable=False)
    duration_ms = Column(Integer)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    run = relationship("AgentRun", back_populates="events")
    __table_args__ = (Index("ix_agent_events_run_type_created", "agent_run_id", "event_type", "created_at"),)


class AgentMessageRecord(Base):
    """Sanitized conversational memory linked to a run and thread."""

    __tablename__ = "agent_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True)
    agent_run_id = Column(BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id = Column(String(100), nullable=False, index=True)
    actor_id = Column(String(255), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    message_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    run = relationship("AgentRun", back_populates="messages")
    __table_args__ = (Index("ix_agent_messages_thread_created", "thread_id", "created_at"),)


class AgentArtifact(Base):
    """Evidence, findings, governance verdicts, and pending proposals."""

    __tablename__ = "agent_artifacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    artifact_id = Column(String(100), unique=True, nullable=False, index=True)
    agent_run_id = Column(BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False, index=True)
    persona = Column(String(100))
    payload = Column(JSON, nullable=False, default=dict)
    citations = Column(JSON, default=list)
    requires_human_approval = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    run = relationship("AgentRun", back_populates="artifacts")
    __table_args__ = (Index("ix_agent_artifacts_run_type", "agent_run_id", "artifact_type"),)
