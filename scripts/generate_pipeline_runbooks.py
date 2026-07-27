"""
Pipeline-Level Cost Optimization Recommendations

Generates fine-grained, step-by-step diagnostic and optimization
recommendations for Azure Data Factory, Synapse Pipelines, and
Databricks workflows.

Each recommendation is a runbook: exact commands to diagnose the problem,
analyse root cause, and implement the fix.
"""

import json
import os
import sys
import uuid
import time
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

PIPELINE_PROMPT = """You are a Senior Azure Data Engineer with 15+ years of experience optimizing
Azure Data Factory, Synapse Pipelines, and Databricks workflows.

You will receive REAL cost data for a specific Azure data pipeline resource. Your job is to produce
a DIAGNOSTIC RUNBOOK: a sequence of exact Azure CLI commands that an engineer runs IN ORDER to:
1. DISCOVER which pipelines/jobs are most expensive
2. DIAGNOSE why they cost so much (retries, over-provisioned IR, long-running activities)
3. OPTIMIZE with specific configuration changes
4. VERIFY the savings

This is NOT generic advice. Every step must have an EXACT az CLI command with the ACTUAL resource
names from the data provided. The engineer should be able to copy-paste and run each command.

Respond in this EXACT JSON format (no markdown, just raw JSON):
{
  "title": "Pipeline cost diagnostic runbook for <resource_name>",
  "priority": "high|medium|low",
  "category": "analytics",
  "savings_percentage": <integer 10-60>,
  "confidence": <float 0.6-0.9>,
  "effort": "hours",
  "risk_level": "low",
  "root_cause": "2-3 sentences about what's likely driving high pipeline costs based on the data",
  "summary": "1-paragraph summary of the diagnostic and optimization approach",
  "steps": [
    {
      "step_number": 1,
      "title": "List top 10 most expensive pipeline runs (last 30 days)",
      "description": "Query the pipeline run history to identify which pipelines consume the most compute/DIU hours. Sort by duration and cost to find the top offenders.",
      "azure_cli": "az datafactory pipeline-run query-by-factory --factory-name <actual_factory_name> --resource-group <actual_rg> --last-updated-after 2026-01-19T00:00:00Z --last-updated-before 2026-02-19T00:00:00Z --filters '[{\"operand\":\"Status\",\"operator\":\"Equals\",\"values\":[\"Succeeded\"]}]' --order-by '[{\"order\":\"DESC\",\"orderBy\":\"RunEnd\"}]' --output table",
      "portal_path": "Azure Portal > Data Factory > <name> > Monitor > Pipeline runs",
      "estimated_time": "5 minutes",
      "risk": "none",
      "rollback": null
    },
    {
      "step_number": 2,
      "title": "Analyse failed/retried runs wasting compute",
      "description": "Count failed pipeline runs that were retried. Each retry re-executes the entire pipeline, multiplying DIU costs. Identify pipelines with >10% failure rate.",
      "azure_cli": "az datafactory pipeline-run query-by-factory --factory-name <name> --resource-group <rg> --last-updated-after 2026-01-19T00:00:00Z --filters '[{\"operand\":\"Status\",\"operator\":\"Equals\",\"values\":[\"Failed\"]}]' --output table | head -20",
      "portal_path": null,
      "estimated_time": "5 minutes",
      "risk": "none",
      "rollback": null
    },
    {
      "step_number": 3,
      "title": "Check Integration Runtime sizing",
      "description": "List all Integration Runtimes and their configuration. Self-hosted IRs with too many nodes or Azure IRs with large compute types waste money when pipelines don't need that capacity.",
      "azure_cli": "az datafactory integration-runtime list --factory-name <name> --resource-group <rg> --output table",
      "portal_path": "Azure Portal > Data Factory > <name> > Manage > Integration runtimes",
      "estimated_time": "3 minutes",
      "risk": "none",
      "rollback": null
    }
  ],
  "expected_timeline": "2-4 hours for full diagnostic + optimization",
  "verification": "Compare daily ADF costs for 7 days after changes vs the 7 days before. Use: az consumption usage list --start-date <date> --end-date <date> --query \"[?contains(instanceName,'<factory_name>')]\"",
  "warnings": ["Important caveats"]
}

CRITICAL RULES:
- Include 8-12 steps: first 3-4 are DIAGNOSTIC (read-only), next 3-4 are OPTIMIZATION (changes), last 1-2 are VERIFICATION
- Use the ACTUAL resource names, resource groups, and subscription IDs from the data
- For ADF: use az datafactory commands (pipeline-run, activity-run, trigger, integration-runtime)
- For Synapse: use az synapse commands (spark job, sql pool, pipeline)
- For Databricks: use az databricks commands and REST API curl commands
- Diagnostic steps should have risk=none (read-only)
- Optimization steps should have risk=low or medium with rollback commands
- Include steps that check: retry rates, activity durations, DIU/core usage, trigger frequency, IR sizing
- Be specific about WHAT TO LOOK FOR in the command output (e.g., "look for pipelines with runDuration > 3600s")
- Include a step to check trigger schedules (are pipelines running more often than needed?)
- Include a step to check if pipeline activities can use smaller DIU counts
- savings_percentage must be realistic based on the cost data"""


def get_pipeline_resources(session):
    """Get all ADF, Synapse, and Databricks resources with their costs."""
    pipeline_services = [
        'Azure Data Factory v2', 'Azure Synapse Analytics', 'Azure Databricks',
        'Logic Apps', 'Functions'
    ]
    
    resources = []
    for svc in pipeline_services:
        rows = (
            session.query(
                CostRecord.resource_name,
                CostRecord.resource_group,
                CostRecord.resource_type,
                CostRecord.service_name,
                CostRecord.subscription_id,
                sqla_func.sum(CostRecord.cost).label("cost"),
                sqla_func.count(CostRecord.id).label("records"),
                sqla_func.avg(CostRecord.cost).label("avg_cost"),
                sqla_func.max(CostRecord.cost).label("max_cost"),
            )
            .filter(
                CostRecord.service_name == svc,
                CostRecord.date >= datetime.utcnow() - timedelta(days=30),
            )
            .group_by(
                CostRecord.resource_name, CostRecord.resource_group,
                CostRecord.resource_type, CostRecord.service_name,
                CostRecord.subscription_id,
            )
            .having(sqla_func.sum(CostRecord.cost) > 100)
            .order_by(desc("cost"))
            .limit(5)
            .all()
        )
        resources.extend(rows)
    
    return resources


def call_gpt4o(resource_data):
    """Call GPT-4o with the pipeline-specific prompt."""
    user_msg = f"""Analyse this Azure data pipeline resource and generate a detailed diagnostic
runbook with exact Azure CLI commands for cost optimization.

RESOURCE DATA:
{json.dumps(resource_data, indent=2)}

Generate your diagnostic runbook as JSON."""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {"role": "system", "content": PIPELINE_PROMPT},
            {"role": "user", "content": user_msg},
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
    """Format into the structured plain-text format."""
    cost = resource_data["total_cost_30d"]
    savings_pct = rec_data.get("savings_percentage", 20)
    savings_amt = cost * savings_pct / 100
    
    L = []
    L.append("=" * 72)
    L.append(f"  PIPELINE DIAGNOSTIC RUNBOOK")
    L.append(f"  {resource_data['resource_name']} ({resource_data['service_name']})")
    L.append(f"  Monthly Cost: ${cost:,.2f}  |  Subscription: {resource_data.get('subscription_id', '?')[:12]}...")
    L.append("=" * 72)
    L.append("")
    L.append("  +-----------------------------------------------------------+")
    L.append(f"  |  POTENTIAL SAVINGS: ${savings_amt:,.2f}/month ({savings_pct}%)")
    L.append(f"  |  Effort: {rec_data.get('effort', 'hours')}  |  Timeline: {rec_data.get('expected_timeline', '2-4 hours')}")
    L.append("  +-----------------------------------------------------------+")
    L.append("")
    
    root = rec_data.get("root_cause", "")
    if root:
        L.append("  -- ROOT CAUSE " + "-" * 55)
        L.append("")
        for s in root.split(". "):
            s = s.strip()
            if s:
                if not s.endswith("."): s += "."
                L.append(f"  {s}")
        L.append("")
    
    summary = rec_data.get("summary", "")
    if summary:
        L.append("  -- APPROACH " + "-" * 57)
        L.append("")
        words = summary.split()
        line = "  "
        for w in words:
            if len(line) + len(w) + 1 > 70:
                L.append(line)
                line = "  " + w
            else:
                line += (" " + w) if len(line) > 2 else w
        if line.strip(): L.append(line)
        L.append("")
    
    steps = rec_data.get("steps", [])
    if steps:
        # Split into phases
        diag_steps = [s for s in steps if s.get("risk", "none") == "none"]
        opt_steps = [s for s in steps if s.get("risk", "none") != "none"]
        
        if diag_steps:
            L.append("  -- PHASE 1: DIAGNOSTIC (read-only) " + "-" * 34)
            L.append("")
            for st in diag_steps:
                L.append(f"  +---- Step {st['step_number']} " + "-" * max(1, 55 - len(str(st['step_number']))) + "+")
                L.append("  |")
                L.append(f"  |  {st.get('title', '')}")
                L.append("  |")
                desc = st.get("description", "")
                words = desc.split()
                line = "  |  "
                for w in words:
                    if len(line) + len(w) + 1 > 68:
                        L.append(line)
                        line = "  |  " + w
                    else:
                        line += (" " + w) if len(line) > 5 else w
                if line.strip("| "): L.append(line)
                if st.get("azure_cli") and st["azure_cli"] != "null":
                    L.append("  |")
                    L.append("  |  Command:")
                    L.append(f"  |  > {st['azure_cli']}")
                if st.get("portal_path"):
                    L.append("  |")
                    L.append(f"  |  Portal: {st['portal_path']}")
                L.append("  |")
                L.append(f"  |  Time: {st.get('estimated_time', '5 min')}")
                L.append("  |")
                L.append("  +" + "-" * 58 + "+")
                L.append("")
        
        if opt_steps:
            L.append("  -- PHASE 2: OPTIMIZATION (changes) " + "-" * 34)
            L.append("")
            for st in opt_steps:
                L.append(f"  +---- Step {st['step_number']} " + "-" * max(1, 55 - len(str(st['step_number']))) + "+")
                L.append("  |")
                L.append(f"  |  {st.get('title', '')}")
                L.append("  |")
                desc = st.get("description", "")
                words = desc.split()
                line = "  |  "
                for w in words:
                    if len(line) + len(w) + 1 > 68:
                        L.append(line)
                        line = "  |  " + w
                    else:
                        line += (" " + w) if len(line) > 5 else w
                if line.strip("| "): L.append(line)
                if st.get("azure_cli") and st["azure_cli"] != "null":
                    L.append("  |")
                    L.append("  |  Command:")
                    L.append(f"  |  > {st['azure_cli']}")
                L.append("  |")
                parts = []
                if st.get("estimated_time"): parts.append(f"Time: {st['estimated_time']}")
                if st.get("risk", "none") != "none": parts.append(f"Risk: {st['risk'].upper()}")
                if parts: L.append(f"  |  {' | '.join(parts)}")
                if st.get("rollback"):
                    L.append(f"  |  Rollback: {st['rollback']}")
                L.append("  |")
                L.append("  +" + "-" * 58 + "+")
                L.append("")
    
    verification = rec_data.get("verification", "")
    if verification:
        L.append("  -- PHASE 3: VERIFICATION " + "-" * 44)
        L.append("")
        L.append(f"  {verification}")
        L.append("")
    
    warnings = rec_data.get("warnings", [])
    if warnings:
        L.append("  -- WARNINGS " + "-" * 57)
        L.append("")
        for w in warnings:
            L.append(f"  [!] {w}")
        L.append("")
    
    L.append("=" * 72)
    return "\n".join(L)


def main():
    print("=" * 60)
    print("  Pipeline Diagnostic Runbook Generator (GPT-4o)")
    print("=" * 60)
    
    db = get_database()
    session = db.get_session_factory()()
    
    try:
        resources = get_pipeline_resources(session)
        print(f"\n  Found {len(resources)} pipeline resources with >$100/month cost\n")
        
        generated = 0
        for i, res in enumerate(resources):
            cost = float(res.cost)
            name = res.resource_name
            svc = res.service_name
            
            # Skip if already have a pipeline runbook for this resource
            existing = session.query(AIRecommendation.id).filter(
                AIRecommendation.title.contains(name),
                AIRecommendation.title.contains("runbook")
            ).first()
            if existing:
                print(f"  [{i+1}/{len(resources)}] {name[:35]:35s} -- already exists, skipping")
                continue
            
            print(f"  [{i+1}/{len(resources)}] {name[:35]:35s} ({svc[:20]}) ${cost:>10,.2f} ... ", end="", flush=True)
            
            resource_data = {
                "resource_name": name,
                "resource_group": res.resource_group,
                "resource_type": res.resource_type,
                "service_name": svc,
                "subscription_id": res.subscription_id,
                "total_cost_30d": round(cost, 2),
                "daily_avg_cost": round(float(res.avg_cost or 0), 4),
                "daily_max_cost": round(float(res.max_cost or 0), 4),
                "record_count": res.records,
            }
            
            try:
                rec_data = call_gpt4o(resource_data)
                description = format_pipeline_description(rec_data, resource_data)
                
                savings_pct = rec_data.get("savings_percentage", 20)
                potential_savings = round(Decimal(str(cost)) * Decimal(str(savings_pct)) / 100, 2)
                
                action_items = []
                for step in rec_data.get("steps", []):
                    item = f"Step {step['step_number']}: {step['title']}"
                    if step.get("azure_cli") and step["azure_cli"] != "null":
                        item += f" -- {step['azure_cli'][:80]}"
                    action_items.append(item)
                
                rec = AIRecommendation(
                    recommendation_id=str(uuid.uuid4()),
                    tier=1,
                    source="ai_engine",
                    category="analytics",
                    title=f"Pipeline runbook: {name} ({svc})",
                    description=description,
                    recommendation_text=rec_data.get("summary", ""),
                    service_name=svc,
                    resource_type=res.resource_type,
                    subscription_id=res.subscription_id,
                    resource_id=f"/subscriptions/{res.subscription_id}/resourceGroups/{res.resource_group}",
                    current_cost=Decimal(str(cost)),
                    potential_savings=potential_savings,
                    savings_percentage=Decimal(str(savings_pct)),
                    priority=rec_data.get("priority", "high"),
                    confidence_score=Decimal(str(rec_data.get("confidence", 0.75))),
                    implementation_effort=rec_data.get("effort", "hours"),
                    action_items=action_items,
                    status="pending",
                    rec_metadata={
                        "generated_by": "gpt-4o-pipeline-runbook",
                        "risk_level": rec_data.get("risk_level", "low"),
                        "expected_timeline": rec_data.get("expected_timeline", ""),
                        "verification": rec_data.get("verification", ""),
                        "warnings": rec_data.get("warnings", []),
                        "steps": rec_data.get("steps", []),
                        "steps_json": rec_data.get("steps", []),
                        "resource_count": 1,
                        "runbook_type": "pipeline_diagnostic",
                    },
                )
                session.add(rec)
                session.commit()
                
                print(f"OK saves ${float(potential_savings):,.0f}/mo ({savings_pct}%)")
                generated += 1
                
                if i < len(resources) - 1:
                    time.sleep(3)
                    
            except json.JSONDecodeError as e:
                print(f"JSON error: {e}")
                session.rollback()
            except Exception as e:
                print(f"Error: {str(e)[:60]}")
                session.rollback()
        
        total = session.execute(text("SELECT COUNT(*) FROM ai_recommendations")).scalar()
        savings = float(session.execute(text("SELECT COALESCE(SUM(potential_savings),0) FROM ai_recommendations")).scalar())
        
        print(f"\n{'=' * 60}")
        print(f"  Generated {generated} pipeline diagnostic runbooks")
        print(f"  Total recommendations: {total} (${savings:,.2f}/month savings)")
        print(f"{'=' * 60}")
        
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
