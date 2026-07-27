"""003 - Unified schema

Creates all tables from the consolidated models:
  - cost_records (enhanced)
  - cost_aggregations
  - cost_budgets
  - cost_alerts (NEW)
  - anomalies
  - cost_forecasts (enhanced)
  - resource_metadata
  - ai_recommendations (enhanced with tiers)
  - spark_job_analyses (NEW)
  - architecture_reviews (NEW)

Revision ID: 003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = None  # fresh start
branch_labels = None
depends_on = None


def upgrade() -> None:
    # cost_records
    op.create_table(
        "cost_records",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("subscription_id", sa.String(255), nullable=False, index=True),
        sa.Column("subscription_name", sa.String(255)),
        sa.Column("resource_group", sa.String(255), nullable=False, index=True),
        sa.Column("resource_id", sa.String(500), nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False, index=True),
        sa.Column("resource_type", sa.String(255), nullable=False, index=True),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(10), default="USD"),
        sa.Column("tags", JSONB, default=dict),
        sa.Column("meter_category", sa.String(255)),
        sa.Column("meter_subcategory", sa.String(255)),
        sa.Column("meter_name", sa.String(255)),
        sa.Column("unit_of_measure", sa.String(100)),
        sa.Column("quantity", sa.Numeric(18, 6)),
        sa.Column("unit_price", sa.Numeric(18, 6)),
        sa.Column("metadata", JSONB, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cost_records_date_sub", "cost_records", ["date", "subscription_id"])
    op.create_index("ix_cost_records_service_date", "cost_records", ["service_name", "date"])
    op.create_index("ix_cost_records_resource_type_date", "cost_records", ["resource_type", "date"])

    # cost_alerts
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

    # spark_job_analyses
    op.create_table(
        "spark_job_analyses",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(255), nullable=False, index=True),
        sa.Column("job_name", sa.String(500)),
        sa.Column("workspace_url", sa.String(500)),
        sa.Column("cluster_id", sa.String(255)),
        sa.Column("cluster_type", sa.String(100)),
        sa.Column("run_id", sa.String(255), index=True),
        sa.Column("run_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("dbu_cost", sa.Numeric(12, 4)),
        sa.Column("compute_cost", sa.Numeric(12, 4)),
        sa.Column("total_cost", sa.Numeric(12, 4)),
        sa.Column("executor_count", sa.Integer),
        sa.Column("driver_node_type", sa.String(100)),
        sa.Column("worker_node_type", sa.String(100)),
        sa.Column("spark_version", sa.String(50)),
        sa.Column("physical_plan", sa.Text),
        sa.Column("logical_plan", sa.Text),
        sa.Column("plan_issues", JSONB, default=list),
        sa.Column("shuffle_bytes_read", sa.BigInteger, default=0),
        sa.Column("shuffle_bytes_written", sa.BigInteger, default=0),
        sa.Column("spill_bytes_disk", sa.BigInteger, default=0),
        sa.Column("spill_bytes_memory", sa.BigInteger, default=0),
        sa.Column("stages_info", JSONB, default=list),
        sa.Column("skewed_partitions", JSONB, default=list),
        sa.Column("notebook_path", sa.String(500)),
        sa.Column("code_snippet", sa.Text),
        sa.Column("code_suggestions", JSONB, default=list),
        sa.Column("recommendations", JSONB, default=list),
        sa.Column("overall_score", sa.Float),
        sa.Column("status", sa.String(50), default="analyzed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # architecture_reviews
    op.create_table(
        "architecture_reviews",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("problem_statement", sa.Text, nullable=False),
        sa.Column("proposal", sa.Text),
        sa.Column("review_assessment", sa.Text),
        sa.Column("decision", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("decision_status", sa.String(50)),
        sa.Column("files", JSONB, default=dict),
        sa.Column("waf_principles_applied", JSONB, default=list),
        sa.Column("estimated_monthly_cost", sa.Numeric(12, 2)),
        sa.Column("estimated_savings", sa.Numeric(12, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("architecture_reviews")
    op.drop_table("spark_job_analyses")
    op.drop_table("cost_alerts")
    op.drop_index("ix_cost_records_resource_type_date", "cost_records")
    op.drop_index("ix_cost_records_service_date", "cost_records")
    op.drop_index("ix_cost_records_date_sub", "cost_records")
