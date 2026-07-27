"""Bounded read-only resource inventory evidence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.models import ResourceMetadata


class ResourceInventoryArguments(BaseModel):
    subscription_id: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=50, ge=1, le=100)


class ResourceInventoryTool:
    name = "resource_inventory"
    description = "Return a bounded inventory summary from cached Azure resource metadata."
    read_only = True
    args_schema = ResourceInventoryArguments

    def __init__(self, db_session):
        self._db = db_session

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        args = ResourceInventoryArguments.model_validate(arguments)
        query = self._db.query(ResourceMetadata)
        if args.subscription_id:
            query = query.filter(ResourceMetadata.subscription_id == args.subscription_id)
        resources = query.order_by(ResourceMetadata.resource_type).limit(args.limit).all()
        by_type: dict[str, int] = {}
        by_region: dict[str, int] = {}
        for resource in resources:
            by_type[resource.resource_type] = by_type.get(resource.resource_type, 0) + 1
            region = resource.location or "unknown"
            by_region[region] = by_region.get(region, 0) + 1
        now = datetime.now(timezone.utc)
        return {
            "evidence_id": str(uuid.uuid4()),
            "source": "resource_metadata",
            "collected_at": now.isoformat(),
            "query": args.model_dump(),
            "data": {
                "returned_count": len(resources),
                "truncated": len(resources) == args.limit,
                "resource_types": by_type,
                "regions": by_region,
            },
        }