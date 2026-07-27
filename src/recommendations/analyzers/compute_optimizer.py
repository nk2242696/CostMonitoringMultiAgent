"""
Compute Optimizer

Analyzes compute resources (VMs, App Services, AKS, Functions) and
generates right-sizing, reserved-instance, and shutdown recommendations.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from src.models import AIRecommendation, CostRecord, ResourceMetadata

logger = logging.getLogger(__name__)

# Azure VM SKU families and relative pricing tiers
VM_SKU_TIERS = {
    "Standard_B": {"tier": "burstable", "relative_cost": 0.3},
    "Standard_D": {"tier": "general", "relative_cost": 1.0},
    "Standard_E": {"tier": "memory", "relative_cost": 1.2},
    "Standard_F": {"tier": "compute", "relative_cost": 0.9},
    "Standard_L": {"tier": "storage", "relative_cost": 1.1},
    "Standard_M": {"tier": "memory_intensive", "relative_cost": 3.0},
    "Standard_N": {"tier": "gpu", "relative_cost": 5.0},
}

# Compute service types to analyze
COMPUTE_SERVICES = [
    "Microsoft.Compute",
    "microsoft.compute",
    "Virtual Machines",
    "Microsoft.Web",
    "microsoft.web",
    "App Service",
    "Microsoft.ContainerService",
    "Azure Kubernetes Service",
    "Microsoft.ContainerInstance",
    "Microsoft.Functions",
]


class ComputeOptimizer:
    """
    Analyze compute workloads and generate optimization recommendations.

    Capabilities:
    - VM right-sizing (downsize over-provisioned VMs)
    - Idle/stopped VM detection
    - Reserved Instance opportunity analysis
    - Dev/Test environment shutdown scheduling
    - B-series burstable VM suggestions for low-utilization workloads
    - App Service plan consolidation
    """

    def __init__(self, db: Session):
        self.db = db

    def analyze(
        self,
        subscription_id: Optional[str] = None,
        lookback_days: int = 30,
    ) -> List[AIRecommendation]:
        """
        Run all compute optimization analyses and return recommendations.
        """
        recommendations: List[AIRecommendation] = []

        recommendations.extend(self._detect_idle_vms(subscription_id, lookback_days))
        recommendations.extend(self._suggest_rightsizing(subscription_id, lookback_days))
        recommendations.extend(self._suggest_reserved_instances(subscription_id, lookback_days))
        recommendations.extend(self._detect_dev_test_schedules(subscription_id, lookback_days))
        recommendations.extend(self._suggest_burstable_vms(subscription_id, lookback_days))

        if recommendations:
            self.db.add_all(recommendations)
            self.db.commit()
            logger.info("Generated %d compute optimisation recommendations", len(recommendations))

        return recommendations

    # ------------------------------------------------------------------
    # Idle VM detection
    # ------------------------------------------------------------------

    def _detect_idle_vms(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """Detect VMs with very low or no recent cost activity."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Find compute resources with very low average daily cost
        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.avg(CostRecord.cost).label("avg_daily_cost"),
                sqla_func.count(sqla_func.distinct(sqla_func.date(CostRecord.date))).label("active_days"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(COMPUTE_SERVICES),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
            )
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            active_days = row.active_days or 0
            avg_cost = float(row.avg_daily_cost or 0)

            # Consider idle if active < 30% of lookback window or avg cost < $1/day
            is_idle = active_days < (lookback_days * 0.3) or avg_cost < 1.0

            if is_idle and float(row.total_cost or 0) > 0:
                monthly_savings = float(row.total_cost) * (30 / max(lookback_days, 1))
                rec = AIRecommendation(
                    recommendation_id=str(uuid.uuid4()),
                    tier=1,
                    source="rule_based",
                    category="compute",
                    title=f"Idle compute resource: {row.resource_name}",
                    description=(
                        f"Resource '{row.resource_name}' appears idle — only active "
                        f"{active_days}/{lookback_days} days with avg daily cost ${avg_cost:.2f}. "
                        f"Consider stopping or deallocating this resource."
                    ),
                    recommendation_text=(
                        f"Deallocate or delete idle VM/compute resource '{row.resource_name}'. "
                        f"If needed intermittently, consider auto-start/stop scheduling."
                    ),
                    subscription_id=row.subscription_id,
                    resource_id=row.resource_id,
                    service_name=row.service_name,
                    resource_type=row.resource_type,
                    current_cost=Decimal(str(round(float(row.total_cost), 2))),
                    potential_savings=Decimal(str(round(monthly_savings * 0.9, 2))),
                    savings_percentage=Decimal("90.00"),
                    priority="high" if monthly_savings > 100 else "medium",
                    confidence_score=Decimal("0.85"),
                    implementation_effort="hours",
                    action_items=[
                        "Review resource utilisation metrics in Azure Monitor",
                        "Confirm the resource is not actively used",
                        "Deallocate or delete the resource",
                        "Set up auto-start/stop if intermittent use is needed",
                    ],
                    status="pending",
                )
                recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Right-sizing
    # ------------------------------------------------------------------

    def _suggest_rightsizing(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Suggest downsizing VMs that are consistently under-utilised.
        Uses cost patterns as a proxy for utilisation.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # High-cost VMs with declining cost trend
        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.max(CostRecord.cost).label("max_daily_cost"),
                sqla_func.avg(CostRecord.cost).label("avg_daily_cost"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(COMPUTE_SERVICES),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
            )
            .having(sqla_func.sum(CostRecord.cost) > 50)  # Focus on > $50/month
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            avg_cost = float(row.avg_daily_cost or 0)
            max_cost = float(row.max_daily_cost or 0)

            # If average is significantly lower than max, likely over-provisioned
            if max_cost > 0 and avg_cost < max_cost * 0.5:
                savings_pct = round(((max_cost - avg_cost) / max_cost) * 100 * 0.4, 2)  # conservative 40%
                monthly_savings = float(row.total_cost) * savings_pct / 100

                if monthly_savings > 10:  # Worth recommending if > $10/month
                    rec = AIRecommendation(
                        recommendation_id=str(uuid.uuid4()),
                        tier=1,
                        source="rule_based",
                        category="compute",
                        title=f"Right-size VM: {row.resource_name}",
                        description=(
                            f"Resource '{row.resource_name}' has avg daily cost ${avg_cost:.2f} vs "
                            f"peak ${max_cost:.2f}, suggesting it's over-provisioned. "
                            f"Consider a smaller SKU."
                        ),
                        recommendation_text=(
                            f"Review '{row.resource_name}' CPU/memory metrics and resize to a "
                            f"smaller SKU. Estimated {savings_pct:.0f}% cost reduction."
                        ),
                        subscription_id=row.subscription_id,
                        resource_id=row.resource_id,
                        service_name=row.service_name,
                        resource_type=row.resource_type,
                        current_cost=Decimal(str(round(float(row.total_cost), 2))),
                        potential_savings=Decimal(str(round(monthly_savings, 2))),
                        savings_percentage=Decimal(str(savings_pct)),
                        priority="medium",
                        confidence_score=Decimal("0.70"),
                        implementation_effort="hours",
                        action_items=[
                            "Check Azure Monitor CPU/memory utilisation",
                            "Identify a smaller VM SKU with adequate capacity",
                            "Schedule a maintenance window for resize",
                            "Test application performance after resize",
                        ],
                        status="pending",
                    )
                    recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Reserved Instance opportunities
    # ------------------------------------------------------------------

    def _suggest_reserved_instances(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Identify consistently running VMs that would benefit from
        Reserved Instances (1-year or 3-year commitments).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.count(sqla_func.distinct(sqla_func.date(CostRecord.date))).label("active_days"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(COMPUTE_SERVICES),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
            )
            .having(
                sqla_func.count(sqla_func.distinct(sqla_func.date(CostRecord.date))) > lookback_days * 0.8
            )
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            monthly_cost = float(row.total_cost) * (30 / max(lookback_days, 1))
            if monthly_cost < 50:
                continue

            # RI typically saves 30-60% for 1-year, 50-72% for 3-year
            savings_1yr = round(monthly_cost * 0.35, 2)
            savings_3yr = round(monthly_cost * 0.55, 2)

            rec = AIRecommendation(
                recommendation_id=str(uuid.uuid4()),
                tier=1,
                source="rule_based",
                category="compute",
                title=f"Reserved Instance opportunity: {row.resource_name}",
                description=(
                    f"'{row.resource_name}' has been running {row.active_days}/{lookback_days} days "
                    f"(monthly cost ~${monthly_cost:.2f}). A 1-year RI could save ~${savings_1yr:.2f}/mo, "
                    f"3-year could save ~${savings_3yr:.2f}/mo."
                ),
                recommendation_text=(
                    f"Purchase a Reserved Instance for '{row.resource_name}'. "
                    f"Consistently running workloads benefit significantly from RI commitments."
                ),
                subscription_id=row.subscription_id,
                resource_id=row.resource_id,
                service_name=row.service_name,
                current_cost=Decimal(str(round(monthly_cost, 2))),
                potential_savings=Decimal(str(savings_1yr)),
                savings_percentage=Decimal("35.00"),
                priority="high" if monthly_cost > 200 else "medium",
                confidence_score=Decimal("0.90"),
                implementation_effort="hours",
                action_items=[
                    "Confirm workload will continue running for 1-3 years",
                    "Check Azure Advisor for specific RI recommendations",
                    "Compare 1-year vs 3-year commitment options",
                    "Purchase RI through Azure portal or EA agreement",
                ],
                status="pending",
            )
            recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Dev/Test shutdown schedules
    # ------------------------------------------------------------------

    def _detect_dev_test_schedules(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Identify resources tagged as dev/test that run 24/7 and
        suggest shutdown scheduling.
        """
        # Look for resources with dev/test indicators in tags or name
        dev_test_keywords = ["dev", "test", "staging", "sandbox", "poc", "demo", "uat"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(COMPUTE_SERVICES),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
            )
            .having(sqla_func.sum(CostRecord.cost) > 30)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            name_lower = (row.resource_name or "").lower()
            is_dev_test = any(kw in name_lower for kw in dev_test_keywords)

            if not is_dev_test:
                continue

            monthly_cost = float(row.total_cost) * (30 / max(lookback_days, 1))
            # 12 hrs/day shutdown = ~50% savings; 16 hrs weekday + weekends = ~65%
            savings = round(monthly_cost * 0.50, 2)

            rec = AIRecommendation(
                recommendation_id=str(uuid.uuid4()),
                tier=2,
                source="rule_based",
                category="compute",
                title=f"Schedule shutdown for dev/test: {row.resource_name}",
                description=(
                    f"'{row.resource_name}' appears to be a dev/test resource running 24/7 "
                    f"(monthly cost ~${monthly_cost:.2f}). Auto-shutdown during non-business hours "
                    f"could save ~${savings:.2f}/mo."
                ),
                recommendation_text=(
                    f"Configure auto-shutdown for '{row.resource_name}' during evenings "
                    f"and weekends. Use Azure DevTest Labs or Azure Automation."
                ),
                subscription_id=row.subscription_id,
                resource_id=row.resource_id,
                service_name=row.service_name,
                resource_type=row.resource_type,
                current_cost=Decimal(str(round(monthly_cost, 2))),
                potential_savings=Decimal(str(savings)),
                savings_percentage=Decimal("50.00"),
                priority="medium",
                confidence_score=Decimal("0.80"),
                implementation_effort="hours",
                automation_type="azure_cli",
                automation_script=self._generate_auto_shutdown_script(row.resource_name),
                action_items=[
                    "Confirm resource is not needed outside business hours",
                    "Configure auto-shutdown in Azure DevTest Labs or Automation",
                    "Set auto-start for business hours if needed",
                    "Monitor to ensure no business impact",
                ],
                status="pending",
            )
            recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Burstable VM suggestions
    # ------------------------------------------------------------------

    def _suggest_burstable_vms(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Suggest B-series burstable VMs for workloads with low average
        but occasional spikes in CPU usage (inferred from cost patterns).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.avg(CostRecord.cost).label("avg_daily_cost"),
                sqla_func.stddev(CostRecord.cost).label("cost_stddev"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(COMPUTE_SERVICES),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
            )
            .having(sqla_func.avg(CostRecord.cost) > 2)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            avg_cost = float(row.avg_daily_cost or 0)
            stddev = float(row.cost_stddev or 0)

            # High coefficient of variation = bursty workload
            cv = stddev / avg_cost if avg_cost > 0 else 0
            if cv > 0.5:  # Significant variability
                monthly_cost = float(row.total_cost) * (30 / max(lookback_days, 1))
                savings = round(monthly_cost * 0.40, 2)

                if savings > 10:
                    rec = AIRecommendation(
                        recommendation_id=str(uuid.uuid4()),
                        tier=1,
                        source="rule_based",
                        category="compute",
                        title=f"Consider B-series VM: {row.resource_name}",
                        description=(
                            f"'{row.resource_name}' shows bursty usage patterns (CV={cv:.2f}). "
                            f"B-series burstable VMs are ~40% cheaper for workloads that "
                            f"don't need constant high CPU."
                        ),
                        recommendation_text=(
                            f"Switch '{row.resource_name}' to a B-series burstable VM. "
                            f"B-series is ideal for workloads with variable CPU needs."
                        ),
                        subscription_id=row.subscription_id,
                        resource_id=row.resource_id,
                        service_name=row.service_name,
                        resource_type=row.resource_type,
                        current_cost=Decimal(str(round(monthly_cost, 2))),
                        potential_savings=Decimal(str(savings)),
                        savings_percentage=Decimal("40.00"),
                        priority="low",
                        confidence_score=Decimal("0.60"),
                        implementation_effort="hours",
                        action_items=[
                            "Review actual CPU utilisation in Azure Monitor",
                            "Verify workload is compatible with burstable CPU",
                            "Select appropriate B-series SKU",
                            "Plan resize during maintenance window",
                        ],
                        status="pending",
                    )
                    recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_auto_shutdown_script(resource_name: str) -> str:
        """Generate a sample Azure CLI auto-shutdown script."""
        return f"""# Auto-shutdown schedule for {resource_name}
# Run via Azure Cloud Shell or local Azure CLI

# Enable auto-shutdown at 7:00 PM UTC
az vm auto-shutdown --resource-group <resource-group> \\
    --name {resource_name} \\
    --time 1900 \\
    --email <notification-email>

# For auto-start, use Azure Automation Runbook:
# https://learn.microsoft.com/en-us/azure/automation/automation-solution-vm-management
"""
