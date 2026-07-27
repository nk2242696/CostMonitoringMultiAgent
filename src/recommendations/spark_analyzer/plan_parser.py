"""
Tier 3 – Spark Execution Plan Parser

Parses Spark physical and logical execution plans to extract:
  - Join strategies (SortMergeJoin, BroadcastHashJoin, ShuffledHashJoin)
  - Exchange (shuffle) nodes with data size estimates
  - Stage boundaries
  - Sort operations
  - Filter pushdowns
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanNode:
    """A single node in a Spark execution plan tree."""
    node_type: str          # e.g. "SortMergeJoin", "Exchange", "Project"
    node_id: int = 0
    children: List["PlanNode"] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    data_size_bytes: Optional[int] = None
    rows_estimate: Optional[int] = None
    raw_text: str = ""


@dataclass
class JoinInfo:
    """Extracted join metadata."""
    join_type: str          # SortMergeJoin, BroadcastHashJoin, ShuffledHashJoin
    join_keys: List[str]
    left_size_bytes: Optional[int] = None
    right_size_bytes: Optional[int] = None
    left_rows: Optional[int] = None
    right_rows: Optional[int] = None
    raw_text: str = ""


@dataclass
class ShuffleInfo:
    """Extracted shuffle (Exchange) metadata."""
    exchange_type: str      # hashpartitioning, rangepartitioning, SinglePartition
    partition_keys: List[str] = field(default_factory=list)
    num_partitions: Optional[int] = None
    data_size_bytes: Optional[int] = None
    raw_text: str = ""


@dataclass
class ParsedPlan:
    """Complete parsed execution plan."""
    joins: List[JoinInfo] = field(default_factory=list)
    shuffles: List[ShuffleInfo] = field(default_factory=list)
    sorts: int = 0
    filters: int = 0
    scans: int = 0
    projects: int = 0
    total_nodes: int = 0
    raw_plan: str = ""


class PlanParser:
    """
    Parses Spark physical execution plans (the text representation)
    and extracts structured information for the pattern detector.
    """

    # Regex patterns for plan parsing
    _JOIN_PATTERN = re.compile(
        r"(SortMergeJoin|BroadcastHashJoin|ShuffledHashJoin|CartesianProduct|BroadcastNestedLoopJoin)"
        r".*?\[(.*?)\]",
        re.IGNORECASE | re.DOTALL,
    )
    _EXCHANGE_PATTERN = re.compile(
        r"Exchange\s+(hashpartitioning|rangepartitioning|SinglePartition|RoundRobinPartitioning)"
        r"(?:\((.*?)\))?"
        r"(?:,\s*(\d+))?"
        r"(?:.*?size[=:]?\s*(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB))?",
        re.IGNORECASE,
    )
    _SIZE_PATTERN = re.compile(
        r"(?:size|sizeInBytes)[=:]\s*(\d+(?:\.\d+)?)\s*(B|KiB|MiB|GiB|TiB|KB|MB|GB|TB)",
        re.IGNORECASE,
    )
    _ROWS_PATTERN = re.compile(
        r"(?:rowCount|numRows|rows)[=:]\s*(\d+)",
        re.IGNORECASE,
    )

    def parse(self, plan_text: str) -> ParsedPlan:
        """Parse a physical plan string into structured components."""
        if not plan_text:
            return ParsedPlan()

        result = ParsedPlan(raw_plan=plan_text)

        # Count node types
        lines = plan_text.split("\n")
        for line in lines:
            stripped = line.strip().lstrip("+- :")
            result.total_nodes += 1
            if "Sort " in stripped or "Sort(" in stripped:
                result.sorts += 1
            if "Filter " in stripped or "Filter(" in stripped:
                result.filters += 1
            if "Scan " in stripped or "FileScan" in stripped:
                result.scans += 1
            if "Project " in stripped or "Project(" in stripped:
                result.projects += 1

        # Extract joins
        for m in self._JOIN_PATTERN.finditer(plan_text):
            join_type = m.group(1)
            keys_text = m.group(2) if m.group(2) else ""
            keys = [k.strip() for k in keys_text.split(",") if k.strip()]

            # Try to find sizes near the join
            context_start = max(0, m.start() - 200)
            context_end = min(len(plan_text), m.end() + 500)
            context = plan_text[context_start:context_end]

            sizes = self._extract_sizes(context)
            rows = self._extract_rows(context)

            ji = JoinInfo(
                join_type=join_type,
                join_keys=keys,
                left_size_bytes=sizes[0] if len(sizes) >= 1 else None,
                right_size_bytes=sizes[1] if len(sizes) >= 2 else None,
                left_rows=rows[0] if len(rows) >= 1 else None,
                right_rows=rows[1] if len(rows) >= 2 else None,
                raw_text=m.group(0),
            )
            result.joins.append(ji)

        # Extract shuffles
        for m in self._EXCHANGE_PATTERN.finditer(plan_text):
            exchange_type = m.group(1)
            keys_text = m.group(2) or ""
            num_partitions = int(m.group(3)) if m.group(3) else None
            size_val = float(m.group(4)) if m.group(4) else None
            size_unit = m.group(5) if m.group(5) else None
            data_size = self._to_bytes(size_val, size_unit) if size_val and size_unit else None

            si = ShuffleInfo(
                exchange_type=exchange_type,
                partition_keys=[k.strip() for k in keys_text.split(",") if k.strip()],
                num_partitions=num_partitions,
                data_size_bytes=data_size,
                raw_text=m.group(0),
            )
            result.shuffles.append(si)

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_sizes(self, text: str) -> List[int]:
        sizes = []
        for m in self._SIZE_PATTERN.finditer(text):
            val = float(m.group(1))
            unit = m.group(2)
            sizes.append(self._to_bytes(val, unit))
        return sizes

    def _extract_rows(self, text: str) -> List[int]:
        return [int(m.group(1)) for m in self._ROWS_PATTERN.finditer(text)]

    @staticmethod
    def _to_bytes(value: float, unit: str) -> int:
        multipliers = {
            "b": 1,
            "kb": 1024, "kib": 1024,
            "mb": 1024**2, "mib": 1024**2,
            "gb": 1024**3, "gib": 1024**3,
            "tb": 1024**4, "tib": 1024**4,
        }
        return int(value * multipliers.get(unit.lower(), 1))
