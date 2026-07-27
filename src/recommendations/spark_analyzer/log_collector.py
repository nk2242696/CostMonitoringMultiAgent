"""
Tier 3 – Spark / Databricks Log Collector

Collects Spark event logs and job metadata from:
  - Databricks REST API (Jobs, Runs, Clusters)
  - Azure Log Analytics (Spark driver/executor logs)
  - DBFS / ABFS event log storage
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class DatabricksClient:
    """Thin wrapper around the Databricks REST API 2.x."""

    def __init__(
        self,
        workspace_url: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.workspace_url = (workspace_url or os.getenv("DATABRICKS_HOST", "")).rstrip("/")
        self.token = token or os.getenv("DATABRICKS_TOKEN", "")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    # ── Jobs & Runs ──

    def list_jobs(self, limit: int = 25) -> List[Dict]:
        resp = requests.get(
            f"{self.workspace_url}/api/2.1/jobs/list",
            headers=self.headers,
            params={"limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("jobs", [])

    def list_runs(
        self,
        job_id: Optional[str] = None,
        start_time_from: Optional[datetime] = None,
        limit: int = 25,
    ) -> List[Dict]:
        params: Dict[str, Any] = {"limit": limit}
        if job_id:
            params["job_id"] = job_id
        if start_time_from:
            params["start_time_from"] = int(start_time_from.timestamp() * 1000)
        resp = requests.get(
            f"{self.workspace_url}/api/2.1/jobs/runs/list",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("runs", [])

    def get_run(self, run_id: str) -> Dict:
        resp = requests.get(
            f"{self.workspace_url}/api/2.1/jobs/runs/get",
            headers=self.headers,
            params={"run_id": run_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_run_output(self, run_id: str) -> Dict:
        resp = requests.get(
            f"{self.workspace_url}/api/2.1/jobs/runs/get-output",
            headers=self.headers,
            params={"run_id": run_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Clusters ──

    def get_cluster(self, cluster_id: str) -> Dict:
        resp = requests.get(
            f"{self.workspace_url}/api/2.0/clusters/get",
            headers=self.headers,
            params={"cluster_id": cluster_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Spark UI / Event Logs ──

    def get_spark_event_log_url(self, cluster_id: str, run_id: str) -> Optional[str]:
        """Return the DBFS path to Spark event logs for a run."""
        try:
            cluster = self.get_cluster(cluster_id)
            log_conf = cluster.get("cluster_log_conf", {})
            dbfs_dest = log_conf.get("dbfs", {}).get("destination")
            if dbfs_dest:
                return f"{dbfs_dest}/{cluster_id}/eventlog"
        except Exception:
            pass
        return None

    # ── Notebooks ──

    def export_notebook(self, path: str) -> str:
        """Export notebook source code."""
        resp = requests.get(
            f"{self.workspace_url}/api/2.0/workspace/export",
            headers=self.headers,
            params={"path": path, "format": "SOURCE"},
            timeout=30,
        )
        resp.raise_for_status()
        import base64
        content = resp.json().get("content", "")
        return base64.b64decode(content).decode("utf-8")


class LogCollector:
    """
    High-level collector that gathers Spark job metadata,
    event logs, and notebook code for analysis.
    """

    def __init__(self, client: Optional[DatabricksClient] = None):
        self.client = client or DatabricksClient()

    def collect_job_data(
        self,
        job_id: Optional[str] = None,
        run_id: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Collect everything needed to analyse a Spark job:
          - run metadata (duration, cluster, cost)
          - notebook source code
          - Spark event log URL
        """
        if run_id:
            run = self.client.get_run(run_id)
        else:
            runs = self.client.list_runs(
                job_id=job_id,
                start_time_from=datetime.utcnow() - timedelta(days=lookback_days),
                limit=1,
            )
            if not runs:
                raise ValueError(f"No runs found for job {job_id}")
            run = runs[0]
            run_id = str(run["run_id"])

        cluster_id = run.get("cluster_instance", {}).get("cluster_id") or run.get("cluster_spec", {}).get("existing_cluster_id", "")

        # Notebook code
        notebook_path = None
        code = ""
        task = run.get("task", run.get("tasks", [{}])[0] if run.get("tasks") else {})
        nb_task = task.get("notebook_task", {})
        if nb_task:
            notebook_path = nb_task.get("notebook_path")
            if notebook_path:
                try:
                    code = self.client.export_notebook(notebook_path)
                except Exception:
                    logger.warning("Could not export notebook %s", notebook_path)

        # Duration and cost estimation
        start_ms = run.get("start_time", 0)
        end_ms = run.get("end_time", 0)
        duration_s = (end_ms - start_ms) // 1000 if end_ms and start_ms else 0

        return {
            "run_id": run_id,
            "job_id": str(run.get("job_id", job_id or "")),
            "job_name": run.get("run_name", ""),
            "cluster_id": cluster_id,
            "notebook_path": notebook_path,
            "code": code,
            "duration_seconds": duration_s,
            "state": run.get("state", {}).get("result_state", "UNKNOWN"),
            "start_time": datetime.fromtimestamp(start_ms / 1000) if start_ms else None,
            "spark_event_log_url": self.client.get_spark_event_log_url(cluster_id, run_id) if cluster_id else None,
            "raw_run": run,
        }
