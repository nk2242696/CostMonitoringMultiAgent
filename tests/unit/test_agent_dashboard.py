"""Contract tests for the governed multi-agent Grafana integration."""

import json
from pathlib import Path


DASHBOARD_PATH = (
    Path(__file__).parents[2]
    / "config"
    / "grafana"
    / "dashboards"
    / "ai-recommendations-real.json"
)


def _dashboard():
    return json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))


def test_dashboard_includes_latest_background_agent_proposals():
    dashboard = _dashboard()
    sql = "\n".join(
        target.get("rawSql", "")
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    )

    assert "FROM agent_artifacts" in sql
    assert "workflow_kind = 'background_review'" in sql
    assert "status = 'completed'" in sql
    assert "ORDER BY completed_at DESC LIMIT 1" in sql


def test_dashboard_exposes_agent_provenance_and_approval_status():
    dashboard = _dashboard()
    proposal_panel = next(panel for panel in dashboard["panels"] if panel["id"] == 13)
    sql = proposal_panel["targets"][0]["rawSql"]

    assert 'AS "Model"' in sql
    assert 'AS "Run ID"' in sql
    assert 'AS "Evidence"' in sql
    assert "requires_human_approval" in sql
    assert "Human approval required" in sql


def test_dashboard_agent_queries_respect_subscription_scope():
    dashboard = _dashboard()
    proposal_panel = next(panel for panel in dashboard["panels"] if panel["id"] == 13)
    sql = proposal_panel["targets"][0]["rawSql"]

    assert "scope->>'subscription_id'" in sql
    assert "scope::jsonb->'subscription_ids'" in sql
    assert "${subscription:sqlstring}" in sql