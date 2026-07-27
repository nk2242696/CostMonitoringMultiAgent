"""
Data Normalizer

Transforms raw Azure Cost Management API responses into clean,
normalised CostRecord rows ready for database insertion.
"""

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.models import CostRecord, CostAggregation, ResourceMetadata

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Normalise heterogeneous Azure Cost Management API payloads into
    canonical ``CostRecord`` instances.

    Handles:
    - Column name mapping (Azure returns inconsistent casing)
    - Currency normalisation
    - Tag flattening / cleaning
    - Region alias resolution
    - De-duplication via hashing
    - Aggregation row generation (daily/service/subscription)
    """

    # Azure API column aliases we need to handle
    _COLUMN_ALIASES: Dict[str, str] = {
        "UsageDate": "date",
        "usageDate": "date",
        "Date": "date",
        "PreTaxCost": "cost",
        "preTaxCost": "cost",
        "Cost": "cost",
        "CostInBillingCurrency": "cost",
        "SubscriptionId": "subscription_id",
        "subscriptionId": "subscription_id",
        "SubscriptionGuid": "subscription_id",
        "SubscriptionName": "subscription_name",
        "subscriptionName": "subscription_name",
        "ResourceGroup": "resource_group",
        "resourceGroup": "resource_group",
        "ResourceGroupName": "resource_group",
        "ResourceId": "resource_id",
        "resourceId": "resource_id",
        "ResourceName": "resource_name",
        "resourceName": "resource_name",
        "ServiceName": "service_name",
        "serviceName": "service_name",
        "ConsumedService": "service_name",
        "ResourceType": "resource_type",
        "resourceType": "resource_type",
        "MeterCategory": "meter_category",
        "meterCategory": "meter_category",
        "MeterSubCategory": "meter_subcategory",
        "meterSubCategory": "meter_subcategory",
        "MeterName": "meter_name",
        "meterName": "meter_name",
        "UnitOfMeasure": "unit_of_measure",
        "unitOfMeasure": "unit_of_measure",
        "Quantity": "quantity",
        "quantity": "quantity",
        "UnitPrice": "unit_price",
        "unitPrice": "unit_price",
        "ResourceLocation": "region",
        "resourceLocation": "region",
        "Location": "region",
        "Currency": "currency",
        "BillingCurrency": "currency",
        "Tags": "tags",
        "tags": "tags",
    }

    # Common Azure region aliases → canonical names
    _REGION_ALIASES: Dict[str, str] = {
        "eastus": "East US",
        "eastus2": "East US 2",
        "westus": "West US",
        "westus2": "West US 2",
        "westus3": "West US 3",
        "centralus": "Central US",
        "northcentralus": "North Central US",
        "southcentralus": "South Central US",
        "westcentralus": "West Central US",
        "westeurope": "West Europe",
        "northeurope": "North Europe",
        "uksouth": "UK South",
        "ukwest": "UK West",
        "eastasia": "East Asia",
        "southeastasia": "Southeast Asia",
        "japaneast": "Japan East",
        "japanwest": "Japan West",
        "australiaeast": "Australia East",
        "australiasoutheast": "Australia Southeast",
        "canadacentral": "Canada Central",
        "canadaeast": "Canada East",
        "brazilsouth": "Brazil South",
        "koreacentral": "Korea Central",
        "koreasouth": "Korea South",
        "centralindia": "Central India",
        "southindia": "South India",
        "westindia": "West India",
    }

    def __init__(self, default_currency: str = "USD"):
        self.default_currency = default_currency
        self._seen_hashes: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize_cost_rows(
        self, raw_rows: List[Dict[str, Any]], subscription_id: Optional[str] = None
    ) -> List[CostRecord]:
        """
        Convert a list of raw Azure API dictionaries into CostRecord objects.

        Args:
            raw_rows: List of cost data dictionaries from Azure API.
            subscription_id: Fallback subscription ID if not present in rows.

        Returns:
            List of normalised CostRecord instances (de-duplicated).
        """
        records: List[CostRecord] = []
        skipped = 0

        for raw in raw_rows:
            normalised = self._map_columns(raw)
            if subscription_id and not normalised.get("subscription_id"):
                normalised["subscription_id"] = subscription_id

            # Skip rows with zero or negative cost
            cost = self._to_decimal(normalised.get("cost", 0))
            if cost <= 0:
                skipped += 1
                continue

            row_hash = self._row_hash(normalised)
            if row_hash in self._seen_hashes:
                skipped += 1
                continue
            self._seen_hashes.add(row_hash)

            record = self._build_cost_record(normalised, cost)
            records.append(record)

        logger.info(
            "Normalised %d cost records (%d skipped/duplicates)",
            len(records),
            skipped,
        )
        return records

    def build_aggregations(
        self,
        records: List[CostRecord],
        aggregation_type: str = "daily",
    ) -> List[CostAggregation]:
        """
        Generate pre-computed aggregation rows from normalised records.

        Groups by (date, subscription_id, dimension) and produces one
        ``CostAggregation`` per group.

        Args:
            records: Normalised CostRecord instances.
            aggregation_type: 'daily', 'weekly', or 'monthly'.

        Returns:
            List of CostAggregation instances.
        """
        buckets: Dict[str, Dict[str, Any]] = {}

        for rec in records:
            date_key = rec.date.strftime("%Y-%m-%d") if rec.date else "unknown"

            for dimension, value in [
                ("subscription", rec.subscription_id),
                ("service", rec.service_name),
                ("resource_group", rec.resource_group),
                ("resource_type", rec.resource_type),
            ]:
                key = f"{date_key}|{rec.subscription_id}|{dimension}|{value}"
                if key not in buckets:
                    buckets[key] = {
                        "date": rec.date,
                        "subscription_id": rec.subscription_id,
                        "dimension": dimension,
                        "dimension_value": value,
                        "total_cost": Decimal("0"),
                        "resource_count": 0,
                    }
                buckets[key]["total_cost"] += rec.cost or Decimal("0")
                buckets[key]["resource_count"] += 1

        aggregations = [
            CostAggregation(
                date=b["date"],
                aggregation_type=aggregation_type,
                dimension=b["dimension"],
                dimension_value=b["dimension_value"],
                subscription_id=b["subscription_id"],
                total_cost=b["total_cost"],
                currency=self.default_currency,
                resource_count=b["resource_count"],
            )
            for b in buckets.values()
        ]

        logger.info(
            "Built %d %s aggregation rows from %d records",
            len(aggregations),
            aggregation_type,
            len(records),
        )
        return aggregations

    def normalize_resource_metadata(
        self, raw_resources: List[Dict[str, Any]]
    ) -> List[ResourceMetadata]:
        """
        Convert raw Azure Resource Graph results into ResourceMetadata rows.
        """
        resources: List[ResourceMetadata] = []
        for raw in raw_resources:
            res = ResourceMetadata(
                resource_id=raw.get("id", raw.get("resourceId", "")),
                subscription_id=raw.get("subscriptionId", ""),
                resource_group=raw.get("resourceGroup", ""),
                resource_name=raw.get("name", ""),
                resource_type=raw.get("type", ""),
                location=self._normalize_region(raw.get("location", "")),
                sku=raw.get("sku", {}).get("name") if isinstance(raw.get("sku"), dict) else raw.get("sku"),
                tags=self._clean_tags(raw.get("tags", {})),
                properties=raw.get("properties", {}),
                status=raw.get("properties", {}).get("provisioningState", "Unknown"),
                last_seen=datetime.now(timezone.utc),
            )
            resources.append(res)

        logger.info("Normalised %d resource metadata entries", len(resources))
        return resources

    def reset_dedup_cache(self) -> None:
        """Clear the in-memory de-duplication hash set."""
        self._seen_hashes.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _map_columns(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Map Azure API column names to canonical names."""
        normalised: Dict[str, Any] = {}
        for key, value in raw.items():
            canonical = self._COLUMN_ALIASES.get(key, key.lower())
            normalised[canonical] = value
        return normalised

    def _build_cost_record(self, data: Dict[str, Any], cost: Decimal) -> CostRecord:
        """Build a CostRecord from a normalised data dict."""
        return CostRecord(
            date=self._parse_date(data.get("date")),
            subscription_id=str(data.get("subscription_id", "")),
            subscription_name=str(data.get("subscription_name", "")),
            resource_group=str(data.get("resource_group", "unknown")),
            resource_id=str(data.get("resource_id", "")),
            resource_name=self._extract_resource_name(data),
            service_name=str(data.get("service_name", "Unknown")),
            resource_type=str(data.get("resource_type", "Unknown")),
            region=self._normalize_region(str(data.get("region", "Unknown"))),
            cost=cost,
            currency=str(data.get("currency", self.default_currency)),
            tags=self._clean_tags(data.get("tags")),
            meter_category=data.get("meter_category"),
            meter_subcategory=data.get("meter_subcategory"),
            meter_name=data.get("meter_name"),
            unit_of_measure=data.get("unit_of_measure"),
            quantity=self._to_decimal(data.get("quantity")),
            unit_price=self._to_decimal(data.get("unit_price")),
        )

    def _extract_resource_name(self, data: Dict[str, Any]) -> str:
        """Extract resource name from data or parse from resource_id."""
        name = data.get("resource_name")
        if name:
            return str(name)
        resource_id = data.get("resource_id", "")
        if "/" in resource_id:
            return resource_id.split("/")[-1]
        return "unknown"

    def _parse_date(self, value: Any) -> datetime:
        """Parse various date formats into a datetime object."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%Y%m%d",
            ):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        if isinstance(value, (int, float)):
            # Excel-style serial date or timestamp
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (OSError, ValueError):
                pass
        logger.warning("Could not parse date value '%s', using now()", value)
        return datetime.now(timezone.utc)

    def _normalize_region(self, region: str) -> str:
        """Resolve Azure region aliases to display names."""
        if not region:
            return "Unknown"
        lower = region.lower().replace(" ", "")
        return self._REGION_ALIASES.get(lower, region)

    def _clean_tags(self, tags: Any) -> dict:
        """Ensure tags is a clean dictionary."""
        if tags is None:
            return {}
        if isinstance(tags, str):
            try:
                import json
                return json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                return {"raw": tags}
        if isinstance(tags, dict):
            # Strip empty values
            return {k: v for k, v in tags.items() if v is not None and v != ""}
        return {}

    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        """Safely convert a value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    @staticmethod
    def _row_hash(data: Dict[str, Any]) -> str:
        """Generate a dedup hash for a normalised row."""
        parts = [
            str(data.get("date", "")),
            str(data.get("subscription_id", "")),
            str(data.get("resource_id", "")),
            str(data.get("service_name", "")),
            str(data.get("meter_name", "")),
            str(data.get("cost", "")),
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()
