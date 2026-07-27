"""004 - Complete schema with TimescaleDB

Adds missing tables and configures TimescaleDB hypertable
for cost_records time-series data.

Missing from 003:
  - cost_aggregations
  - cost_budgets (needed before cost_alerts FK)
  - anomalies
  - cost_forecasts
  - resource_metadata
  - ai_recommendations (full unified schema)
  - TimescaleDB hypertable for cost_records

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── cost_aggregations ──
    op.create_table(
        "cost_aggregations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("aggregation_type", sa.String(50), nullable=False, index=True),
        sa.Column("dimension", sa.String(100), nullable=False, index=True),
        sa.Column("dimension_value", sa.String(500), nullable=False, index=True),
        sa.Column("subscription_id", sa.String(100), nullable=False, index=True),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, default="USD"),
        sa.Column("resource_count", sa.Integer, default=0),
        sa.Column("extra_metadata", JSONB, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "date", "aggregation_type", "dimension", "dimension_value",
            "subscription_id", name="uq_cost_aggregation",
        ),
    )
    op.create_index("ix_cost_agg_date_type", "cost_aggregations", ["date", "aggregation_type"])
    op.create_index("ix_cost_agg_dimension", "cost_aggregations", ["dimension", "dimension_value"])

    # ── cost_budgets (must exist before cost_alerts FK) ──
    op.create_table(
        "cost_budgets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("budget_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subscription_id", sa.String(100), nullable=False, index=True),
        sa.Column("resource_group", sa.String(255), index=True),
        sa.Column("scope_type", sa.String(50), default="subscription"),
        sa.Column("scope_value", sa.String(500)),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, default="USD"),
        sa.Column("time_grain", sa.String(20), nullable=False, default="Monthly"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alert_thresholds", JSONB, default=dict),
        sa.Column("notification_channels", JSONB, default=list),
        sa.Column("current_spend", sa.Numeric(18, 2), default=0),
        sa.Column("forecasted_spend", sa.Numeric(18, 2)),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("filters", JSONB, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cost_budgets_dates", "cost_budgets", ["start_date", "end_date"])

    # ── cost_alerts (depends on cost_budgets) ──
    op.create_table(
        "cost_alerts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("budget_id", sa.BigInteger, sa.ForeignKey("cost_budgets.id"), index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, default="medium"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("subscription_id", sa.String(100), index=True),
        sa.Column("resource_group", sa.String(255)),
        sa.Column("service_name", sa.String(255)),
        sa.Column("threshold_value", sa.Float),
        sa.Column("current_value", sa.Float),
        sa.Column("threshold_percentage", sa.Float),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("notification_sent", sa.Boolean, default=False),
        sa.Column("notification_channels", JSONB, default=list),
        sa.Column("acknowledged_by", sa.String(255)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("context", JSONB, default=dict),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cost_alerts_status", "cost_alerts", ["status"])
    op.create_index("ix_cost_alerts_severity", "cost_alerts", ["severity"])
    op.create_index("ix_cost_alerts_fired", "cost_alerts", ["fired_at"])

    # ── anomalies ──
    op.create_table(
        "anomalies",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("subscription_id", sa.String(100), nullable=False, index=True),
        sa.Column("resource_group", sa.String(255), index=True),
        sa.Column("resource_id", sa.String(500), index=True),
        sa.Column("resource_name", sa.String(255)),
        sa.Column("service_name", sa.String(100), index=True),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("detection_method", sa.String(50), nullable=False),
        sa.Column("expected_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("actual_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("deviation_percentage", sa.Float, nullable=False),
        sa.Column("deviation_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, default="USD"),
        sa.Column("confidence_score", sa.Float),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(50), default="open"),
        sa.Column("context", JSONB, default=dict),
        sa.Column("baseline_data", JSONB, default=dict),
        sa.Column("resolution_notes", sa.Text),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_anomalies_status", "anomalies", ["status"])
    op.create_index("ix_anomalies_severity", "anomalies", ["severity"])
    op.create_index("ix_anomalies_resource", "anomalies", ["resource_id", "detected_at"])

    # ── cost_forecasts ──
    op.create_table(
        "cost_forecasts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("forecast_date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subscription_id", sa.String(100), nullable=False, index=True),
        sa.Column("grain", sa.String(50), nullable=False, default="subscription"),
        sa.Column("grain_value", sa.String(500)),
        sa.Column("forecast_period", sa.String(20), nullable=False, default="monthly"),
        sa.Column("forecasted_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("lower_bound", sa.Numeric(18, 6)),
        sa.Column("upper_bound", sa.Numeric(18, 6)),
        sa.Column("currency", sa.String(10), nullable=False, default="USD"),
        sa.Column("confidence_level", sa.Float, default=0.95),
        sa.Column("model_used", sa.String(50)),
        sa.Column("model_parameters", JSONB, default=dict),
        sa.Column("actual_cost", sa.Numeric(18, 6)),
        sa.Column("forecast_accuracy", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cost_forecasts_target", "cost_forecasts", ["target_date"])
    op.create_index("ix_cost_forecasts_grain", "cost_forecasts", ["grain", "grain_value"])
    op.create_index("ix_cost_forecasts_sub_target", "cost_forecasts", ["subscription_id", "target_date"])

    # ── resource_metadata ──
    op.create_table(
        "resource_metadata",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(500), unique=True, nullable=False, index=True),
        sa.Column("subscription_id", sa.String(100), nullable=False, index=True),
        sa.Column("resource_group", sa.String(255), index=True),
        sa.Column("resource_name", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False, index=True),
        sa.Column("location", sa.String(100)),
        sa.Column("sku", sa.String(100)),
        sa.Column("tags", JSONB, default=dict),
        sa.Column("properties", JSONB, default=dict),
        sa.Column("status", sa.String(50)),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── ai_recommendations ──
    op.create_table(
        "ai_recommendations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("recommendation_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("tier", sa.Integer, nullable=False, default=1),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("recommendation_text", sa.Text, nullable=False),
        sa.Column("subscription_id", sa.String(255), index=True),
        sa.Column("resource_id", sa.String(500)),
        sa.Column("service_name", sa.String(255), index=True),
        sa.Column("resource_type", sa.String(255)),
        sa.Column("current_cost", sa.Numeric(18, 2)),
        sa.Column("potential_savings", sa.Numeric(18, 2)),
        sa.Column("savings_percentage", sa.Numeric(5, 2)),
        sa.Column("priority", sa.String(20), nullable=False, default="medium"),
        sa.Column("confidence_score", sa.Numeric(3, 2)),
        sa.Column("implementation_effort", sa.String(50)),
        sa.Column("action_items", JSONB, default=list),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("automation_script", sa.Text),
        sa.Column("automation_type", sa.String(50)),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("implemented_at", sa.DateTime(timezone=True)),
        sa.Column("implementation_result", JSONB, default=dict),
        sa.Column("notes", sa.Text),
        sa.Column("metadata", JSONB, default=dict),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_rec_tier", "ai_recommendations", ["tier"])
    op.create_index("ix_ai_rec_status", "ai_recommendations", ["status"])
    op.create_index("ix_ai_rec_priority", "ai_recommendations", ["priority"])
    op.create_index("ix_ai_rec_service", "ai_recommendations", ["service_name"])

    # The TimescaleDB image is retained, but cost_records remains a regular
    # PostgreSQL table. Timescale requires every unique key on a hypertable to
    # include the partition column; the current public ORM uses an id-only key.
    # A later schema migration can introduce a compatible composite key.


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("ai_recommendations")
    op.drop_table("resource_metadata")
    op.drop_table("cost_forecasts")
    op.drop_table("anomalies")
    op.drop_table("cost_alerts")
    op.drop_table("cost_budgets")
    op.drop_table("cost_aggregations")
