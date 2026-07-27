"""Reformat all AI recommendation descriptions using stored metadata."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "dev")

from src.common.database import get_database
from sqlalchemy import text


def fmt(title, svc, cost, savings, pct, effort, meta_json):
    try:
        m = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
    except Exception:
        m = {}

    risk = m.get("risk_level", "low").upper()
    timeline = m.get("expected_timeline", "1-2 weeks")
    verification = m.get("verification", "Monitor costs for 7 days.")
    warnings = m.get("warnings", [])
    steps = m.get("steps", m.get("steps_json", []))
    root_cause = m.get("root_cause", "")
    summary = m.get("summary", "")
    res_count = m.get("resource_count", 0)
    c = float(cost or 0)
    s = float(savings or 0)
    p = float(pct or 0)

    L = []
    L.append("=" * 72)
    L.append(f"  {svc}")
    L.append(f"  Monthly Cost: ${c:,.2f}  |  Resources: {res_count}  |  Risk: {risk}")
    L.append("=" * 72)
    L.append("")
    L.append("  +-----------------------------------------------------------+")
    L.append(f"  |  POTENTIAL SAVINGS: ${s:,.2f}/month ({p:.0f}%)")
    L.append(f"  |  Effort: {effort or 'hours':<12}  Timeline: {timeline}")
    L.append("  +-----------------------------------------------------------+")
    L.append("")

    if root_cause:
        L.append("  -- ROOT CAUSE " + "-" * 55)
        L.append("")
        for sent in root_cause.split(". "):
            t = sent.strip()
            if t:
                if not t.endswith("."):
                    t += "."
                L.append(f"  {t}")
        L.append("")

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

    if steps:
        L.append("  -- IMPLEMENTATION STEPS " + "-" * 46)
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

            if cli:
                L.append("  |")
                L.append("  |  CLI Command:")
                L.append(f"  |  > {cli}")
            if portal:
                L.append("  |")
                L.append("  |  Portal:")
                L.append(f"  |  > {portal}")

            L.append("  |")
            parts = []
            if et:
                parts.append(f"Time: {et}")
            if sr and sr != "none":
                parts.append(f"Risk: {sr.upper()}")
            if parts:
                L.append(f"  |  {' | '.join(parts)}")
            if rb and sr not in ("none", None):
                L.append(f"  |  Rollback: {rb}")
            L.append("  |")
            L.append("  +" + "-" * 58 + "+")
            L.append("")

    L.append("  -- VERIFICATION " + "-" * 53)
    L.append("")
    L.append(f"  {verification}")
    L.append("")

    if warnings:
        L.append("  -- WARNINGS " + "-" * 57)
        L.append("")
        for w in warnings:
            L.append(f"  [!] {w}")
        L.append("")

    L.append("=" * 72)
    return "\n".join(L)


db = get_database()
session = db.get_session_factory()()

rows = session.execute(text(
    "SELECT id, title, service_name, current_cost, potential_savings, "
    "savings_percentage, implementation_effort, metadata "
    "FROM ai_recommendations ORDER BY potential_savings DESC"
)).fetchall()

print(f"Reformatting {len(rows)} recommendations...")
n = 0
for row in rows:
    rid, title, svc, cost, savings, pct, effort, meta = row
    new_desc = fmt(title, svc, cost, savings, pct, effort, meta)
    session.execute(text("UPDATE ai_recommendations SET description = :d WHERE id = :i"), {"d": new_desc, "i": rid})
    n += 1
    print(f"  [{n}/{len(rows)}] {svc}")

session.commit()
session.close()
print(f"\nDone! Reformatted {n} recommendations.")
