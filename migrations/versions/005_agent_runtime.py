"""005 - Durable multi-agent runs and audit records.

Revision ID: 005
Revises: 004
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("thread_id", sa.String(100), nullable=False, index=True),
        sa.Column("workflow_kind", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False, index=True),
        sa.Column("request_id", sa.String(100), index=True),
        sa.Column("scope", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued", index=True),
        sa.Column("model", sa.String(255)),
        sa.Column("personas", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("usage", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("error_category", sa.String(100)),
        sa.Column("safe_error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_runs_actor_created", "agent_runs", ["actor_id", "created_at"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("agent_run_id", sa.BigInteger, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("node_name", sa.String(100)),
        sa.Column("persona", sa.String(100)),
        sa.Column("prompt_id", sa.String(100)),
        sa.Column("prompt_version", sa.String(30)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("details", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_agent_events_run_type_created", "agent_events", ["agent_run_id", "event_type", "created_at"])

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("agent_run_id", sa.BigInteger, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("thread_id", sa.String(100), nullable=False, index=True),
        sa.Column("actor_id", sa.String(255), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_agent_messages_thread_created", "agent_messages", ["thread_id", "created_at"])

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("artifact_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("agent_run_id", sa.BigInteger, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("artifact_type", sa.String(50), nullable=False, index=True),
        sa.Column("persona", sa.String(100)),
        sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("citations", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("requires_human_approval", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_agent_artifacts_run_type", "agent_artifacts", ["agent_run_id", "artifact_type"])


def downgrade() -> None:
    op.drop_table("agent_artifacts")
    op.drop_table("agent_messages")
    op.drop_table("agent_events")
    op.drop_table("agent_runs")