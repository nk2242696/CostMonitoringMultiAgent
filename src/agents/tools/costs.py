"""Read-only cost evidence adapter."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.monitoring.storage.repositories import CostRecordRepository


class CostSummaryArguments(BaseModel):
    subscription_id: str | None = Field(default=None, max_length=255)
    lookback_days: int = Field(default=30, ge=1, le=365)
    top_n: int = Field(default=10, ge=1, le=20)


class CostSummaryTool:
    name = "cost_summary"
    description = "Return total cost and top services from canonical persisted cost records."
    read_only = True
    args_schema = CostSummaryArguments

    def __init__(self, repository: CostRecordRepository):
        self._repository = repository

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        args = CostSummaryArguments.model_validate(arguments)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=args.lookback_days)
        total = self._repository.get_total_cost(start, end, args.subscription_id)
        services = self._repository.get_cost_by_service(
            start, end, args.subscription_id, args.top_n
        )
        return {
            "evidence_id": str(uuid.uuid4()),
            "source": "cost_records",
            "collected_at": end.isoformat(),
            "query": args.model_dump(),
            "data": {"total_cost": total, "currency": "USD", "top_services": services},
        }