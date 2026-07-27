"""
AI-Powered Cost Optimization Recommendation Generator

Uses Azure OpenAI GPT-4o to produce actionable step-by-step recommendations.
Generates BOTH service-level AND resource-level recommendations.

Usage:
    python scripts/generate_ai_recommendations.py
"""

import json, os, sys, uuid, time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

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

SYSTEM_PROMPT = """You are a Senior Azure FinOps Engineer with 15+ years experience.
You will receive real Azure cost data. Produce a HIGHLY ACTIONABLE cost optimization
recommendation with GRANULAR step-by-step instructions.

Respond in this EXACT JSON format (no markdown fences, just raw JSON):
{
  "title": "Concise title (max 80 chars)",
  "priority": "high|medium|low",
  "category": "compute|storage|database|network|security|analytics",
  "savings_percentage": <integer 5-80>,
  "confidence": <float 0.5-0.95>,
  "effort": "minutes|hours|days",
  "risk_level": "low|medium|high",
  "root_cause": "2-3 sentences explaining WHY this costs money",
  "summary": "1-paragraph actionable summary",
  "steps": [
    {
      "step_number": 1,
      "title": "Short step title",
      "description": "Detailed description of exactly what to do",
      "azure_cli": "az ... command with placeholders (null if N/A)",
      "portal_path": "Azure Portal > ... navigation path",
      "estimated_time": "5 minutes",
      "risk": "none|low|medium",
      "rollback": "How to undo this step"
    }
  ],
  "expected_timeline": "Total implementation time",
  "verification": "How to verify savings after implementation",
  "warnings": ["Important caveats"]
}

RULES:
- 4-8 steps per recommendation with Azure CLI commands
- Reference ACTUAL cost numbers and resource names from the data
- Be specific about target SKUs, tiers, and configurations
- Include rollback for risky steps"""


def get_service_cost_data(session, service_name):
    """Gather detailed cost data for a service."""
    now = datetime.utcnow()
    start = now - timedelta(days=30)
    total = float(session.query(sqla_func.sum(CostRecord.cost)).filter(
        CostRecord.service_name == service_name, CostRecord.date >= start).scalar() or 0)
    res_count = session.query(sqla_func.count(sqla_func.distinct(CostRecord.resource_id))).filter(
        CostRecord.service_name == service_name, CostRecord.date >= start).scalar() or 0
    rg_count = session.query(sqla_func.count(sqla_func.distinct(CostRecord.resource_group))).filter(
        CostRecord.service_name == service_name, CostRecord.date >= start).scalar() or 0
    stats = session.query(
        sqla_func.avg(CostRecord.cost).label("avg"),
        sqla_func.min(CostRecord.cost).label("min"),
        sqla_func.max(CostRecord.cost).label("max"),
    ).filter(CostRecord.service_name == service_name, CostRecord.date >= start).first()
    top_res = session.query(
        CostRecord.resource_name, CostRecord.resource_group, CostRecord.resource_type,
        sqla_func.sum(CostRecord.cost).label("cost"),
    ).filter(CostRecord.service_name == service_name, CostRecord.date >= start
    ).group_by(CostRecord.resource_name, CostRecord.resource_group, CostRecord.resource_type
    ).order_by(desc("cost")).limit(10).all()
    return {
        "service_name": service_name, "total_cost_30d": round(total, 2),
        "projected_monthly_cost": round(total, 2), "resource_count": res_count,
        "resource_group_count": rg_count,
        "daily_avg_cost": round(float(stats.avg or 0), 4),
        "daily_min_cost": round(float(stats.min or 0), 4),
        "daily_max_cost": round(float(stats.max or 0), 4),
        "top_resources": [{"name": r.resource_name, "resource_group": r.resource_group,
            "type": r.resource_type, "cost_30d": round(float(r.cost), 2)} for r in top_res],
    }


def call_gpt4o(data):
    """Call GPT-4o and parse JSON response."""
    prompt = f"Analyse this Azure cost data and generate a recommendation.\n\nDATA:\n{json.dumps(data, indent=2)}\n\nGenerate JSON."
    resp = client.chat.completions.create(model=DEPLOYMENT, messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}], temperature=0.3, max_tokens=3000)
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"): raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"): raw = raw[:raw.rfind("```")]
    return json.loads(raw.strip())


def format_description(rec_data, service_data):
    """Format recommendation as structured plain text for Grafana."""
    cost = service_data["total_cost_30d"]
    pct = rec_data.get("savings_percentage", 15)
    savings = cost * pct / 100
    svc = service_data.get("resource_name", service_data["service_name"])
    res_count = service_data["resource_count"]
    risk = rec_data.get("risk_level", "low").upper()
    effort = rec_data.get("effort", "hours")
    timeline = rec_data.get("expected_timeline", "1-2 weeks")

    L = ["=" * 72, f"  {svc}", f"  Monthly Cost: ${cost:,.2f}  |  Resources: {res_count}  |  Risk: {risk}", "=" * 72, "",
         "  +-----------------------------------------------------------+",
         f"  |  POTENTIAL SAVINGS: ${savings:,.2f}/month ({pct}%)",
         f"  |  Effort: {effort:<12}  Timeline: {timeline}",
         "  +-----------------------------------------------------------+", ""]

    root = rec_data.get("root_cause", "")
    if root:
        L += ["  -- ROOT CAUSE " + "-" * 55, ""]
        for s in root.split(". "):
            s = s.strip()
            if s:
                L.append(f"  {s}." if not s.endswith(".") else f"  {s}")
        L.append("")

    summary = rec_data.get("summary", "")
    if summary:
        L += ["  -- RECOMMENDATION " + "-" * 51, ""]
        words, line = summary.split(), "  "
        for w in words:
            if len(line) + len(w) + 1 > 70: L.append(line); line = "  " + w
            else: line += (" " + w) if len(line) > 2 else w
        if line.strip(): L.append(line)
        L.append("")

    steps = rec_data.get("steps", [])
    if steps:
        L += ["  -- IMPLEMENTATION STEPS " + "-" * 46, ""]
        for st in steps:
            n, t, d = st.get("step_number", "?"), st.get("title", ""), st.get("description", "")
            L += [f"  +---- Step {n} " + "-" * max(1, 55-len(str(n))) + "+", "  |", f"  |  {t}", "  |"]
            words, line = d.split(), "  |  "
            for w in words:
                if len(line) + len(w) + 1 > 68: L.append(line); line = "  |  " + w
                else: line += (" " + w) if len(line) > 5 else w
            if line.strip("| "): L.append(line)
            if st.get("azure_cli"): L += ["  |", "  |  CLI Command:", f"  |  > {st['azure_cli']}"]
            if st.get("portal_path"): L += ["  |", "  |  Portal:", f"  |  > {st['portal_path']}"]
            L.append("  |")
            parts = []
            if st.get("estimated_time"): parts.append(f"Time: {st['estimated_time']}")
            sr = st.get("risk", "none")
            if sr and sr != "none": parts.append(f"Risk: {sr.upper()}")
            if parts: L.append(f"  |  {' | '.join(parts)}")
            if st.get("rollback") and sr not in ("none", None): L.append(f"  |  Rollback: {st['rollback']}")
            L += ["  |", "  +" + "-" * 58 + "+", ""]

    v = rec_data.get("verification", "Monitor costs for 7 days.")
    L += ["  -- VERIFICATION " + "-" * 53, "", f"  {v}", ""]
    warnings = rec_data.get("warnings", [])
    if warnings:
        L += ["  -- WARNINGS " + "-" * 57, ""]
        for w in warnings: L.append(f"  [!] {w}")
        L.append("")
    L.append("=" * 72)
    return "\n".join(L)


def persist_recommendation(session, service_data, rec_data):
    """Save recommendation to database."""
    cost = Decimal(str(service_data["total_cost_30d"]))
    pct = rec_data.get("savings_percentage", 15)
    savings = round(cost * Decimal(str(pct)) / 100, 2)
    desc_text = format_description(rec_data, service_data)
    actions = [f"Step {s['step_number']}: {s['title']}" for s in rec_data.get("steps", [])]
    rec = AIRecommendation(
        recommendation_id=str(uuid.uuid4()), tier=1, source="ai_engine",
        category=rec_data.get("category", "general"),
        title=rec_data.get("title", f"Optimize {service_data['service_name']}"),
        description=desc_text, recommendation_text=rec_data.get("summary", ""),
        service_name=service_data["service_name"],
        resource_type=service_data.get("resource_type", service_data["service_name"]),
        current_cost=cost, potential_savings=savings,
        savings_percentage=Decimal(str(pct)),
        priority=rec_data.get("priority", "medium"),
        confidence_score=Decimal(str(rec_data.get("confidence", 0.80))),
        implementation_effort=rec_data.get("effort", "hours"),
        action_items=actions, status="pending",
        rec_metadata={
            "generated_by": "gpt-4o", "risk_level": rec_data.get("risk_level", "low"),
            "expected_timeline": rec_data.get("expected_timeline", ""),
            "verification": rec_data.get("verification", ""),
            "warnings": rec_data.get("warnings", []),
            "steps_json": rec_data.get("steps", []), "steps": rec_data.get("steps", []),
            "root_cause": rec_data.get("root_cause", ""),
            "summary": rec_data.get("summary", ""),
            "resource_count": service_data["resource_count"],
        })
    session.add(rec)
    return rec


def main():
    print("=" * 70)
    print("  AI Cost Optimization - GPT-4o Recommendation Generator")
    print("=" * 70)
    db = get_database()
    session = db.get_session_factory()()

    try:
        # Check existing
        existing = {r[0] for r in session.query(AIRecommendation.title).all()}
        if existing:
            print(f"\n  Skipping {len(existing)} already-generated recommendations")

        # ── Service-level recommendations ──
        services = session.query(
            CostRecord.service_name, sqla_func.sum(CostRecord.cost).label("total_cost"),
        ).group_by(CostRecord.service_name).having(sqla_func.sum(CostRecord.cost) > 0.10
        ).order_by(desc("total_cost")).all()
        services = [s for s in services if s.service_name not in
                    {r[0] for r in session.query(AIRecommendation.service_name).distinct().all()}]

        print(f"  {len(services)} services to process\n")
        generated = 0
        for i, svc in enumerate(services):
            total_cost = float(svc.total_cost)
            print(f"  [{i+1}/{len(services)}] {svc.service_name:40s} ${total_cost:>10,.2f} ... ", end="", flush=True)
            try:
                data = get_service_cost_data(session, svc.service_name)
                rec_data = call_gpt4o(data)
                rec = persist_recommendation(session, data, rec_data)
                session.commit()
                print(f"OK saves ${float(rec.potential_savings):,.2f}/mo")
                generated += 1
                if i < len(services) - 1: time.sleep(3)
            except Exception as e:
                print(f"FAIL {str(e)[:60]}")
                session.rollback()

        # ── Resource-level recommendations ──
        print(f"\n  Generating resource-level recommendations...")
        start_30d = datetime.utcnow() - timedelta(days=30)
        top_resources = session.query(
            CostRecord.resource_name, CostRecord.resource_group, CostRecord.resource_type,
            CostRecord.service_name, CostRecord.subscription_id,
            sqla_func.sum(CostRecord.cost).label("cost"),
            sqla_func.avg(CostRecord.cost).label("avg_cost"),
            sqla_func.max(CostRecord.cost).label("max_cost"),
        ).filter(CostRecord.date >= start_30d
        ).group_by(CostRecord.resource_name, CostRecord.resource_group,
                   CostRecord.resource_type, CostRecord.service_name, CostRecord.subscription_id
        ).having(sqla_func.sum(CostRecord.cost) > 500
        ).order_by(desc("cost")).limit(30).all()

        existing_titles = {r[0] for r in session.query(AIRecommendation.title).all()}
        res_gen = 0
        for j, res in enumerate(top_resources):
            if any(res.resource_name in t for t in existing_titles):
                continue
            res_cost = float(res.cost)
            print(f"  [R{j+1}] {res.resource_name[:35]:35s} ({res.service_name[:20]}) ${res_cost:>10,.2f} ... ", end="", flush=True)
            resource_data = {
                "service_name": res.service_name, "resource_name": res.resource_name,
                "resource_group": res.resource_group, "resource_type": res.resource_type,
                "subscription_id": res.subscription_id,
                "total_cost_30d": round(res_cost, 2), "projected_monthly_cost": round(res_cost, 2),
                "resource_count": 1, "resource_group_count": 1,
                "daily_avg_cost": round(float(res.avg_cost or 0), 4), "daily_min_cost": 0,
                "daily_max_cost": round(float(res.max_cost or 0), 4),
                "top_resources": [{"name": res.resource_name, "resource_group": res.resource_group,
                    "type": res.resource_type, "cost_30d": round(res_cost, 2)}],
            }
            try:
                rec_data = call_gpt4o(resource_data)
                rec_data["title"] = f"{res.resource_name}: {rec_data.get('title', 'Optimize')}"[:500]
                rec = persist_recommendation(session, resource_data, rec_data)
                rec.subscription_id = res.subscription_id
                session.commit()
                print(f"OK saves ${float(rec.potential_savings):,.2f}/mo")
                res_gen += 1
                existing_titles.add(rec_data["title"])
                if j < len(top_resources) - 1: time.sleep(3)
            except Exception as e:
                print(f"FAIL {str(e)[:60]}")
                session.rollback()
        generated += res_gen
        print(f"  Resource-level: {res_gen} recommendations")

        # Tag top recommendations as architecture reviews for Grafana
        try:
            session.execute(text("ALTER TABLE ai_recommendations ADD COLUMN IF NOT EXISTS recommendation_type VARCHAR(50)"))
            session.commit()
        except Exception: session.rollback()
        top5 = session.query(AIRecommendation.id).order_by(desc(AIRecommendation.potential_savings)).limit(5).all()
        if top5:
            session.execute(text("UPDATE ai_recommendations SET recommendation_type = 'architecture_review' WHERE id = ANY(:ids)"), {"ids": [r.id for r in top5]})
            session.commit()

        total_savings = float(session.query(sqla_func.sum(AIRecommendation.potential_savings)).scalar() or 0)
        total_recs = session.query(sqla_func.count(AIRecommendation.id)).scalar() or 0
        print(f"\n{'=' * 70}")
        print(f"  Generated {generated} new recommendations ({total_recs} total)")
        print(f"  Total potential savings: ${total_savings:,.2f}/month")
        print(f"{'=' * 70}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
