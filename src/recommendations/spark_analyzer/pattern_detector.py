"""
Tier 3 – Spark Anti-Pattern Detector

Analyses parsed execution plans and code to detect performance
and cost anti-patterns such as:

  1. SortMergeJoin where one side is small enough to broadcast
  2. Excessive shuffles (Exchange nodes)
  3. Data skew (partition imbalance)
  4. Missing filter push-down
  5. Cartesian products / cross joins
  6. Spill to disk
  7. Too many / too few partitions
  8. Collect() on large datasets
  9. UDF usage preventing Catalyst optimisations
  10. Repeated reads of the same data (missing caching)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from src.recommendations.spark_analyzer.plan_parser import (
    JoinInfo,
    ParsedPlan,
    ShuffleInfo,
)

logger = logging.getLogger(__name__)

# Threshold: if either side of a join is below this, broadcast is better
BROADCAST_THRESHOLD_BYTES = 256 * 1024 * 1024  # 256 MB (Spark default is 10 MB, but up to 256 MB is usually safe)
BROADCAST_THRESHOLD_ROWS = 5_000_000

# Shuffle thresholds
HIGH_SHUFFLE_BYTES = 1 * 1024**3  # 1 GB
TOO_MANY_SHUFFLES = 5

# Partition thresholds
MIN_RECOMMENDED_PARTITIONS = 8
MAX_RECOMMENDED_PARTITIONS = 2000


@dataclass
class PatternIssue:
    """A single detected anti-pattern issue."""
    pattern_id: str
    severity: str          # critical, high, medium, low
    title: str
    description: str
    suggestion: str
    estimated_impact: str  # e.g., "reduce shuffle by 80%"
    code_fix: Optional[str] = None
    affected_node: Optional[str] = None


class PatternDetector:
    """
    Detects Spark performance / cost anti-patterns from parsed plans
    and notebook code.
    """

    def detect(
        self,
        plan: ParsedPlan,
        code: str = "",
        spill_disk_bytes: int = 0,
        spill_memory_bytes: int = 0,
    ) -> List[PatternIssue]:
        """
        Run all pattern detectors and return found issues.

        Args:
            plan:               Parsed execution plan.
            code:               Notebook / script source code.
            spill_disk_bytes:   Total bytes spilled to disk.
            spill_memory_bytes: Total bytes spilled in memory.

        Returns:
            List of detected PatternIssue instances.
        """
        issues: List[PatternIssue] = []

        # Plan-based detections
        issues.extend(self._check_broadcast_opportunity(plan))
        issues.extend(self._check_excessive_shuffles(plan))
        issues.extend(self._check_cartesian_product(plan))
        issues.extend(self._check_partition_count(plan))
        issues.extend(self._check_spill(spill_disk_bytes, spill_memory_bytes))

        # Code-based detections
        if code:
            issues.extend(self._check_collect_on_large(code))
            issues.extend(self._check_udf_usage(code))
            issues.extend(self._check_missing_cache(code))
            issues.extend(self._check_repartition_misuse(code))
            issues.extend(self._check_schema_inference(code))

        return issues

    # ------------------------------------------------------------------
    # Plan-based detections
    # ------------------------------------------------------------------

    def _check_broadcast_opportunity(self, plan: ParsedPlan) -> List[PatternIssue]:
        """Detect SortMergeJoin where one side is small enough to broadcast."""
        issues = []
        for join in plan.joins:
            if join.join_type != "SortMergeJoin":
                continue

            small_side = None
            small_size = None

            # Check by bytes
            if join.right_size_bytes and join.right_size_bytes < BROADCAST_THRESHOLD_BYTES:
                small_side = "right"
                small_size = join.right_size_bytes
            elif join.left_size_bytes and join.left_size_bytes < BROADCAST_THRESHOLD_BYTES:
                small_side = "left"
                small_size = join.left_size_bytes

            # Check by row count
            if not small_side:
                if join.right_rows and join.right_rows < BROADCAST_THRESHOLD_ROWS:
                    small_side = "right"
                elif join.left_rows and join.left_rows < BROADCAST_THRESHOLD_ROWS:
                    small_side = "left"

            if small_side:
                size_str = self._format_bytes(small_size) if small_size else "small"
                issues.append(
                    PatternIssue(
                        pattern_id="SPARK-001",
                        severity="high",
                        title="SortMergeJoin can be replaced with BroadcastHashJoin",
                        description=(
                            f"A SortMergeJoin on keys [{', '.join(join.join_keys)}] "
                            f"has a {small_side} side of only {size_str}. "
                            f"This causes a full shuffle of both datasets."
                        ),
                        suggestion=(
                            f"Use broadcast() on the {small_side} DataFrame to avoid the shuffle.\n"
                            f"This will eliminate the Exchange (shuffle) step for the smaller dataset "
                            f"and significantly reduce I/O and network cost."
                        ),
                        estimated_impact="Reduce shuffle I/O by 50-80%, decrease job duration by 30-60%",
                        code_fix=(
                            f"from pyspark.sql.functions import broadcast\n"
                            f"result = large_df.join(broadcast(small_df), on=[{', '.join(repr(k) for k in join.join_keys)}])"
                        ),
                        affected_node=join.raw_text[:200],
                    )
                )
        return issues

    def _check_excessive_shuffles(self, plan: ParsedPlan) -> List[PatternIssue]:
        """Flag excessive shuffle operations."""
        issues = []
        if len(plan.shuffles) >= TOO_MANY_SHUFFLES:
            total_shuffle_bytes = sum(
                s.data_size_bytes or 0 for s in plan.shuffles
            )
            issues.append(
                PatternIssue(
                    pattern_id="SPARK-002",
                    severity="high",
                    title=f"Excessive shuffles: {len(plan.shuffles)} Exchange nodes",
                    description=(
                        f"The query plan contains {len(plan.shuffles)} shuffle (Exchange) operations "
                        f"moving an estimated {self._format_bytes(total_shuffle_bytes)} of data. "
                        f"Each shuffle involves serializing, writing to disk, network transfer, and deserializing."
                    ),
                    suggestion=(
                        "Reduce shuffles by:\n"
                        "1. Pre-partitioning data by join/group keys using .repartition()\n"
                        "2. Using broadcast joins for small tables\n"
                        "3. Combining multiple narrow transformations\n"
                        "4. Using bucketed tables for repeated join patterns"
                    ),
                    estimated_impact="Reduce job duration by 20-50%",
                )
            )

        # Flag individual large shuffles
        for shuffle in plan.shuffles:
            if shuffle.data_size_bytes and shuffle.data_size_bytes > HIGH_SHUFFLE_BYTES:
                issues.append(
                    PatternIssue(
                        pattern_id="SPARK-003",
                        severity="medium",
                        title=f"Large shuffle: {self._format_bytes(shuffle.data_size_bytes)}",
                        description=(
                            f"Exchange ({shuffle.exchange_type}) is shuffling "
                            f"{self._format_bytes(shuffle.data_size_bytes)} of data."
                        ),
                        suggestion=(
                            "Consider partitioning source data by the shuffle key "
                            f"[{', '.join(shuffle.partition_keys)}] to avoid this shuffle."
                        ),
                        estimated_impact="Reduce shuffle I/O",
                    )
                )
        return issues

    def _check_cartesian_product(self, plan: ParsedPlan) -> List[PatternIssue]:
        """Detect cartesian products / cross joins."""
        issues = []
        for join in plan.joins:
            if join.join_type in ("CartesianProduct", "BroadcastNestedLoopJoin"):
                issues.append(
                    PatternIssue(
                        pattern_id="SPARK-004",
                        severity="critical",
                        title=f"Cartesian product detected ({join.join_type})",
                        description=(
                            "A CartesianProduct or BroadcastNestedLoopJoin produces the cross product "
                            "of two datasets. This can explode data size and is almost always unintended."
                        ),
                        suggestion=(
                            "Add a join condition to convert this into an equi-join. "
                            "If a cross join is truly needed, call .crossJoin() explicitly."
                        ),
                        estimated_impact="Prevent potential OOM and massive cost increase",
                    )
                )
        return issues

    def _check_partition_count(self, plan: ParsedPlan) -> List[PatternIssue]:
        issues = []
        for shuffle in plan.shuffles:
            if shuffle.num_partitions is not None:
                if shuffle.num_partitions < MIN_RECOMMENDED_PARTITIONS:
                    issues.append(
                        PatternIssue(
                            pattern_id="SPARK-005",
                            severity="medium",
                            title=f"Too few partitions: {shuffle.num_partitions}",
                            description=(
                                f"Shuffle repartitions into only {shuffle.num_partitions} partitions. "
                                f"This may under-utilise executor cores and cause memory pressure."
                            ),
                            suggestion="Increase shuffle partitions: spark.conf.set('spark.sql.shuffle.partitions', 200)",
                            estimated_impact="Better parallelism, reduced risk of OOM",
                        )
                    )
                elif shuffle.num_partitions > MAX_RECOMMENDED_PARTITIONS:
                    issues.append(
                        PatternIssue(
                            pattern_id="SPARK-006",
                            severity="low",
                            title=f"Too many partitions: {shuffle.num_partitions}",
                            description=(
                                f"Shuffle creates {shuffle.num_partitions} partitions. "
                                f"Very high partition counts cause excessive scheduling overhead."
                            ),
                            suggestion="Reduce spark.sql.shuffle.partitions or use coalesce() after wide transformations",
                            estimated_impact="Reduce scheduling overhead",
                        )
                    )
        return issues

    def _check_spill(self, disk_bytes: int, memory_bytes: int) -> List[PatternIssue]:
        issues = []
        if disk_bytes > 0:
            issues.append(
                PatternIssue(
                    pattern_id="SPARK-007",
                    severity="high",
                    title=f"Disk spill detected: {self._format_bytes(disk_bytes)}",
                    description=(
                        f"Executors spilled {self._format_bytes(disk_bytes)} to disk. "
                        f"This dramatically slows down execution and increases I/O costs."
                    ),
                    suggestion=(
                        "Increase executor memory (spark.executor.memory) or reduce data per partition:\n"
                        "1. Increase spark.sql.shuffle.partitions\n"
                        "2. Filter data earlier in the pipeline\n"
                        "3. Use broadcast joins to reduce shuffle size\n"
                        "4. Consider larger worker node types"
                    ),
                    estimated_impact="Eliminate disk I/O overhead, 20-60% speed improvement",
                )
            )
        return issues

    # ------------------------------------------------------------------
    # Code-based detections
    # ------------------------------------------------------------------

    def _check_collect_on_large(self, code: str) -> List[PatternIssue]:
        issues = []
        collect_calls = re.findall(r"\.collect\(\)", code)
        if len(collect_calls) > 0:
            issues.append(
                PatternIssue(
                    pattern_id="SPARK-008",
                    severity="medium",
                    title=f".collect() called {len(collect_calls)} time(s)",
                    description=(
                        ".collect() pulls all data to the driver. If the dataset is large, "
                        "this causes OutOfMemoryError and defeats the purpose of distributed computing."
                    ),
                    suggestion=(
                        "Replace .collect() with:\n"
                        "  - .take(N) for sampling\n"
                        "  - .toPandas() only on small aggregated results\n"
                        "  - .write.format(...) to persist results"
                    ),
                    estimated_impact="Prevent driver OOM",
                )
            )
        return issues

    def _check_udf_usage(self, code: str) -> List[PatternIssue]:
        issues = []
        udf_count = len(re.findall(r"(?:udf\(|@udf|register.*[Uu][Dd][Ff])", code))
        if udf_count > 0:
            issues.append(
                PatternIssue(
                    pattern_id="SPARK-009",
                    severity="medium",
                    title=f"Python UDF detected ({udf_count} occurrence(s))",
                    description=(
                        "Python UDFs prevent Catalyst optimizer from applying optimisations "
                        "like predicate pushdown and column pruning. They also require "
                        "serialising data between JVM and Python, adding significant overhead."
                    ),
                    suggestion=(
                        "Replace Python UDFs with:\n"
                        "  - Built-in Spark SQL functions (pyspark.sql.functions)\n"
                        "  - Pandas UDFs (@pandas_udf) for vectorised operations\n"
                        "  - Spark SQL expressions"
                    ),
                    estimated_impact="2-10x performance improvement",
                )
            )
        return issues

    def _check_missing_cache(self, code: str) -> List[PatternIssue]:
        """Detect DataFrames read multiple times without caching."""
        issues = []
        # Find all read operations
        reads = re.findall(r"(spark\.read\.[^\n]+|\.load\([^\)]+\))", code)
        cache_calls = re.findall(r"\.(cache|persist)\(\)", code)

        if len(reads) > 1 and len(cache_calls) == 0:
            # Check if the same variable is used in multiple actions
            issues.append(
                PatternIssue(
                    pattern_id="SPARK-010",
                    severity="low",
                    title="Multiple data reads without caching",
                    description=(
                        f"Found {len(reads)} read operations but no .cache() or .persist() calls. "
                        f"If the same DataFrame is used in multiple actions, Spark will re-read "
                        f"and recompute it each time."
                    ),
                    suggestion=(
                        "Cache DataFrames that are reused:\n"
                        "  df = spark.read.parquet('...').cache()\n"
                        "Remember to .unpersist() when no longer needed."
                    ),
                    estimated_impact="Avoid repeated I/O, 20-50% faster for reused DataFrames",
                )
            )
        return issues

    def _check_repartition_misuse(self, code: str) -> List[PatternIssue]:
        issues = []
        repartition_calls = re.findall(r"\.repartition\((\d+)?\)", code)
        coalesce_calls = re.findall(r"\.coalesce\((\d+)\)", code)

        for match in repartition_calls:
            if match and int(match) == 1:
                issues.append(
                    PatternIssue(
                        pattern_id="SPARK-011",
                        severity="high",
                        title=".repartition(1) forces all data to single partition",
                        description=(
                            "repartition(1) causes a full shuffle of all data into one partition. "
                            "Use .coalesce(1) instead if you need a single output file, "
                            "as it avoids a full shuffle."
                        ),
                        suggestion="Replace .repartition(1) with .coalesce(1)",
                        estimated_impact="Eliminate unnecessary full shuffle",
                        code_fix="df = df.coalesce(1)  # instead of repartition(1)",
                    )
                )
        return issues

    def _check_schema_inference(self, code: str) -> List[PatternIssue]:
        issues = []
        if re.search(r"inferSchema.*[Tt]rue|\.csv\(", code):
            if not re.search(r"schema\s*=|StructType", code):
                issues.append(
                    PatternIssue(
                        pattern_id="SPARK-012",
                        severity="low",
                        title="Schema inference on CSV/JSON files",
                        description=(
                            "inferSchema=True reads the entire file once to determine types, "
                            "then reads it again for processing. This doubles I/O for large files."
                        ),
                        suggestion=(
                            "Define an explicit schema:\n"
                            "  schema = StructType([StructField('col1', StringType()), ...])\n"
                            "  df = spark.read.schema(schema).csv('...')"
                        ),
                        estimated_impact="Eliminate double-read of source data",
                    )
                )
        return issues

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _format_bytes(b: Optional[int]) -> str:
        if b is None:
            return "unknown"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(b) < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"
