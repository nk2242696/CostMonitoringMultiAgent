"""
Tier 3 – Spark Cost Correlator & AI Analyser

Brings together:
  - Cost data from cost_records (Databricks DBU / compute costs)
  - Execution plan analysis (plan_parser + pattern_detector)
  - Notebook source code
  - GPT-4 for natural-language recommendations

Produces actionable recommendations like:
  "Dataset B is 12 MB — use broadcast(df_b) instead of SortMergeJoin
   to eliminate the 4.2 GB shuffle, saving ~$18/run."
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from src.models import AIRecommendation, CostRecord, SparkJobAnalysis
from src.recommendations.spark_analyzer.log_collector import DatabricksClient, LogCollector
from src.recommendations.spark_analyzer.pattern_detector import PatternDetector, PatternIssue
from src.recommendations.spark_analyzer.plan_parser import PlanParser

logger = logging.getLogger(__name__)


class SparkCostAnalyser:
    """
    End-to-end Spark job analysis pipeline:
      1. Collect job metadata + notebook code from Databricks
      2. Parse the Spark physical execution plan
      3. Detect anti-patterns (broadcast opportunity, shuffle, skew, etc.)
      4. Correlate with Azure cost data
      5. Use GPT-4 to generate human-readable, code-aware recommendations
      6. Persist results
    """

    def __init__(
        self,
        db: Session,
        databricks_client: Optional[DatabricksClient] = None,
    ):
        self.db = db
        self.databricks = databricks_client or DatabricksClient()
        self.collector = LogCollector(self.databricks)
        self.parser = PlanParser()
        self.detector = PatternDetector()
        self._openai_client = None

    @property
    def openai_client(self):
        if self._openai_client is None:
            from openai import AzureOpenAI

            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            key = os.getenv("AZURE_OPENAI_KEY")
            if endpoint and key:
                self._openai_client = AzureOpenAI(
                    api_key=key,
                    api_version="2024-02-01",
                    azure_endpoint=endpoint,
                    timeout=60.0,
                )
        return self._openai_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse_job(
        self,
        job_id: Optional[str] = None,
        run_id: Optional[str] = None,
        physical_plan: Optional[str] = None,
        code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyse a single Spark/Databricks job run.

        You can either provide job_id/run_id (will fetch from Databricks API)
        or supply physical_plan + code directly for offline analysis.

        Returns:
            Dict with analysis results, issues found, recommendations, and cost data.
        """
        # Step 1: Collect data
        if physical_plan is None:
            job_data = self.collector.collect_job_data(job_id=job_id, run_id=run_id)
            code = code or job_data.get("code", "")
            physical_plan = physical_plan or ""  # Plan must come from Spark UI or event logs
            run_id = job_data.get("run_id", run_id)
            job_id = job_data.get("job_id", job_id)
            job_name = job_data.get("job_name", "")
            duration = job_data.get("duration_seconds", 0)
            notebook_path = job_data.get("notebook_path")
        else:
            job_name = ""
            duration = 0
            notebook_path = None

        # Step 2: Parse execution plan
        parsed_plan = self.parser.parse(physical_plan)

        # Step 3: Detect anti-patterns
        issues = self.detector.detect(
            plan=parsed_plan,
            code=code or "",
        )

        # Step 4: Correlate costs
        cost_data = self._correlate_costs(job_id, run_id)

        # Step 5: Generate AI recommendations
        ai_recommendations = []
        if issues and self.openai_client:
            ai_recommendations = self._generate_ai_recommendations(
                issues=issues,
                code=code or "",
                plan_summary=self._summarise_plan(parsed_plan),
                cost_data=cost_data,
                job_name=job_name,
            )

        # Step 6: Compute efficiency score
        score = self._compute_score(issues)

        # Step 7: Persist SparkJobAnalysis
        analysis = SparkJobAnalysis(
            job_id=str(job_id or ""),
            job_name=job_name,
            workspace_url=self.databricks.workspace_url,
            run_id=str(run_id or ""),
            run_date=datetime.utcnow(),
            duration_seconds=duration,
            dbu_cost=cost_data.get("dbu_cost"),
            compute_cost=cost_data.get("compute_cost"),
            total_cost=cost_data.get("total_cost"),
            physical_plan=physical_plan,
            plan_issues=[
                {
                    "pattern_id": i.pattern_id,
                    "severity": i.severity,
                    "title": i.title,
                    "suggestion": i.suggestion,
                }
                for i in issues
            ],
            shuffle_bytes_read=sum(s.data_size_bytes or 0 for s in parsed_plan.shuffles),
            notebook_path=notebook_path,
            code_snippet=(code or "")[:5000],
            code_suggestions=ai_recommendations,
            overall_score=score,
        )
        self.db.add(analysis)

        # Step 8: Create Tier-3 AIRecommendation records
        rec_ids = []
        for issue in issues:
            rec = AIRecommendation(
                recommendation_id=str(uuid.uuid4()),
                tier=3,
                source="spark_analyzer",
                category="spark",
                title=issue.title,
                description=issue.description,
                recommendation_text=issue.suggestion,
                service_name="Microsoft.Databricks",
                priority=issue.severity,
                confidence_score=0.85,
                implementation_effort="1-2 hours",
                action_items=[issue.suggestion],
                status="pending",
                potential_savings=cost_data.get("estimated_savings_per_run"),
                rec_metadata={
                    "pattern_id": issue.pattern_id,
                    "code_fix": issue.code_fix,
                    "affected_node": issue.affected_node,
                    "job_id": str(job_id or ""),
                    "run_id": str(run_id or ""),
                },
            )
            self.db.add(rec)
            rec_ids.append(rec.recommendation_id)

        analysis.recommendations = rec_ids
        self.db.commit()

        return {
            "job_id": job_id,
            "run_id": run_id,
            "job_name": job_name,
            "score": score,
            "issues_found": len(issues),
            "issues": [
                {
                    "pattern_id": i.pattern_id,
                    "severity": i.severity,
                    "title": i.title,
                    "description": i.description,
                    "suggestion": i.suggestion,
                    "code_fix": i.code_fix,
                    "estimated_impact": i.estimated_impact,
                }
                for i in issues
            ],
            "ai_recommendations": ai_recommendations,
            "cost": cost_data,
            "plan_summary": {
                "joins": len(parsed_plan.joins),
                "shuffles": len(parsed_plan.shuffles),
                "sorts": parsed_plan.sorts,
                "total_nodes": parsed_plan.total_nodes,
            },
            "recommendation_ids": rec_ids,
        }

    def analyse_top_expensive_jobs(self, top_n: int = 10) -> List[Dict]:
        """Batch-analyse the top N most expensive Databricks jobs."""
        results = []
        try:
            runs = self.databricks.list_runs(limit=top_n * 3)
            # Sort by duration as a proxy for cost
            runs.sort(key=lambda r: (r.get("end_time", 0) - r.get("start_time", 0)), reverse=True)

            for run in runs[:top_n]:
                try:
                    result = self.analyse_job(run_id=str(run["run_id"]))
                    results.append(result)
                except Exception:
                    logger.exception("Failed to analyse run %s", run.get("run_id"))
        except Exception:
            logger.exception("Failed to list Databricks runs")

        return results

    # ------------------------------------------------------------------
    # Cost correlation
    # ------------------------------------------------------------------

    def _correlate_costs(
        self,
        job_id: Optional[str],
        run_id: Optional[str],
    ) -> Dict[str, Any]:
        """Look up Databricks cost from cost_records table."""
        query = self.db.query(
            sqla_func.sum(CostRecord.cost).label("total"),
        ).filter(
            CostRecord.service_name.ilike("%databricks%"),
        )

        total = float(query.scalar() or 0)
        # Rough per-job estimate based on count
        job_count = max(
            self.db.query(sqla_func.count(CostRecord.id))
            .filter(CostRecord.service_name.ilike("%databricks%"))
            .scalar() or 1,
            1,
        )
        avg_cost = total / job_count

        return {
            "total_databricks_cost": total,
            "estimated_job_cost": round(avg_cost, 2),
            "total_cost": round(avg_cost, 2),
            "dbu_cost": round(avg_cost * 0.6, 2),
            "compute_cost": round(avg_cost * 0.4, 2),
            "estimated_savings_per_run": round(avg_cost * 0.3, 2),
        }

    # ------------------------------------------------------------------
    # AI-powered code recommendations
    # ------------------------------------------------------------------

    def _generate_ai_recommendations(
        self,
        issues: List[PatternIssue],
        code: str,
        plan_summary: str,
        cost_data: Dict,
        job_name: str,
    ) -> List[Dict]:
        """Use GPT-4 to generate natural-language, code-aware recommendations."""
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        issues_text = "\n".join(
            f"- [{i.severity.upper()}] {i.title}: {i.description}" for i in issues
        )

        prompt = f"""You are a senior Spark performance engineer. Analyse this Databricks job and provide specific, actionable code recommendations.

JOB: {job_name}
ESTIMATED COST PER RUN: ${cost_data.get('estimated_job_cost', 0):.2f}

DETECTED ISSUES:
{issues_text}

EXECUTION PLAN SUMMARY:
{plan_summary}

NOTEBOOK CODE (first 3000 chars):
```python
{code[:3000]}
```

For each issue, provide:
1. **What's wrong** — explain the performance problem in plain English
2. **Why it's expensive** — relate to DBU / compute cost
3. **Exact code fix** — show the before and after PySpark code
4. **Expected improvement** — quantify the savings (e.g., "reduce shuffle from 4.2 GB to 12 MB, saving ~30% runtime")

Be extremely specific. Reference actual DataFrame names from the code.
Output as JSON array: [{{"issue": "...", "explanation": "...", "code_before": "...", "code_after": "...", "expected_savings": "..."}}]
"""

        try:
            resp = self.openai_client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are a Spark/Databricks performance optimization expert."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            import json

            content = resp.choices[0].message.content
            # Try to parse JSON from the response
            # Handle cases where the response includes markdown code blocks
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except Exception:
            logger.exception("AI recommendation generation failed")
            return [
                {
                    "issue": issue.title,
                    "explanation": issue.description,
                    "code_before": "",
                    "code_after": issue.code_fix or issue.suggestion,
                    "expected_savings": issue.estimated_impact,
                }
                for issue in issues
            ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarise_plan(plan) -> str:
        lines = []
        for j in plan.joins:
            lines.append(
                f"Join: {j.join_type} on [{', '.join(j.join_keys)}] "
                f"(left={j.left_size_bytes}, right={j.right_size_bytes})"
            )
        for s in plan.shuffles:
            lines.append(
                f"Shuffle: {s.exchange_type} keys=[{', '.join(s.partition_keys)}] "
                f"partitions={s.num_partitions} size={s.data_size_bytes}"
            )
        lines.append(f"Sorts: {plan.sorts}, Filters: {plan.filters}, Scans: {plan.scans}")
        return "\n".join(lines)

    @staticmethod
    def _compute_score(issues: List[PatternIssue]) -> float:
        """0-100 efficiency score. 100 = no issues."""
        if not issues:
            return 100.0
        severity_weights = {"critical": 25, "high": 15, "medium": 8, "low": 3}
        penalty = sum(severity_weights.get(i.severity, 5) for i in issues)
        return max(0, 100 - penalty)

    # ------------------------------------------------------------------
    # Spark Job Scorecard
    # ------------------------------------------------------------------

    def generate_scorecard(
        self,
        job_id: str = None,
        run_id: str = None,
        analysis: dict = None,
    ) -> str:
        """
        Generate a human-readable scorecard for a Spark job.

        Can work from:
          - A fresh analysis dict (from analyse_job)
          - A stored SparkJobAnalysis record (looked up by job_id/run_id)

        Returns a formatted plain-text scorecard.
        """
        # Load from DB if no analysis provided
        if analysis is None:
            q = self.db.query(SparkJobAnalysis)
            if run_id:
                q = q.filter(SparkJobAnalysis.run_id == run_id)
            elif job_id:
                q = q.filter(SparkJobAnalysis.job_id == job_id)
            else:
                q = q.order_by(SparkJobAnalysis.run_date.desc())
            record = q.first()
            if not record:
                return "No Spark job analysis found."
            analysis = {
                "job_id": record.job_id,
                "job_name": record.job_name or record.job_id,
                "cluster_type": record.cluster_type or "unknown",
                "worker_node_type": record.worker_node_type or "unknown",
                "executor_count": record.executor_count or 0,
                "duration_seconds": record.duration_seconds or 0,
                "total_cost": float(record.total_cost or 0),
                "dbu_cost": float(record.dbu_cost or 0),
                "compute_cost": float(record.compute_cost or 0),
                "score": record.overall_score or 0,
                "issues": record.plan_issues or [],
                "recommendations": record.recommendations or [],
                "run_date": record.run_date.isoformat() if record.run_date else "unknown",
                "notebook_path": record.notebook_path or "",
            }

        job_name = analysis.get("job_name", analysis.get("job_id", "Unknown"))
        cluster = f"{analysis.get('worker_node_type', '?')} x {analysis.get('executor_count', '?')} workers"
        duration_min = (analysis.get("duration_seconds", 0) or 0) / 60
        cost_per_run = analysis.get("total_cost", 0)
        dbu_cost = analysis.get("dbu_cost", 0)
        compute_cost = analysis.get("compute_cost", 0)
        score = analysis.get("score", 0)
        issues = analysis.get("issues", [])
        run_date = analysis.get("run_date", "unknown")

        L = []
        L.append("=" * 72)
        L.append(f"  SPARK JOB SCORECARD")
        L.append("=" * 72)
        L.append("")
        L.append(f"  Job:      {job_name}")
        L.append(f"  Cluster:  {cluster}")
        L.append(f"  Last Run: {run_date}")
        L.append(f"  Duration: {duration_min:.1f} min")
        L.append(f"  Cost:     ${cost_per_run:.2f} (DBU: ${dbu_cost:.2f}, Compute: ${compute_cost:.2f})")
        L.append("")

        # Score bar
        score_bar_len = 40
        filled = int(score / 100 * score_bar_len)
        bar = "█" * filled + "░" * (score_bar_len - filled)
        if score >= 80:
            grade = "GOOD"
        elif score >= 60:
            grade = "NEEDS IMPROVEMENT"
        elif score >= 40:
            grade = "POOR"
        else:
            grade = "CRITICAL"
        L.append(f"  EFFICIENCY SCORE: {score:.0f}/100 [{grade}]")
        L.append(f"  [{bar}]")
        L.append("")

        # Issues
        if issues:
            L.append("  -- ISSUES FOUND " + "-" * 53)
            L.append("")
            total_savings_per_run = 0
            for issue in issues:
                sev = issue.get("severity", "medium").upper()
                title = issue.get("title", issue.get("issue", ""))
                desc = issue.get("description", issue.get("explanation", ""))
                suggestion = issue.get("suggestion", issue.get("code_after", ""))
                savings = issue.get("estimated_impact", issue.get("expected_savings", ""))

                L.append(f"  [{sev:8s}] {title}")
                if desc:
                    # Word-wrap
                    words = desc.split()
                    line = "             "
                    for w in words:
                        if len(line) + len(w) + 1 > 70:
                            L.append(line)
                            line = "             " + w
                        else:
                            line += (" " + w) if len(line) > 13 else w
                    if line.strip():
                        L.append(line)

                if suggestion:
                    L.append(f"             Fix: {suggestion[:200]}")
                if savings:
                    L.append(f"             Savings: {savings}")
                L.append("")
        else:
            L.append("  No issues detected — job is well-optimized!")
            L.append("")

        # Metrics summary
        L.append("  -- JOB METRICS " + "-" * 54)
        L.append("")
        L.append(f"  Duration:        {duration_min:.1f} min")
        L.append(f"  Cost per run:    ${cost_per_run:.2f}")
        L.append(f"  Monthly (30x):   ${cost_per_run * 30:.2f}")
        if issues:
            # Estimate total potential savings
            L.append(f"  Issues found:    {len(issues)}")
            sev_counts = {}
            for i in issues:
                s = i.get("severity", "medium")
                sev_counts[s] = sev_counts.get(s, 0) + 1
            sev_str = ", ".join(f"{v} {k}" for k, v in sorted(sev_counts.items()))
            L.append(f"  By severity:     {sev_str}")
        L.append("")
        L.append("=" * 72)

        return "\n".join(L)
