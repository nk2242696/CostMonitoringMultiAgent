"""
Pipeline Execution Analysis — Fine-grained cost optimization for
Azure Data Factory, Synapse Pipelines, and Databricks workflows.

Produces step-by-step diagnostic commands to:
1. List top pipelines by cost/execution count
2. Analyse retry patterns and wasted runs
3. Identify over-provisioned Integration Runtimes
4. Find long-running activities
5. Detect unnecessary data movement
6. Recommend specific optimizations with exact CLI commands

Usage:
    python scripts/analyse_pipelines.py
"""

import json, os, sys, uuid, time
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "dev")

from openai import AzureOpenAI
from sqlalchemy import desc, text
from sqlalchemy import func as sqla_func
from src.common.database import get_database
from src.models import AIRecommendation, CostRecord

AZURE_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://kuamnuii.openai.azure.com/")
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

if not AZURE_KEY:
    raise SystemExit("Set AZURE_OPENAI_KEY before running this script.")

client = AzureOpenAI(api_key=AZURE_KEY, api_version="2024-02-15-preview", azure_endpoint=AZURE_ENDPOINT)

PIPELINE_PROMPT = """You are a Senior Azure Data Engineer specializing in pipeline cost optimization.

You will receive cost data for Azure Data Factory or Synapse Pipeline resources.
Your job is to produce an EXTREMELY GRANULAR, STEP-BY-STEP diagnostic and optimization
plan that an engineer can execute immediately.

CRITICAL: Every step must be a CONCRETE COMMAND that produces measurable output.
Not "review the pipelines" but "run THIS EXACT COMMAND to get the list, then look for THIS PATTERN".

The steps should follow this EXACT diagnostic workflow:

PHASE 1: DISCOVERY (Steps 1-3)
- Step 1: List all pipelines with execution count and cost in the last 30 days
- Step 2: List top 10 most expensive pipeline runs with duration and status
- Step 3: List all FAILED runs to quantify retry waste

PHASE 2: ANALYSIS (Steps 4-6)
- Step 4: For the top-cost pipeline, list its activities with individual durations
- Step 5: Check Integration Runtime utilization and sizing
- Step 6: Check data movement volumes (GB transferred per pipeline)

PHASE 3: OPTIMIZATION (Steps 7-10)
- Step 7: Specific action to reduce the #1 cost driver
- Step 8: Retry policy optimization (reduce max retries, add smarter conditions)
- Step 9: Integration Runtime right-sizing command
- Step 10: Schedule optimization (reduce unnecessary frequency)

Respond in EXACT JSON format (no markdown fences):
{
  "title": "Pipeline cost title (max 80 chars)",
  "priority": "high",
  "category": "analytics",
  "savings_percentage": <integer 10-60>,
  "confidence": <float 0.6-0.9>,
  "effort": "hours",
  "risk_level": "low",
  "root_cause": "Specific explanation of why pipelines are expensive based on the cost data",
  "summary": "1-paragraph action plan",
  "steps": [
    {
      "step_number": 1,
      "title": "List all pipeline runs with cost breakdown",
      "description": "Run this command to get a list of all pipeline executions in the last 30 days sorted by cost. Look for pipelines with >100 runs or >$50 total cost.",
      "azure_cli": "az datafactory pipeline-run query-by-factory --factory-name <factory> --resource-group <rg> --last-updated-after 2026-01-19T00:00:00Z --last-updated-before 2026-02-19T00:00:00Z --output table --query \"[].{Pipeline:pipelineName, Status:status, Duration:durationInMs, Start:runStart}\" | sort",
      "portal_path": "Azure Portal > Data Factory > <factory> > Monitor > Pipeline runs",
      "estimated_time": "5 minutes",
      "risk": "none",
      "rollback": null
    }
  ],
  "expected_timeline": "2-4 hours for full analysis",
  "verification": "Compare pipeline costs 7 days before vs after changes",
  "warnings": ["Important caveats"]
}

CRITICAL RULES:
- Use REAL az datafactory / az synapse CLI commands (not made-up ones)
- For each step, the azure_cli must be a WORKING command with <placeholders>
- Each step must explain WHAT TO LOOK FOR in the output (e.g., "pipelines with >100 failed runs")
- Include exact --query JMESPath filters to extract useful columns
- For Synapse: use az synapse commands; for ADF: use az datafactory commands
- Reference the ACTUAL factory/workspace names from the cost data
- Include commands for: pipeline-run query, activity-run query, integration-runtime show
- The description should say "If you see X, do Y" — decision trees, not just commands
- Include 8-12 steps (more granular than usual)
- Include retry policy analysis and data movement volume checks"""


def get_pipeline_resources(session):
    """Get ADF and Synapse resources with their costs."""
    start = datetime.utcnow() - timedelta(days=30)
    pipeline_services = [
        "Azure Data Factory v2", "Azure Synapse Analytics",
        "Azure Databricks", "Microsoft Fabric",
    ]

    resources = []
    for svc in pipeline_services:
        rows = session.query(
            CostRecord.resource_name,
            CostRecord.resource_group,
            CostRecord.resource_type,
            CostRecord.subscription_id,
            CostRecord.service_name,
            sqla_func.sum(CostRecord.cost).label("cost"),
            sqla_func.count(CostRecord.id).label("records"),
            sqla_func.avg(CostRecord.cost).label("avg_cost"),
            sqla_func.max(CostRecord.cost).label("max_cost"),
        ).filter(
            CostRecord.service_name == svc,
            CostRecord.date >= start,
        ).group_by(
            CostRecord.resource_name, CostRecord.resource_group,
            CostRecord.resource_type, CostRecord.subscription_id,
            CostRecord.service_name,
        ).having(sqla_func.sum(CostRecord.cost) > 10).order_by(desc("cost")).all()

        for r in rows:
            resources.append({
                "resource_name": r.resource_name,
                "resource_group": r.resource_group,
                "resource_type": r.resource_type,
                "subscription_id": r.subscription_id,
                "service_name": r.service_name,
                "cost_30d": round(float(r.cost), 2),
                "record_count": r.records,
                "avg_daily_cost": round(float(r.avg_cost), 4),
                "max_daily_cost": round(float(r.max_cost), 4),
            })

    return resources


def generate_pipeline_recommendation(resource_data):
    """Call GPT-4o with pipeline-specific prompt."""
    user_prompt = f"""Analyse this Azure pipeline/ETL resource and generate a GRANULAR
step-by-step diagnostic and optimization plan.

RESOURCE DATA:
{json.dumps(resource_data, indent=2)}

Generate your recommendation as JSON."""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {"role": "system", "content": PIPELINE_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")]
    return json.loads(raw.strip())


def format_pipeline_description(rec_data, resource_data):
    """Format into structured plain text."""
    cost = resource_data["cost_30d"]
    savings_pct = rec_data.get("savings_percentage", 20)
    savings = cost * savings_pct / 100

    L = []
    L.append("=" * 72)
    L.append(f"  PIPELINE ANALYSIS: {resource_data['resource_name']}")
    L.append(f"  Service: {resource_data['service_name']}")
    L.append(f"  Resource Group: {resource_data['resource_group']}")
    L.append(f"  Subscription: {resource_data['subscription_id']}")
    L.append(f"  Monthly Cost: ${cost:,.2f}  |  Potential Savings: ${savings:,.2f} ({savings_pct}%)")
    L.append("=" * 72)
    L.append("")

    root = rec_data.get("root_cause", "")
    if root:
        L.append("  -- ROOT CAUSE " + "-" * 55)
        L.append("")
        for s in root.split(". "):
            s = s.strip()
            if s:
                L.append(f"  {s}." if not s.endswith(".") else f"  {s}")
        L.append("")

    summary = rec_data.get("summary", "")
    if summary:
        L.append("  -- RECOMMENDATION " + "-" * 51)
        L.append("")
        words = summary.split()
        line = "  "
        for w in words:
            if len(line) + len(w) + 1 > 70:
                L.append(line)
                line = "  " + w
            else:
                line += (" " + w) if len(line) > 2 else w
        if line.strip():
            L.append(line)
        L.append("")

    steps = rec_data.get("steps", [])
    if steps:
        L.append("  -- DIAGNOSTIC & OPTIMIZATION STEPS " + "-" * 34)
        L.append("")

        for st in steps:
            n = st.get("step_number", "?")
            tt = st.get("title", "")
            desc = st.get("description", "")
            cli = st.get("azure_cli")
            portal = st.get("portal_path")
            et = st.get("estimated_time", "")
            sr = st.get("risk", "none")
            rb = st.get("rollback")

            L.append(f"  +---- Step {n} " + "-" * max(1, 55 - len(str(n))) + "+")
            L.append("  |")
            L.append(f"  |  {tt}")
            L.append("  |")

            words = desc.split()
            line = "  |  "
            for w in words:
                if len(line) + len(w) + 1 > 68:
                    L.append(line)
                    line = "  |  " + w
                else:
                    line += (" " + w) if len(line) > 5 else w
            if line.strip("| "):
                L.append(line)

            if cli and cli != "null":
                L.append("  |")
                L.append("  |  COMMAND:")
                # Split long commands across lines
                if len(cli) > 60:
                    parts = cli.split(" --")
                    L.append(f"  |  > {parts[0]}")
                    for p in parts[1:]:
                        L.append(f"  |      --{p}")
                else:
                    L.append(f"  |  > {cli}")

            if portal:
                L.append("  |")
                L.append(f"  |  PORTAL: {portal}")

            L.append("  |")
            parts = []
            if et:
                parts.append(f"Time: {et}")
            if sr and sr != "none":
                parts.append(f"Risk: {sr.upper()}")
            if parts:
                L.append(f"  |  {' | '.join(parts)}")
            if rb and rb != "null" and sr not in ("none", None):
                L.append(f"  |  Rollback: {rb}")
            L.append("  |")
            L.append("  +" + "-" * 58 + "+")
            L.append("")

    verification = rec_data.get("verification", "")
    if verification:
        L.append("  -- VERIFICATION " + "-" * 53)
        L.append(f"  {verification}")
        L.append("")

    warnings = rec_data.get("warnings", [])
    if warnings:
        L.append("  -- WARNINGS " + "-" * 57)
        for w in warnings:
            L.append(f"  [!] {w}")
        L.append("")

    L.append("=" * 72)
    return "\n".join(L)


def main():
    print("=" * 60)
    print("  Pipeline Execution Analysis — GPT-4o")
    print("=" * 60)

    db = get_database()
    session = db.get_session_factory()()

    try:
        resources = get_pipeline_resources(session)
        print(f"\n  Found {len(resources)} pipeline/ETL resources with >$10 cost\n")

        if not resources:
            print("  No pipeline resources found with significant cost.")
            return

        # Check which ones already have pipeline-specific recommendations
        existing = {
            r[0] for r in session.query(AIRecommendation.title).filter(
                AIRecommendation.title.like("Pipeline:%")
            ).all()
        }

        generated = 0
        for i, res in enumerate(resources):
            title_prefix = f"Pipeline: {res['resource_name']}"
            if any(title_prefix in t for t in existing):
                print(f"  [{i+1}/{len(resources)}] {res['resource_name']:35s} SKIP (already exists)")
                continue

            print(f"  [{i+1}/{len(resources)}] {res['resource_name']:35s} ${res['cost_30d']:>10,.2f} ... ", end="", flush=True)

            try:
                rec_data = generate_pipeline_recommendation(res)
                description = format_pipeline_description(rec_data, res)

                savings_pct = rec_data.get("savings_percentage", 20)
                potential_savings = round(Decimal(str(res["cost_30d"])) * Decimal(str(savings_pct)) / 100, 2)

                action_items = []
                for st in rec_data.get("steps", []):
                    item = f"Step {st['step_number']}: {st['title']}"
                    if st.get("azure_cli") and st["azure_cli"] != "null":
                        item += f" — {st['azure_cli'][:80]}"
                    action_items.append(item)

                rec = AIRecommendation(
                    recommendation_id=str(uuid.uuid4()),
                    tier=1,
                    source="ai_engine",
                    category="analytics",
                    title=f"Pipeline: {rec_data.get('title', res['resource_name'])}",
                    description=description,
                    recommendation_text=rec_data.get("summary", ""),
                    service_name=res["service_name"],
                    resource_type=res["resource_type"],
                    subscription_id=res["subscription_id"],
                    resource_id=f"/subscriptions/{res['subscription_id']}/resourceGroups/{res['resource_group']}",
                    current_cost=Decimal(str(res["cost_30d"])),
                    potential_savings=potential_savings,
                    savings_percentage=Decimal(str(savings_pct)),
                    priority=rec_data.get("priority", "high"),
                    confidence_score=Decimal(str(rec_data.get("confidence", 0.75))),
                    implementation_effort=rec_data.get("effort", "hours"),
                    action_items=action_items,
                    status="pending",
                    rec_metadata={
                        "generated_by": "gpt-4o",
                        "analysis_type": "pipeline_execution",
                        "risk_level": rec_data.get("risk_level", "low"),
                        "expected_timeline": rec_data.get("expected_timeline", ""),
                        "verification": rec_data.get("verification", ""),
                        "warnings": rec_data.get("warnings", []),
                        "steps_json": rec_data.get("steps", []),
                        "steps": rec_data.get("steps", []),
                        "resource_name": res["resource_name"],
                        "resource_group": res["resource_group"],
                    },
                )
                session.add(rec)
                session.commit()
                generated += 1
                print(f"OK saves ${float(potential_savings):,.2f}/mo ({savings_pct}%)")

                if i < len(resources) - 1:
                    time.sleep(3)

            except json.JSONDecodeError as e:
                print(f"JSON error: {e}")
                session.rollback()
            except Exception as e:
                print(f"Error: {str(e)[:60]}")
                session.rollback()

        print(f"\n  Generated {generated} pipeline analysis recommendations")
        print(f"  Refresh Grafana to see the results!")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
