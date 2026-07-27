"""
Spark / Databricks Analysis API Endpoints (Tier 3)

  - /api/v1/spark/analyse          – analyse a specific job/run
  - /api/v1/spark/analyse-code     – analyse code + plan directly (offline)
  - /api/v1/spark/analyses         – list past analyses
  - /api/v1/spark/top-expensive    – batch-analyse top expensive jobs
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.common.database import get_session
from src.models import SparkJobAnalysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/spark", tags=["Spark Analysis (Tier 3)"])


# ── Request / Response ──


class SparkAnalyseRequest(BaseModel):
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    workspace_url: Optional[str] = None
    databricks_token: Optional[str] = None


class SparkCodeAnalyseRequest(BaseModel):
    """For offline analysis without Databricks connectivity."""
    physical_plan: str
    code: str = ""
    job_name: str = "offline_analysis"


class SparkIssue(BaseModel):
    pattern_id: str
    severity: str
    title: str
    description: str
    suggestion: str
    code_fix: Optional[str] = None
    estimated_impact: str = ""


class SparkAnalysisResponse(BaseModel):
    job_id: Optional[str]
    run_id: Optional[str]
    job_name: str = ""
    score: float
    issues_found: int
    issues: List[SparkIssue]
    ai_recommendations: list = []
    cost: dict = {}
    plan_summary: dict = {}
    recommendation_ids: List[str] = []


class SparkAnalysisListItem(BaseModel):
    id: int
    job_id: str
    job_name: Optional[str]
    run_id: Optional[str]
    run_date: Optional[datetime]
    duration_seconds: Optional[int]
    total_cost: Optional[float]
    overall_score: Optional[float]
    issues_count: int
    status: str

    class Config:
        from_attributes = True


# ── Endpoints ──


@router.post("/analyse", response_model=SparkAnalysisResponse)
def analyse_spark_job(
    body: SparkAnalyseRequest,
    db: Session = Depends(get_session),
):
    """
    Analyse a Spark/Databricks job by fetching its metadata, execution plan,
    and notebook code from the Databricks API. Returns detected anti-patterns
    and AI-powered code recommendations.
    """
    from src.recommendations.spark_analyzer.cost_correlator import SparkCostAnalyser
    from src.recommendations.spark_analyzer.log_collector import DatabricksClient

    client = DatabricksClient(
        workspace_url=body.workspace_url,
        token=body.databricks_token,
    )
    analyser = SparkCostAnalyser(db, databricks_client=client)

    try:
        result = analyser.analyse_job(job_id=body.job_id, run_id=body.run_id)
    except Exception as exc:
        raise HTTPException(500, f"Analysis failed: {exc}")

    return SparkAnalysisResponse(**result)


@router.post("/analyse-code", response_model=SparkAnalysisResponse)
def analyse_spark_code(
    body: SparkCodeAnalyseRequest,
    db: Session = Depends(get_session),
):
    """
    Offline analysis: provide a Spark physical execution plan and/or PySpark
    code directly. No Databricks connectivity required.

    Great for:
      - CI/CD pipelines (analyse before deploy)
      - Local development
      - Reviewing code in pull requests
    """
    from src.recommendations.spark_analyzer.cost_correlator import SparkCostAnalyser

    analyser = SparkCostAnalyser(db)
    result = analyser.analyse_job(
        physical_plan=body.physical_plan,
        code=body.code,
    )

    return SparkAnalysisResponse(**result)


@router.get("/analyses", response_model=List[SparkAnalysisListItem])
def list_analyses(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """List past Spark job analyses."""
    rows = (
        db.query(SparkJobAnalysis)
        .order_by(desc(SparkJobAnalysis.created_at))
        .limit(limit)
        .all()
    )
    return [
        SparkAnalysisListItem(
            id=r.id,
            job_id=r.job_id,
            job_name=r.job_name,
            run_id=r.run_id,
            run_date=r.run_date,
            duration_seconds=r.duration_seconds,
            total_cost=float(r.total_cost) if r.total_cost else None,
            overall_score=r.overall_score,
            issues_count=len(r.plan_issues) if r.plan_issues else 0,
            status=r.status,
        )
        for r in rows
    ]


@router.post("/top-expensive")
def analyse_top_expensive(
    top_n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_session),
):
    """Batch-analyse the top N most expensive Databricks jobs."""
    from src.recommendations.spark_analyzer.cost_correlator import SparkCostAnalyser

    analyser = SparkCostAnalyser(db)
    results = analyser.analyse_top_expensive_jobs(top_n=top_n)

    return {
        "jobs_analysed": len(results),
        "total_issues": sum(r.get("issues_found", 0) for r in results),
        "results": results,
    }


@router.get("/scorecard/{job_id}")
def get_scorecard(
    job_id: str,
    run_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Get a human-readable scorecard for a Spark/Databricks job."""
    from src.recommendations.spark_analyzer.cost_correlator import SparkCostAnalyser

    analyser = SparkCostAnalyser(db)
    scorecard = analyser.generate_scorecard(job_id=job_id, run_id=run_id)

    if scorecard.startswith("No Spark"):
        from fastapi import HTTPException
        raise HTTPException(404, scorecard)

    return {"job_id": job_id, "scorecard": scorecard}
