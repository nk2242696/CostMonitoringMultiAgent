"""
Storage Optimizer

Analyzes Azure storage resources (Blob, Disk, File, SQL) and generates
recommendations for tier optimization, orphan cleanup, and lifecycle
management.
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

# Storage-related service types
STORAGE_SERVICES = [
    "Microsoft.Storage",
    "microsoft.storage",
    "Storage",
    "Microsoft.Compute/disks",
    "Managed Disks",
    "Microsoft.Sql",
    "microsoft.sql",
    "SQL Database",
    "Azure SQL",
    "Microsoft.DBforPostgreSQL",
    "Microsoft.DBforMySQL",
    "Microsoft.DocumentDB",
    "Cosmos DB",
    "Microsoft.Cache",
    "Redis Cache",
]

DISK_SERVICES = [
    "Microsoft.Compute/disks",
    "Managed Disks",
    "microsoft.compute/disks",
]


class StorageOptimizer:
    """
    Analyze storage workloads and generate cost optimization recommendations.

    Capabilities:
    - Storage tier optimization (Hot → Cool → Archive)
    - Orphaned disk detection
    - Unattached managed disk cleanup
    - Database right-sizing (DTU/vCore)
    - Lifecycle management policies
    - Snapshot cleanup recommendations
    """

    def __init__(self, db: Session):
        self.db = db

    def analyze(
        self,
        subscription_id: Optional[str] = None,
        lookback_days: int = 30,
    ) -> List[AIRecommendation]:
        """Run all storage optimization analyses."""
        recommendations: List[AIRecommendation] = []

        recommendations.extend(self._detect_orphaned_disks(subscription_id, lookback_days))
        recommendations.extend(self._suggest_storage_tier_changes(subscription_id, lookback_days))
        recommendations.extend(self._detect_oversized_databases(subscription_id, lookback_days))
        recommendations.extend(self._suggest_lifecycle_policies(subscription_id, lookback_days))

        if recommendations:
            self.db.add_all(recommendations)
            self.db.commit()
            logger.info("Generated %d storage optimisation recommendations", len(recommendations))

        return recommendations

    # ------------------------------------------------------------------
    # Orphaned disk detection
    # ------------------------------------------------------------------

    def _detect_orphaned_disks(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Detect managed disks with very low cost activity, suggesting
        they're unattached or orphaned.
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
                sqla_func.count(sqla_func.distinct(sqla_func.date(CostRecord.date))).label("active_days"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(DISK_SERVICES + STORAGE_SERVICES[:3]),
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
            name_lower = (row.resource_name or "").lower()
            total_cost = float(row.total_cost or 0)

            # Check for disk-like resources with cost but possibly unattached
            is_disk = any(d.lower() in (row.service_name or "").lower() for d in DISK_SERVICES)
            if is_disk and total_cost > 5:
                monthly_cost = total_cost * (30 / max(lookback_days, 1))
                rec = AIRecommendation(
                    recommendation_id=str(uuid.uuid4()),
                    tier=1,
                    source="rule_based",
                    category="storage",
                    title=f"Potential orphaned disk: {row.resource_name}",
                    description=(
                        f"Managed disk '{row.resource_name}' costs ${monthly_cost:.2f}/mo. "
                        f"If unattached to any VM, it's accruing cost unnecessarily."
                    ),
                    recommendation_text=(
                        f"Verify if disk '{row.resource_name}' is attached to a VM. "
                        f"If orphaned, snapshot it (if needed) and delete."
                    ),
                    subscription_id=row.subscription_id,
                    resource_id=row.resource_id,
                    service_name=row.service_name,
                    resource_type=row.resource_type,
                    current_cost=Decimal(str(round(monthly_cost, 2))),
                    potential_savings=Decimal(str(round(monthly_cost * 0.95, 2))),
                    savings_percentage=Decimal("95.00"),
                    priority="high" if monthly_cost > 50 else "medium",
                    confidence_score=Decimal("0.65"),
                    implementation_effort="minutes",
                    action_items=[
                        "Check disk attachment status in Azure Portal",
                        "Create a snapshot if data is needed",
                        "Delete the unattached disk",
                        "Tag remaining disks for better tracking",
                    ],
                    status="pending",
                )
                recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Storage tier optimization
    # ------------------------------------------------------------------

    def _suggest_storage_tier_changes(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Suggest moving storage accounts from Hot to Cool or Archive
        based on access patterns inferred from cost.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.avg(CostRecord.cost).label("avg_daily_cost"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(STORAGE_SERVICES[:3]),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
            )
            .having(sqla_func.sum(CostRecord.cost) > 20)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            monthly_cost = float(row.total_cost) * (30 / max(lookback_days, 1))
            # Cool tier saves ~50% on storage, Archive saves ~90%
            savings_cool = round(monthly_cost * 0.50, 2)

            rec = AIRecommendation(
                recommendation_id=str(uuid.uuid4()),
                tier=1,
                source="rule_based",
                category="storage",
                title=f"Storage tier optimisation: {row.resource_name}",
                description=(
                    f"Storage account '{row.resource_name}' costs ${monthly_cost:.2f}/mo on Hot tier. "
                    f"If data is infrequently accessed, Cool tier could save ~${savings_cool:.2f}/mo."
                ),
                recommendation_text=(
                    f"Review access patterns for '{row.resource_name}'. Move infrequently "
                    f"accessed blobs to Cool tier (30-day min) or Archive (180-day min)."
                ),
                subscription_id=row.subscription_id,
                resource_id=row.resource_id,
                service_name=row.service_name,
                current_cost=Decimal(str(round(monthly_cost, 2))),
                potential_savings=Decimal(str(savings_cool)),
                savings_percentage=Decimal("50.00"),
                priority="medium",
                confidence_score=Decimal("0.55"),
                implementation_effort="hours",
                action_items=[
                    "Review blob access patterns with Storage Analytics logs",
                    "Identify blobs not accessed in 30+ days",
                    "Set up lifecycle management policies for automatic tiering",
                    "Move cold data to Cool tier, archive data to Archive tier",
                ],
                status="pending",
            )
            recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Database right-sizing
    # ------------------------------------------------------------------

    def _detect_oversized_databases(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Detect databases with consistently low cost-per-DTU/vCore,
        suggesting over-provisioning.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        db_services = [s for s in STORAGE_SERVICES if "sql" in s.lower() or "db" in s.lower() or "cosmos" in s.lower() or "cache" in s.lower()]

        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
                sqla_func.avg(CostRecord.cost).label("avg_daily_cost"),
                sqla_func.max(CostRecord.cost).label("max_daily_cost"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(db_services),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                CostRecord.resource_type,
            )
            .having(sqla_func.sum(CostRecord.cost) > 100)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            avg_cost = float(row.avg_daily_cost or 0)
            max_cost = float(row.max_daily_cost or 0)
            monthly_cost = float(row.total_cost) * (30 / max(lookback_days, 1))

            # If average utilisation is < 40% of peak, likely oversized
            if max_cost > 0 and avg_cost < max_cost * 0.4:
                savings = round(monthly_cost * 0.30, 2)
                rec = AIRecommendation(
                    recommendation_id=str(uuid.uuid4()),
                    tier=1,
                    source="rule_based",
                    category="storage",
                    title=f"Database right-sizing: {row.resource_name}",
                    description=(
                        f"Database '{row.resource_name}' ({row.service_name}) has avg daily cost "
                        f"${avg_cost:.2f} vs peak ${max_cost:.2f}, suggesting over-provisioning. "
                        f"Monthly cost: ${monthly_cost:.2f}."
                    ),
                    recommendation_text=(
                        f"Consider scaling down '{row.resource_name}' to a smaller tier/SKU "
                        f"or using elastic pools for variable workloads."
                    ),
                    subscription_id=row.subscription_id,
                    resource_id=row.resource_id,
                    service_name=row.service_name,
                    resource_type=row.resource_type,
                    current_cost=Decimal(str(round(monthly_cost, 2))),
                    potential_savings=Decimal(str(savings)),
                    savings_percentage=Decimal("30.00"),
                    priority="high" if monthly_cost > 500 else "medium",
                    confidence_score=Decimal("0.65"),
                    implementation_effort="hours",
                    action_items=[
                        "Review DTU/vCore utilisation in Azure Portal metrics",
                        "Check query performance insights for workload patterns",
                        "Scale down to next smaller tier during low-traffic window",
                        "Consider elastic pools for multi-database workloads",
                    ],
                    status="pending",
                )
                recommendations.append(rec)

        return recommendations

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def _suggest_lifecycle_policies(
        self,
        subscription_id: Optional[str],
        lookback_days: int,
    ) -> List[AIRecommendation]:
        """
        Suggest blob lifecycle management policies for storage
        accounts without them.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        query = (
            self.db.query(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
                sqla_func.sum(CostRecord.cost).label("total_cost"),
            )
            .filter(
                CostRecord.date >= cutoff,
                CostRecord.service_name.in_(STORAGE_SERVICES[:3]),
            )
            .group_by(
                CostRecord.resource_id,
                CostRecord.resource_name,
                CostRecord.subscription_id,
                CostRecord.service_name,
            )
            .having(sqla_func.sum(CostRecord.cost) > 50)
        )
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)

        recommendations: List[AIRecommendation] = []
        for row in query.all():
            monthly_cost = float(row.total_cost) * (30 / max(lookback_days, 1))
            savings = round(monthly_cost * 0.20, 2)  # 20% savings from lifecycle mgmt

            rec = AIRecommendation(
                recommendation_id=str(uuid.uuid4()),
                tier=2,
                source="rule_based",
                category="storage",
                title=f"Add lifecycle policy: {row.resource_name}",
                description=(
                    f"Storage account '{row.resource_name}' (${monthly_cost:.2f}/mo) may not "
                    f"have lifecycle management policies. Automated tiering and deletion "
                    f"can reduce costs by ~20%."
                ),
                recommendation_text=(
                    f"Configure lifecycle management rules for '{row.resource_name}' to "
                    f"automatically move blobs to cooler tiers and delete expired data."
                ),
                subscription_id=row.subscription_id,
                resource_id=row.resource_id,
                service_name=row.service_name,
                current_cost=Decimal(str(round(monthly_cost, 2))),
                potential_savings=Decimal(str(savings)),
                savings_percentage=Decimal("20.00"),
                priority="low",
                confidence_score=Decimal("0.50"),
                implementation_effort="hours",
                automation_type="azure_cli",
                automation_script=self._generate_lifecycle_script(row.resource_name),
                action_items=[
                    "Review current lifecycle management configuration",
                    "Define rules: move to Cool after 30 days, Archive after 90 days",
                    "Set deletion policies for old snapshots and versions",
                    "Enable last access tracking for better tiering decisions",
                ],
                status="pending",
            )
            recommendations.append(rec)

        return recommendations

    @staticmethod
    def _generate_lifecycle_script(storage_name: str) -> str:
        """Generate a lifecycle management policy script."""
        return f"""# Lifecycle management policy for {storage_name}
# Apply via Azure CLI

az storage account management-policy create \\
    --account-name {storage_name} \\
    --resource-group <resource-group> \\
    --policy @- <<'POLICY'
{{
  "rules": [
    {{
      "name": "moveToCool",
      "enabled": true,
      "type": "Lifecycle",
      "definition": {{
        "filters": {{ "blobTypes": ["blockBlob"] }},
        "actions": {{
          "baseBlob": {{ "tierToCool": {{ "daysAfterModificationGreaterThan": 30 }} }},
          "snapshot": {{ "delete": {{ "daysAfterCreationGreaterThan": 90 }} }}
        }}
      }}
    }},
    {{
      "name": "moveToArchive",
      "enabled": true,
      "type": "Lifecycle",
      "definition": {{
        "filters": {{ "blobTypes": ["blockBlob"] }},
        "actions": {{
          "baseBlob": {{ "tierToArchive": {{ "daysAfterModificationGreaterThan": 90 }} }}
        }}
      }}
    }}
  ]
}}
POLICY
"""
