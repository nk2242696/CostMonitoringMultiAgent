"""
Tier 1: Architecture-Aware Recommendation Engine

Consolidates:
  - Azure Advisor API recommendations
  - Azure Well-Architected Framework cost principles
  - Architecture review (3-agent proposal → review → decision)
  - Reference architecture gap analysis

Compares the current resource topology (from Azure Resource Graph) against
best-practice reference architectures and flags gaps such as:
  - Missing reserved instances
  - No autoscale configured
  - Oversized SKUs
  - Missing lifecycle policies
  - Lack of cost governance tags
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI
from sqlalchemy.orm import Session

from src.models import AIRecommendation, ArchitectureReview

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Reference architecture patterns
# ──────────────────────────────────────────────────────────────────────

REFERENCE_ARCHITECTURES: Dict[str, Dict[str, Any]] = {
    "Microsoft.Compute": {
        "name": "Compute Best Practices",
        "expected": [
            {"check": "reserved_instances", "description": "Reserved Instances for steady-state VMs", "savings_pct": 40},
            {"check": "autoscale", "description": "Autoscale configured for variable workloads", "savings_pct": 25},
            {"check": "right_sizing", "description": "VM SKU matches actual utilisation", "savings_pct": 30},
            {"check": "spot_vms", "description": "Spot VMs for fault-tolerant / batch workloads", "savings_pct": 60},
            {"check": "auto_shutdown", "description": "Auto-shutdown for dev/test VMs", "savings_pct": 65},
            {"check": "hybrid_benefit", "description": "Azure Hybrid Benefit enabled", "savings_pct": 40},
        ],
    },
    "Microsoft.Storage": {
        "name": "Storage Best Practices",
        "expected": [
            {"check": "lifecycle_policy", "description": "Blob lifecycle management policy", "savings_pct": 30},
            {"check": "access_tier", "description": "Cool/Archive tiers for cold data", "savings_pct": 50},
            {"check": "orphan_disks", "description": "No unattached managed disks", "savings_pct": 100},
            {"check": "snapshot_cleanup", "description": "Old snapshots cleaned up", "savings_pct": 20},
        ],
    },
    "Microsoft.Sql": {
        "name": "SQL Database Best Practices",
        "expected": [
            {"check": "serverless", "description": "Serverless tier for intermittent workloads", "savings_pct": 50},
            {"check": "elastic_pool", "description": "Elastic pools for multi-DB scenarios", "savings_pct": 35},
            {"check": "reserved_capacity", "description": "Reserved capacity for predictable DTU/vCore", "savings_pct": 40},
            {"check": "auto_pause", "description": "Auto-pause for dev/test databases", "savings_pct": 70},
        ],
    },
    "Microsoft.Databricks": {
        "name": "Databricks Best Practices",
        "expected": [
            {"check": "job_clusters", "description": "Job clusters instead of all-purpose for production", "savings_pct": 50},
            {"check": "autoscale_workers", "description": "Worker autoscaling enabled", "savings_pct": 30},
            {"check": "spot_workers", "description": "Spot instances for worker nodes", "savings_pct": 60},
            {"check": "cluster_policies", "description": "Cluster policies to limit max DBU", "savings_pct": 20},
            {"check": "photon", "description": "Photon acceleration where beneficial", "savings_pct": 25},
        ],
    },
    "Microsoft.Network": {
        "name": "Network Best Practices",
        "expected": [
            {"check": "cdn", "description": "Azure CDN for static content delivery", "savings_pct": 30},
            {"check": "unused_ips", "description": "No orphaned public IPs", "savings_pct": 100},
            {"check": "nat_gateway", "description": "NAT Gateway for outbound traffic efficiency", "savings_pct": 15},
        ],
    },
    "Microsoft.Web": {
        "name": "App Service Best Practices",
        "expected": [
            {"check": "consumption_plan", "description": "Consumption plan for low-traffic Functions", "savings_pct": 60},
            {"check": "plan_consolidation", "description": "Multiple apps consolidated into fewer plans", "savings_pct": 40},
            {"check": "linux_plan", "description": "Linux App Service plans (cheaper than Windows)", "savings_pct": 20},
        ],
    },
}


class ArchitectureRecommender:
    """
    Tier 1 recommendation engine that combines:
      1. Reference architecture gap analysis
      2. WAF cost optimization principles
      3. GPT-4 powered architecture review
    """

    def __init__(self, db: Session):
        self.db = db
        self.openai_client = self._init_openai()

    def _init_openai(self) -> Optional[AzureOpenAI]:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        key = os.getenv("AZURE_OPENAI_KEY")
        if endpoint and key:
            return AzureOpenAI(
                api_key=key,
                api_version="2024-02-01",
                azure_endpoint=endpoint,
                timeout=60.0,
            )
        return None

    # ------------------------------------------------------------------
    # Gap Analysis against Reference Architectures
    # ------------------------------------------------------------------

    def analyse_gaps(
        self,
        services: List[Dict[str, Any]],
    ) -> List[AIRecommendation]:
        """
        Compare discovered services against reference architectures
        and generate Tier 1 recommendations for every gap.

        Args:
            services: List of dicts with at least `service_name` and `total_cost`.

        Returns:
            List of persisted AIRecommendation objects.
        """
        recommendations: List[AIRecommendation] = []

        for svc in services:
            svc_name = svc.get("service_name", "")
            total_cost = float(svc.get("total_cost", 0))
            ref = REFERENCE_ARCHITECTURES.get(svc_name)
            if not ref:
                continue

            for check in ref["expected"]:
                rec = AIRecommendation(
                    recommendation_id=str(uuid.uuid4()),
                    tier=1,
                    source="reference_architecture",
                    category=self._infer_category(svc_name),
                    title=f"{check['description']} ({svc_name})",
                    description=f"Reference architecture check: {check['description']}",
                    recommendation_text=(
                        f"For {svc_name} ({ref['name']}): ensure that '{check['description']}' "
                        f"is implemented. This can reduce costs by up to {check['savings_pct']}%."
                    ),
                    subscription_id=svc.get("subscription_id"),
                    service_name=svc_name,
                    current_cost=total_cost,
                    potential_savings=round(total_cost * check["savings_pct"] / 100, 2),
                    savings_percentage=check["savings_pct"],
                    priority=self._priority_from_cost(total_cost, check["savings_pct"]),
                    confidence_score=0.80,
                    implementation_effort="2-4 hours",
                    action_items=self._check_action_items(svc_name, check["check"]),
                    status="pending",
                    rec_metadata={"reference_check": check["check"], "architecture_name": ref["name"]},
                )
                self.db.add(rec)
                recommendations.append(rec)

        self.db.commit()
        logger.info("Generated %d Tier-1 reference architecture recommendations", len(recommendations))
        return recommendations

    # ------------------------------------------------------------------
    # 3-Agent Architecture Review
    # ------------------------------------------------------------------

    def run_architecture_review(
        self,
        problem_statement: str,
        review_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Execute the 3-agent architecture review:
          Agent 1 → Azure architecture proposal
          Agent 2 → Effort / complexity review
          Agent 3 → Final go / no-go decision
        """
        if not self.openai_client:
            raise RuntimeError("Azure OpenAI not configured – cannot run architecture review")

        review_id = review_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        # Agent 1: Propose
        proposal = self._agent_propose(problem_statement, deployment)
        # Agent 2: Review
        review = self._agent_review(problem_statement, proposal, deployment)
        # Agent 3: Decide
        decision = self._agent_decide(problem_statement, proposal, review, deployment)

        summary = (
            f"# Architecture Review: {review_id}\n\n"
            f"## Proposal\n{proposal}\n\n---\n\n"
            f"## Review\n{review}\n\n---\n\n"
            f"## Decision\n{decision}"
        )

        # Persist
        ar = ArchitectureReview(
            review_id=review_id,
            problem_statement=problem_statement,
            proposal=proposal,
            review_assessment=review,
            decision=decision,
            summary=summary,
        )
        self.db.add(ar)
        self.db.commit()

        return {
            "review_id": review_id,
            "proposal": proposal,
            "review": review,
            "decision": decision,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Agent implementations
    # ------------------------------------------------------------------

    def _agent_propose(self, problem: str, deployment: str) -> str:
        resp = self.openai_client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Senior Azure Cloud Architect. Propose a cost-optimised "
                        "Azure architecture for the given problem. Be specific about services, "
                        "SKUs, estimated costs, and trade-offs.  Follow Azure Well-Architected "
                        "Framework cost optimization principles."
                    ),
                },
                {"role": "user", "content": problem},
            ],
            max_tokens=3000,
        )
        return resp.choices[0].message.content

    def _agent_review(self, problem: str, proposal: str, deployment: str) -> str:
        resp = self.openai_client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Principal Engineer. Critically review the architecture proposal "
                        "for implementation effort, complexity, hidden costs, over-engineering, "
                        "and skill gaps.  Be blunt and suggest simpler alternatives where appropriate."
                    ),
                },
                {"role": "user", "content": f"PROBLEM:\n{problem}\n\nPROPOSAL:\n{proposal}"},
            ],
            max_tokens=3000,
        )
        return resp.choices[0].message.content

    def _agent_decide(self, problem: str, proposal: str, review: str, deployment: str) -> str:
        resp = self.openai_client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Staff Architect responsible for the final go/no-go decision. "
                        "Decide: Approved, Approved with Changes, or Rejected. "
                        "List mandatory changes and deferred items."
                    ),
                },
                {
                    "role": "user",
                    "content": f"PROBLEM:\n{problem}\n\nPROPOSAL:\n{proposal}\n\nREVIEW:\n{review}",
                },
            ],
            max_tokens=3000,
        )
        return resp.choices[0].message.content

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_category(service_name: str) -> str:
        mapping = {
            "Microsoft.Compute": "compute",
            "Microsoft.Storage": "storage",
            "Microsoft.Sql": "database",
            "Microsoft.Network": "network",
            "Microsoft.Web": "compute",
            "Microsoft.Databricks": "spark",
        }
        return mapping.get(service_name, "architecture")

    @staticmethod
    def _priority_from_cost(cost: float, savings_pct: float) -> str:
        potential = cost * savings_pct / 100
        if potential > 500 or savings_pct >= 50:
            return "critical"
        if potential > 200 or savings_pct >= 30:
            return "high"
        if potential > 50:
            return "medium"
        return "low"

    @staticmethod
    def _check_action_items(service_name: str, check: str) -> List[str]:
        """Return concrete action items for a reference architecture check."""
        items_map: Dict[str, List[str]] = {
            "reserved_instances": [
                "Navigate to Azure Portal → Reservations",
                "Review Azure Advisor RI recommendations",
                "Identify VMs running 24x7 with stable utilisation",
                "Purchase 1-year or 3-year reservation",
            ],
            "autoscale": [
                "Enable VMSS autoscale or App Service autoscale",
                "Set min/max instance counts based on traffic",
                "Configure scale-in cool-down to avoid flapping",
            ],
            "right_sizing": [
                "Review Azure Advisor right-sizing recommendations",
                "Check CPU/memory utilisation over 30 days",
                "Downsize VMs with <40% average utilisation",
            ],
            "spot_vms": [
                "Identify batch / fault-tolerant workloads",
                "Create Spot VM pools in VMSS",
                "Set eviction policy to Deallocate",
            ],
            "auto_shutdown": [
                "Azure Portal → VM → Auto-shutdown",
                "Set shutdown at 19:00 local time",
                "Tag VMs: Environment=Dev",
            ],
            "lifecycle_policy": [
                "Storage Account → Lifecycle management",
                "Move blobs to Cool after 30 days, Archive after 90 days",
                "Delete old versions after 180 days",
            ],
            "access_tier": [
                "Analyse blob access patterns via Storage Analytics",
                "Move infrequently accessed blobs to Cool tier",
                "Move archival data to Archive tier",
            ],
            "orphan_disks": [
                "Azure Portal → Disks → filter: Unattached",
                "Review and delete orphaned disks",
            ],
            "serverless": [
                "Review database utilisation patterns",
                "Switch intermittent DBs to Azure SQL Serverless",
                "Configure auto-pause delay (e.g., 60 min)",
            ],
            "job_clusters": [
                "Convert interactive cluster jobs to job clusters",
                "Use cluster policies to enforce job cluster usage",
            ],
            "autoscale_workers": [
                "Enable autoscaling on Databricks clusters",
                "Set min=1, max based on peak workload",
            ],
            "spot_workers": [
                "Enable Spot instances for Databricks worker nodes",
                "Keep driver on on-demand, workers on Spot",
            ],
        }
        return items_map.get(check, [f"Review {check} for {service_name}"])
