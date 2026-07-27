"""
Azure Cost Data Collector

Consolidated collector that fetches cost data from Azure Cost Management API
at different grains (subscription, service, resource_type, resource) and
stores it into the unified cost_records table.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from azure.core.exceptions import AzureError
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.resource import SubscriptionClient
from sqlalchemy.orm import Session

from src.models import CostRecord, CostAggregation

logger = logging.getLogger(__name__)


class CostCollector:
    """
    Collects cost data from Azure Cost Management API and persists
    it to the database.

    Supports multiple grains:
      - subscription: total cost per subscription per day
      - service:      cost broken down by ServiceName
      - resource_type: cost broken down by ResourceType
      - resource:     cost broken down by individual ResourceId
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        import os

        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET")
        self.credential = self._get_credential()
        self._cost_client = None  # Lazy-init, reuse across calls

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_credential(self):
        if self.tenant_id and self.client_id and self.client_secret:
            logger.info("Using Service Principal authentication")
            return ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
        logger.info("Using DefaultAzureCredential (CLI / Managed Identity)")
        return DefaultAzureCredential()

    # ------------------------------------------------------------------
    # Subscription discovery
    # ------------------------------------------------------------------

    def discover_subscriptions(self) -> List[Dict]:
        """Return all accessible Azure subscriptions."""
        client = SubscriptionClient(self.credential)
        subs = []
        for s in client.subscriptions.list():
            subs.append(
                {
                    "subscription_id": s.subscription_id,
                    "display_name": s.display_name,
                    "state": s.state,
                    "tenant_id": s.tenant_id,
                }
            )
        logger.info("Discovered %d subscriptions", len(subs))
        return subs

    def fetch_resource_tags(self, subscription_id: str) -> Dict[str, Dict]:
        """
        Fetch tags for all resources in a subscription via Azure Resource Graph.
        Returns: {resource_id_lower: {tag_key: tag_value, ...}}
        """
        try:
            from azure.mgmt.resourcegraph import ResourceGraphClient
            from azure.mgmt.resourcegraph.models import QueryRequest

            client = ResourceGraphClient(self.credential)
            query = QueryRequest(
                subscriptions=[subscription_id],
                query="Resources | project id, tags, type, location | where isnotnull(tags)",
                options={"resultFormat": "objectArray"},
            )
            result = client.resources(query)
            tag_map = {}
            for row in (result.data or []):
                rid = (row.get("id") or "").lower()
                tags = row.get("tags") or {}
                if rid and tags:
                    tag_map[rid] = tags
            logger.info("Fetched tags for %d resources in %s", len(tag_map), subscription_id)
            return tag_map
        except Exception as exc:
            logger.warning("Resource Graph tag fetch failed for %s: %s", subscription_id, str(exc)[:80])
            return {}

    def enrich_records_with_tags(
        self, records: List[Dict], tag_map: Dict[str, Dict]
    ) -> List[Dict]:
        """Merge tags from Resource Graph into cost records."""
        enriched = 0
        for rec in records:
            rid = (rec.get("resource_id") or "").lower()
            if rid in tag_map:
                rec["tags"] = tag_map[rid]
                enriched += 1
        if enriched:
            logger.info("Enriched %d/%d records with tags", enriched, len(records))
        return records

    # ------------------------------------------------------------------
    # Cost queries
    # ------------------------------------------------------------------

    def _build_query(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str,
        grouping_dimensions: List[str],
    ) -> dict:
        return {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {
                "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                "to": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            },
            "dataset": {
                "granularity": granularity,
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"},
                    "totalQuantity": {"name": "UsageQuantity", "function": "Sum"},
                },
                "grouping": [
                    {"type": "Dimension", "name": dim}
                    for dim in grouping_dimensions
                ],
            },
        }

    def collect_costs(
        self,
        subscription_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "Daily",
    ) -> List[Dict]:
        """
        Collect detailed cost data grouped by ServiceName, ResourceGroupName,
        ResourceType, and ResourceId.
        """
        start_date = start_date or (datetime.utcnow() - timedelta(days=30))
        end_date = end_date or datetime.utcnow()
        scope = f"/subscriptions/{subscription_id}"

        if self._cost_client is None:
            self._cost_client = CostManagementClient(self.credential)

        query = self._build_query(
            start_date,
            end_date,
            granularity,
            [
                "ServiceName",
                "ResourceGroupName",
                "ResourceType",
                "ResourceId",
            ],
        )

        logger.info(
            "Collecting costs for %s (%s – %s)",
            subscription_id,
            start_date.date(),
            end_date.date(),
        )

        try:
            result = self._cost_client.query.usage(scope, query)
        except AzureError as exc:
            logger.error("Azure query failed for %s: %s", subscription_id, str(exc)[:120])
            raise

        records: List[Dict] = []
        if not result.rows:
            logger.warning("No cost rows returned for %s", subscription_id)
            return records

        # Column order depends on the query; parse from result.columns
        col_names = [c.name for c in result.columns]

        for row in result.rows:
            row_dict = dict(zip(col_names, row))
            cost_val = row_dict.get("Cost", row_dict.get("totalCost", 0))
            records.append(
                {
                    "date": row_dict.get("UsageDate", row_dict.get("BillingPeriod")),
                    "cost": float(cost_val) if cost_val else 0.0,
                    "quantity": float(row_dict.get("UsageQuantity", 0)),
                    "service_name": row_dict.get("ServiceName", "Unknown"),
                    "resource_group": row_dict.get("ResourceGroupName", "Unknown"),
                    "resource_type": row_dict.get("ResourceType", "Unknown"),
                    "resource_id": row_dict.get("ResourceId", ""),
                    "currency": "USD",
                    "subscription_id": subscription_id,
                }
            )

        logger.info("Collected %d cost records for %s", len(records), subscription_id)
        return records

    def collect_by_service(
        self,
        subscription_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict]:
        """Collect costs aggregated by service (lighter query)."""
        start_date = start_date or datetime.utcnow().replace(day=1)
        end_date = end_date or datetime.utcnow()
        scope = f"/subscriptions/{subscription_id}"
        if self._cost_client is None:
            self._cost_client = CostManagementClient(self.credential)

        query = self._build_query(start_date, end_date, "None", ["ServiceName"])

        try:
            result = self._cost_client.query.usage(scope, query)
        except AzureError as exc:
            logger.error("Service cost query failed: %s", exc)
            raise

        costs = []
        if result.rows:
            for row in result.rows:
                costs.append(
                    {
                        "service_name": row[1] if len(row) > 1 else "Unknown",
                        "total_cost": float(row[0]) if row[0] else 0.0,
                        "currency": "USD",
                        "subscription_id": subscription_id,
                    }
                )
            costs.sort(key=lambda x: x["total_cost"], reverse=True)
        return costs

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_azure_date(raw_date) -> datetime:
        """Parse date from Azure Cost Management API.

        Azure returns dates in various formats:
        - Integer like 20260119
        - String like '20260119' or '2026-01-19' or '2026-01-19T00:00:00'
        - datetime object
        """
        if isinstance(raw_date, datetime):
            return raw_date
        if isinstance(raw_date, (int, float)):
            s = str(int(raw_date))
            return datetime.strptime(s, "%Y%m%d")
        if isinstance(raw_date, str):
            for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(raw_date, fmt)
                except ValueError:
                    continue
        logger.warning("Could not parse date '%s', using utcnow()", raw_date)
        return datetime.utcnow()

    def persist_cost_records(
        self, db: Session, records: List[Dict], subscription_name: str = ""
    ) -> int:
        """Upsert cost records into the database. Returns count inserted."""
        count = 0
        for rec in records:
            resource_name = (rec.get("resource_id") or "").rsplit("/", 1)[-1] or "Unknown"
            cost_record = CostRecord(
                date=self._parse_azure_date(rec["date"]),
                subscription_id=rec["subscription_id"],
                subscription_name=subscription_name,
                resource_group=rec.get("resource_group", "Unknown"),
                resource_id=rec.get("resource_id", ""),
                resource_name=resource_name,
                service_name=rec.get("service_name", "Unknown"),
                resource_type=rec.get("resource_type", "Unknown"),
                region=rec.get("region", "Unknown"),
                cost=rec["cost"],
                currency=rec.get("currency", "USD"),
                quantity=rec.get("quantity"),
                tags=rec.get("tags", {}),
            )
            db.add(cost_record)
            count += 1

        db.commit()
        logger.info("Persisted %d cost records", count)
        return count

    def build_aggregations(
        self,
        db: Session,
        subscription_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Build daily aggregations at subscription, service, and resource_type
        grain from raw cost_records.
        """
        from sqlalchemy import func as sqla_func, cast, Date

        start_date = start_date or (datetime.utcnow() - timedelta(days=30))
        end_date = end_date or datetime.utcnow()
        count = 0

        for dimension_col, dimension_name in [
            (CostRecord.subscription_id, "subscription"),
            (CostRecord.service_name, "service"),
            (CostRecord.resource_type, "resource_type"),
        ]:
            rows = (
                db.query(
                    cast(CostRecord.date, Date).label("day"),
                    dimension_col.label("dim_value"),
                    sqla_func.sum(CostRecord.cost).label("total"),
                    sqla_func.count(CostRecord.id).label("cnt"),
                )
                .filter(
                    CostRecord.subscription_id == subscription_id,
                    CostRecord.date >= start_date,
                    CostRecord.date <= end_date,
                )
                .group_by("day", "dim_value")
                .all()
            )

            for row in rows:
                agg = CostAggregation(
                    date=row.day,
                    aggregation_type="daily",
                    dimension=dimension_name,
                    dimension_value=row.dim_value,
                    subscription_id=subscription_id,
                    total_cost=row.total,
                    resource_count=row.cnt,
                )
                db.merge(agg)
                count += 1

        db.commit()
        logger.info("Built %d aggregation rows for %s", count, subscription_id)
        return count


def run_collection(
    subscription_ids: Optional[List[str]] = None,
    days: int = 30,
):
    """
    CLI / scheduled entry-point: discover subscriptions (or use provided list),
    collect costs, persist, and build aggregations.
    """
    from src.common.database import get_database

    collector = CostCollector()

    if not subscription_ids:
        subs = collector.discover_subscriptions()
        subscription_ids = [s["subscription_id"] for s in subs]

    db = get_database()
    start_date = datetime.utcnow() - timedelta(days=days)
    end_date = datetime.utcnow()

    import time as _time

    with db.get_session() as session:
        collected = 0
        skipped = 0
        for i, sub_id in enumerate(subscription_ids):
            try:
                records = collector.collect_costs(sub_id, start_date, end_date)
                if records:
                    # Enrich with tags from Resource Graph
                    try:
                        tag_map = collector.fetch_resource_tags(sub_id)
                        if tag_map:
                            records = collector.enrich_records_with_tags(records, tag_map)
                    except Exception:
                        pass  # Tags are best-effort, don't block collection

                    collector.persist_cost_records(session, records)
                    collector.build_aggregations(session, sub_id, start_date, end_date)
                    collected += 1
                    logger.info("[%d/%d] ✅ %s — %d records", i+1, len(subscription_ids), sub_id[:12], len(records))
                else:
                    skipped += 1
            except Exception as exc:
                err_msg = str(exc)[:80]
                if "RBACAccessDenied" in err_msg:
                    skipped += 1  # Silently skip — no permission
                else:
                    logger.warning("[%d/%d] ❌ %s — %s", i+1, len(subscription_ids), sub_id[:12], err_msg)
                try:
                    session.rollback()
                except Exception:
                    pass
                continue
            finally:
                # Throttle to avoid Azure 429 rate limits (5s for large sub counts)
                if i < len(subscription_ids) - 1:
                    _time.sleep(5)

    logger.info("Collection complete: %d succeeded, %d skipped, out of %d total", collected, skipped, len(subscription_ids))
