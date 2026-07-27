"""
Azure Resource Intelligence Collector

Fetches real utilization metrics and resource configuration from Azure
to provide evidence-based recommendations instead of guesswork.

Collects:
  - Azure Monitor metrics (CPU%, DWU%, memory%, connections, etc.)
  - Resource configuration (SKU, tier, auto-pause, auto-scale)
  - Activity log (last operation timestamp)
  - Azure Advisor recommendations (cross-validation)
"""

import json
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceIntelligence:
    """
    Gathers real metrics and config for Azure resources using az CLI.
    All methods return dicts with both the raw data and the az command used,
    so users can verify/re-run themselves.
    """

    # Metric mappings per resource type
    METRICS_MAP = {
        "microsoft.synapse/workspaces/sqlpools": [
            {"name": "DWUUsedPercent", "display": "DWU Used %"},
            {"name": "CPUPercent", "display": "CPU %"},
            {"name": "MemoryUsedPercent", "display": "Memory %"},
            {"name": "ActiveQueries", "display": "Active Queries"},
            {"name": "QueuedQueries", "display": "Queued Queries"},
            {"name": "Connections", "display": "Connections"},
        ],
        "microsoft.synapse/workspaces/bigdatapools": [
            {"name": "BigDataPoolApplicationsActive", "display": "Active Spark Apps"},
            {"name": "BigDataPoolAllocatedCores", "display": "Allocated Cores"},
            {"name": "BigDataPoolAllocatedMemory", "display": "Allocated Memory"},
        ],
        "microsoft.synapse/workspaces": [
            {"name": "IntegrationPipelineRunsEnded", "display": "Pipeline Runs"},
            {"name": "IntegrationActivityRunsEnded", "display": "Activity Runs"},
            {"name": "IntegrationTriggerRunsEnded", "display": "Trigger Runs"},
        ],
        "microsoft.sql/servers/databases": [
            {"name": "dwu_consumption_percent", "display": "DWU Used %"},
            {"name": "cpu_percent", "display": "CPU %"},
            {"name": "connection_successful", "display": "Connections"},
            {"name": "connection_failed", "display": "Failed Connections"},
            {"name": "active_queries", "display": "Active Queries"},
            {"name": "queued_queries", "display": "Queued Queries"},
            {"name": "dwu_used", "display": "DWU Used"},
            {"name": "dwu_limit", "display": "DWU Limit"},
        ],
        "microsoft.sql/servers": [
            {"name": "dtu_consumption_percent", "display": "DTU %"},
            {"name": "cpu_percent", "display": "CPU %"},
            {"name": "connection_successful", "display": "Connections"},
            {"name": "storage_percent", "display": "Storage %"},
        ],
        "microsoft.compute/virtualmachines": [
            {"name": "Percentage CPU", "display": "CPU %"},
            {"name": "Available Memory Bytes", "display": "Available Memory"},
            {"name": "Disk Read Bytes", "display": "Disk Read"},
            {"name": "Disk Write Bytes", "display": "Disk Write"},
            {"name": "Network In Total", "display": "Network In"},
            {"name": "Network Out Total", "display": "Network Out"},
        ],
        "microsoft.web/sites": [
            {"name": "CpuPercentage", "display": "CPU %"},
            {"name": "MemoryPercentage", "display": "Memory %"},
            {"name": "Requests", "display": "Requests"},
            {"name": "Http5xx", "display": "5xx Errors"},
        ],
        "microsoft.storage/storageaccounts": [
            {"name": "UsedCapacity", "display": "Used Capacity"},
            {"name": "Transactions", "display": "Transactions"},
            {"name": "Ingress", "display": "Ingress"},
            {"name": "Egress", "display": "Egress"},
        ],
        "microsoft.datafactory/factories": [
            {"name": "PipelineSucceededRuns", "display": "Succeeded Runs"},
            {"name": "PipelineFailedRuns", "display": "Failed Runs"},
            {"name": "ActivitySucceededRuns", "display": "Activity Succeeded"},
            {"name": "ActivityFailedRuns", "display": "Activity Failed"},
            {"name": "IntegrationRuntimeCpuPercentage", "display": "IR CPU %"},
        ],
        "microsoft.dbformysql/servers": [
            {"name": "cpu_percent", "display": "CPU %"},
            {"name": "memory_percent", "display": "Memory %"},
            {"name": "active_connections", "display": "Active Connections"},
        ],
        "microsoft.documentdb/databaseaccounts": [
            {"name": "TotalRequestUnits", "display": "Total RU/s"},
            {"name": "NormalizedRUConsumption", "display": "Normalized RU %"},
            {"name": "TotalRequests", "display": "Total Requests"},
        ],
        "microsoft.containerregistry/registries": [
            {"name": "StorageUsed", "display": "Storage Used"},
            {"name": "TotalPullCount", "display": "Total Pulls"},
            {"name": "TotalPushCount", "display": "Total Pushes"},
        ],
        "microsoft.cache/redis": [
            {"name": "percentProcessorTime", "display": "CPU %"},
            {"name": "usedmemorypercentage", "display": "Memory %"},
            {"name": "connectedclients", "display": "Connected Clients"},
            {"name": "totalcommandsprocessed", "display": "Commands/sec"},
        ],
    }

    @staticmethod
    def run_az_command(command: str, timeout: int = 60) -> Dict[str, Any]:
        """Run an az CLI command and return structured result."""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()

            # Try to parse as JSON
            data = None
            if result.returncode == 0 and output:
                try:
                    data = json.loads(output)
                except (json.JSONDecodeError, ValueError):
                    data = output

            return {
                "success": result.returncode == 0,
                "command": command,
                "output": output[:5000],
                "data": data,
                "error": result.stderr.strip()[:1000] if result.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "command": command, "error": "Command timed out", "data": None}
        except Exception as e:
            return {"success": False, "command": command, "error": str(e)[:500], "data": None}

    @classmethod
    def get_metrics_for_resource(
        cls,
        resource_id: str,
        resource_type: str = None,
        days: int = 7,
        interval: str = "PT1H",
    ) -> Dict[str, Any]:
        """
        Fetch Azure Monitor metrics for a resource.
        Returns the command used + raw metric data so user can verify.
        """
        end_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        start_time = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Get metrics list — always prefer type inferred from resource_id (most specific)
        inferred = cls._infer_type_from_id(resource_id)
        effective_type = inferred if inferred else (resource_type or "").lower()
        metrics_config = cls.METRICS_MAP.get(effective_type)

        # Fallback: scan METRICS_MAP keys by specificity (longest match first)
        if not metrics_config:
            res_id_lower = (resource_id or "").lower()
            for key, config in sorted(cls.METRICS_MAP.items(), key=lambda x: -len(x[0])):
                if key in res_id_lower:
                    metrics_config = config
                    break

        if not metrics_config:
            # Generic: just list available metrics
            cmd = f'az monitor metrics list-definitions --resource "{resource_id}" --query "[].{{name:name.value, unit:unit}}" --output json'
            return cls.run_az_command(cmd)

        # Fetch each metric
        metric_names = " ".join(m["name"] for m in metrics_config)
        cmd = (
            f'az monitor metrics list --resource "{resource_id}" '
            f'--metric {metric_names} '
            f'--interval {interval} '
            f'--start-time {start_time} --end-time {end_time} '
            f'--aggregation Average Maximum Minimum '
            f'--output json'
        )

        result = cls.run_az_command(cmd)
        result["metrics_requested"] = [m["display"] for m in metrics_config]
        result["period"] = f"{days} days ({start_time} to {end_time})"
        return result

    @classmethod
    def get_resource_config(cls, resource_id: str) -> Dict[str, Any]:
        """Fetch resource configuration (SKU, tier, auto-pause, etc.)."""
        cmd = f'az resource show --ids "{resource_id}" --query "{{name:name, sku:sku, kind:kind, location:location, tags:tags, properties:properties}}" --output json'
        return cls.run_az_command(cmd)

    @classmethod
    def get_activity_log(cls, resource_id: str, days: int = 7) -> Dict[str, Any]:
        """Get recent activity log entries to see last operation."""
        start_time = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cmd = (
            f'az monitor activity-log list '
            f'--resource-id "{resource_id}" '
            f'--start-time {start_time} '
            f'--query "[].{{operation:operationName.localizedValue, status:status.value, time:eventTimestamp, caller:caller}}" '
            f'--output json'
        )
        return cls.run_az_command(cmd)

    @classmethod
    def get_advisor_recommendations(cls, resource_id: str) -> Dict[str, Any]:
        """Get Azure Advisor recommendations for a specific resource."""
        cmd = (
            f'az advisor recommendation list '
            f'--query "[?resourceMetadata.resourceId==\'{resource_id}\'].'
            f'{{category:category, impact:impact, problem:shortDescription.problem, '
            f'solution:shortDescription.solution}}" '
            f'--output json'
        )
        return cls.run_az_command(cmd)

    @classmethod
    def diagnose_resource(
        cls,
        resource_id: str,
        resource_type: str = None,
        resource_name: str = None,
        subscription_id: str = None,
    ) -> Dict[str, Any]:
        """
        Full diagnostic for a resource: metrics + config + activity + advisor.
        Returns all evidence needed for an informed recommendation.
        """
        # ALWAYS extract subscription from resource_id — it's the ground truth
        if "/subscriptions/" in resource_id:
            parts = resource_id.lower().split("/subscriptions/")
            if len(parts) > 1:
                subscription_id = parts[1].split("/")[0]

        # ALWAYS infer type from resource_id — it's more specific than stored resource_type
        # e.g., resource_id contains "/sqlpools/" -> "microsoft.synapse/workspaces/sqlpools"
        # but stored resource_type might just be "microsoft.synapse/workspaces"
        inferred_type = cls._infer_type_from_id(resource_id)
        effective_type = inferred_type if inferred_type else (resource_type or "")

        results = {
            "resource_id": resource_id,
            "resource_name": resource_name or resource_id.rsplit("/", 1)[-1],
            "resource_type": effective_type,
            "subscription_id": subscription_id,
            "diagnosed_at": datetime.utcnow().isoformat(),
            "diagnostics": {},
            "commands_used": [],
        }

        # Switch subscription if needed
        if subscription_id:
            switch_cmd = f"az account set --subscription {subscription_id}"
            switch_result = cls.run_az_command(switch_cmd)
            results["commands_used"].append(switch_cmd)
            if not switch_result["success"]:
                results["diagnostics"]["subscription_switch"] = switch_result
                return results

        # 1. Resource config
        config = cls.get_resource_config(resource_id)
        results["diagnostics"]["configuration"] = config
        results["commands_used"].append(config["command"])

        # 2. Metrics (7-day)
        metrics = cls.get_metrics_for_resource(resource_id, resource_type, days=7)
        results["diagnostics"]["metrics_7d"] = metrics
        results["commands_used"].append(metrics["command"])

        # 3. Activity log
        activity = cls.get_activity_log(resource_id, days=7)
        results["diagnostics"]["activity_log"] = activity
        results["commands_used"].append(activity["command"])

        # 4. Advisor recommendations
        advisor = cls.get_advisor_recommendations(resource_id)
        results["diagnostics"]["advisor"] = advisor
        results["commands_used"].append(advisor["command"])

        return results

    @classmethod
    def analyze_from_metrics(cls, diagnostics: Dict) -> Dict[str, Any]:
        """
        Pure metrics-based analysis. ALL scores are calculated from real data.
        Nothing is hardcoded. Returns structured analysis that the summary and UI can use.
        """
        diag = diagnostics.get("diagnostics", {})
        resource_type = diagnostics.get("resource_type", "")

        # ── Extract config ──
        sku_name = ""
        sku_tier = ""
        location = ""
        state = ""
        auto_pause_enabled = None  # None=unknown, True/False
        auto_pause_delay = None
        auto_resume = None
        tags = {}
        config = diag.get("configuration", {})
        if config.get("success") and isinstance(config.get("data"), dict):
            cfg = config["data"]
            sku = cfg.get("sku") or {}
            sku_name = (sku.get("name") or "").strip()
            sku_tier = (sku.get("tier") or "").strip()
            location = cfg.get("location", "")
            props = cfg.get("properties") or {}
            state = props.get("status", props.get("state", ""))
            # Check auto-pause / auto-resume configuration
            for key in ("autoPauseDelay", "autopauseDelay", "autoScaleProperties"):
                if key in str(props):
                    val = props.get(key, props.get("autoPauseDelay"))
                    if val is not None:
                        if isinstance(val, dict):
                            auto_pause_enabled = val.get("enabled", None)
                            auto_pause_delay = val.get("delayInMinutes", None)
                        elif str(val).isdigit():
                            auto_pause_delay = int(val)
                            auto_pause_enabled = int(val) > 0
                        elif val == -1 or val == "-1":
                            auto_pause_enabled = False
            if "autoResumeDelay" in str(props) or "automaticResume" in str(props):
                auto_resume = True
            tags = cfg.get("tags") or {}

        # ── Extract metrics into structured form ──
        metric_data = {}
        metrics = diag.get("metrics_7d", {})
        if metrics.get("success") and isinstance(metrics.get("data"), dict):
            for m in (metrics["data"].get("value") or []):
                name = (m.get("name") or {}).get("localizedValue", "Unknown")
                metric_key = (m.get("name") or {}).get("value", name)
                ts = m.get("timeseries") or []
                if ts and ts[0].get("data"):
                    vals = [
                        d.get("average") if d.get("average") is not None
                        else d.get("maximum") if d.get("maximum") is not None
                        else d.get("total")
                        for d in ts[0]["data"]
                        if d.get("average") is not None or d.get("maximum") is not None or d.get("total") is not None
                    ]
                    if vals:
                        metric_data[metric_key] = {
                            "name": name, "avg": sum(vals) / len(vals),
                            "max": max(vals), "min": min(vals),
                            "samples": len(vals),
                            "non_zero_samples": sum(1 for v in vals if v > 0),
                            "total": sum(vals),
                        }

        # ── Activity log ──
        activity_count = 0
        recent_ops = []
        activity = diag.get("activity_log", {})
        if activity.get("success") and isinstance(activity.get("data"), list):
            activity_count = len(activity["data"])
            recent_ops = activity["data"][:5]

        # ── Advisor ──
        advisor_recs = []
        advisor = diag.get("advisor", {})
        if advisor.get("success") and isinstance(advisor.get("data"), list):
            advisor_recs = advisor["data"][:5]

        # ═══════════════════════════════════════════════
        # CALCULATE UTILIZATION SCORE FROM REAL METRICS
        # ═══════════════════════════════════════════════
        utilization_scores = []  # each metric's utilization as 0-100
        for key, md in metric_data.items():
            nl = md["name"].lower()
            if any(k in nl for k in ("percent", "%", "cpu", "dwu", "dtu", "memory", "ru consumption")):
                # This is a percentage metric — use directly
                utilization_scores.append({
                    "metric": md["name"],
                    "avg_pct": md["avg"],
                    "peak_pct": md["max"],
                    "samples": md["samples"],
                    "active_samples": md["non_zero_samples"],
                    "active_ratio": md["non_zero_samples"] / md["samples"] if md["samples"] else 0,
                })

        # Activity-based score for non-compute resources (ADF, Storage, etc.)
        activity_score = None
        for key, md in metric_data.items():
            nl = md["name"].lower()
            if any(k in nl for k in ("run", "request", "transaction", "command")):
                ratio = md["non_zero_samples"] / md["samples"] if md["samples"] else 0
                activity_score = {
                    "metric": md["name"],
                    "total": md["total"],
                    "avg": md["avg"],
                    "active_hours_pct": ratio * 100,
                    "active_samples": md["non_zero_samples"],
                    "total_samples": md["samples"],
                }
                break

        # ── Composite utilization score (0-100) ──
        if utilization_scores:
            # Weighted: peak matters more than avg for rightsizing
            composite = 0
            for us in utilization_scores:
                # Score = 60% avg + 40% peak (peak ensures you don't downsize below burst needs)
                score = us["avg_pct"] * 0.6 + us["peak_pct"] * 0.4
                composite = max(composite, score)
            utilization_score = round(min(composite, 100), 1)
        elif activity_score:
            # No percentage metrics but has activity counts — score by active hours ratio
            utilization_score = round(min(activity_score["active_hours_pct"], 100), 1)
        elif activity_count > 5:
            # Only activity log available — give a moderate score
            utilization_score = round(min(activity_count / 2, 80), 1)
        else:
            utilization_score = 0.0

        # ── Savings potential (0-100%) — inverse of utilization ──
        # But capped: if something is 30% utilized, potential = 70% * safety_factor
        # Safety factor = 0.8 (keep 20% headroom for bursts)
        if utilization_score >= 80:
            savings_potential = 0
        elif utilization_score >= 50:
            savings_potential = round((100 - utilization_score) * 0.5, 1)  # conservative
        elif utilization_score > 0:
            savings_potential = round((100 - utilization_score) * 0.7, 1)  # more aggressive
        else:
            savings_potential = 95  # near-total waste (keep 5% for storage costs)

        # ── Identify improvement areas ──
        improvement_areas = []

        # Auto-pause check
        is_sql_pool = "sqlpool" in resource_type.lower() or ("sql/servers" in resource_type.lower() and "database" in resource_type.lower())
        is_synapse_pool = "synapse" in resource_type.lower() and "pool" in resource_type.lower()
        if (is_sql_pool or is_synapse_pool) and auto_pause_enabled is not True:
            improvement_areas.append({
                "area": "Auto-Pause Not Enabled",
                "impact": "high",
                "detail": "Enable auto-pause to automatically pause during idle periods. This alone can save 50-90% of compute cost for intermittent workloads.",
                "action": "Enable auto-pause with a 60-minute inactivity timeout",
            })

        if (is_sql_pool or is_synapse_pool) and auto_resume is not True:
            improvement_areas.append({
                "area": "Auto-Resume Not Configured",
                "impact": "medium",
                "detail": "Without auto-resume, paused pools must be manually resumed, risking blocked workflows.",
                "action": "Enable auto-resume so the pool wakes on connection",
            })

        # Overprovisioned check (from metrics)
        if utilization_scores:
            best = max(utilization_scores, key=lambda x: x["peak_pct"])
            if best["peak_pct"] < 30 and best["peak_pct"] > 0:
                improvement_areas.append({
                    "area": "Overprovisioned SKU",
                    "impact": "high",
                    "detail": f"Peak {best['metric']} is only {best['peak_pct']:.1f}% over 7 days. The current SKU has far more capacity than needed.",
                    "action": f"Right-size to a smaller SKU that matches the ~{best['peak_pct']:.0f}% peak with 30% headroom",
                })
            elif best["avg_pct"] < 10 and best["peak_pct"] < 50:
                improvement_areas.append({
                    "area": "Low Average Utilization",
                    "impact": "medium",
                    "detail": f"Average {best['metric']} is only {best['avg_pct']:.1f}% with peak {best['peak_pct']:.1f}%. Resource is mostly idle.",
                    "action": "Consider downsizing or enabling auto-scale",
                })

        # Completely idle check
        if utilization_score == 0 and activity_count <= 2:
            improvement_areas.append({
                "area": "Resource Appears Completely Unused",
                "impact": "critical",
                "detail": "Zero utilization metrics and minimal activity in 7 days. This resource may be abandoned.",
                "action": "Verify with resource owner. If unused, pause or delete.",
            })

        # Tag compliance
        expected_tags = ["Environment", "CostCenter", "Owner", "Team", "Project"]
        missing_tags = [t for t in expected_tags if not any(k.lower() == t.lower() for k in tags)]
        if len(missing_tags) >= 3:
            improvement_areas.append({
                "area": "Missing Cost Tags",
                "impact": "low",
                "detail": f"Missing tags: {', '.join(missing_tags[:4])}. Without tags, costs can't be allocated to teams/projects.",
                "action": f"Add tags: {', '.join(missing_tags[:3])}",
            })

        is_paused = state.lower() in ("paused", "offline", "suspended") if state else False

        return {
            "utilization_score": utilization_score,
            "savings_potential_pct": savings_potential,
            "utilization_details": utilization_scores,
            "activity_score": activity_score,
            "activity_count": activity_count,
            "recent_ops": recent_ops,
            "improvement_areas": improvement_areas,
            "advisor_recs": advisor_recs,
            "config": {
                "sku": sku_name, "tier": sku_tier, "location": location,
                "state": state, "is_paused": is_paused,
                "auto_pause_enabled": auto_pause_enabled,
                "auto_pause_delay_min": auto_pause_delay,
                "auto_resume": auto_resume,
                "tags": tags,
            },
            "resource_type": resource_type,
            "friendly_type": cls._friendly_type_name(resource_type),
            "metric_data": {k: {"name": v["name"], "avg": v["avg"], "max": v["max"], "min": v["min"], "samples": v["samples"]} for k, v in metric_data.items()},
        }

    @classmethod
    def generate_evidence_summary(cls, diagnostics: Dict) -> str:
        """Convert raw diagnostics into a manager-friendly evidence report.
        All numbers are calculated from actual metrics — nothing is hardcoded."""

        analysis = cls.analyze_from_metrics(diagnostics)
        resource_name = diagnostics.get("resource_name", "Unknown")
        cfg = analysis["config"]
        friendly_type = analysis["friendly_type"]
        score = analysis["utilization_score"]
        savings = analysis["savings_potential_pct"]
        improvements = analysis["improvement_areas"]

        # ── Verdict from score ──
        if cfg["is_paused"]:
            verdict_emoji = "⏸️"
            verdict = "PAUSED — NOT INCURRING COMPUTE COSTS"
        elif score == 0:
            verdict_emoji = "🔴"
            verdict = "IDLE — ZERO UTILIZATION DETECTED"
        elif score < 10:
            verdict_emoji = "🔴"
            verdict = "NEAR-IDLE — MINIMAL UTILIZATION"
        elif score < 30:
            verdict_emoji = "🟠"
            verdict = "UNDERUTILIZED"
        elif score < 60:
            verdict_emoji = "🟡"
            verdict = "MODERATELY UTILIZED"
        elif score < 80:
            verdict_emoji = "🟢"
            verdict = "WELL UTILIZED"
        else:
            verdict_emoji = "🟢"
            verdict = "HEAVILY UTILIZED"

        L = []

        # ═══ Header ═══
        L.append(f"{verdict_emoji}  VERDICT: {verdict}")
        L.append("=" * 60)
        L.append("")

        # ═══ Scores calculated from metrics ═══
        L.append("📊 METRICS-BASED ASSESSMENT")
        L.append("-" * 40)
        bar_filled = int(score / 5)  # 20-char bar
        bar_empty = 20 - bar_filled
        bar = "█" * bar_filled + "░" * bar_empty
        L.append(f"  Utilization Score:    [{bar}] {score}%")
        L.append(f"  Savings Potential:    {savings}%")
        L.append(f"  (calculated from {len(analysis['utilization_details'])} metrics over 7 days, {analysis['activity_count']} activity log events)")
        L.append("")

        # ═══ Resource summary ═══
        L.append("📋 RESOURCE")
        L.append("-" * 40)
        L.append(f"  Name:       {resource_name}")
        L.append(f"  Type:       {friendly_type}")
        tier_str = f" ({cfg['tier']})" if cfg['tier'] else ""
        L.append(f"  SKU:        {cfg['sku'] or 'Unknown'}{tier_str}")
        L.append(f"  Region:     {cfg['location'] or 'Unknown'}")
        if cfg["state"]:
            L.append(f"  State:      {cfg['state']}")
        # Auto-pause/resume status
        if cfg["auto_pause_enabled"] is True:
            L.append(f"  Auto-Pause: ✅ Enabled (after {cfg['auto_pause_delay_min']} min)")
        elif cfg["auto_pause_enabled"] is False:
            L.append(f"  Auto-Pause: ❌ Not Enabled")
        if cfg["auto_resume"] is True:
            L.append(f"  Auto-Resume: ✅ Enabled")
        L.append("")

        # ═══ Metric details ═══
        if analysis["utilization_details"]:
            L.append("📈 UTILIZATION METRICS (7-day window)")
            L.append("-" * 40)
            for ud in analysis["utilization_details"]:
                active_pct = ud["active_ratio"] * 100
                bar_f = int(ud["avg_pct"] / 5)
                bar_e = 20 - bar_f
                bar = "█" * bar_f + "░" * bar_e
                L.append(f"  {ud['metric']}:")
                L.append(f"    [{bar}] avg {ud['avg_pct']:.1f}% | peak {ud['peak_pct']:.1f}%")
                L.append(f"    Active in {ud['active_samples']}/{ud['samples']} samples ({active_pct:.0f}% of the time)")
            L.append("")

        if analysis["activity_score"]:
            asc = analysis["activity_score"]
            L.append("🔄 ACTIVITY METRICS")
            L.append("-" * 40)
            L.append(f"  {asc['metric']}: {asc['total']:.0f} total over 7 days (avg {asc['avg']:.1f}/hour)")
            L.append(f"  Active in {asc['active_samples']}/{asc['total_samples']} time windows ({asc['active_hours_pct']:.0f}% of the time)")
            L.append("")

        # Other metrics
        shown_keys = set()
        for ud in analysis["utilization_details"]:
            shown_keys.add(ud["metric"])
        if analysis["activity_score"]:
            shown_keys.add(analysis["activity_score"]["metric"])
        other = {k: v for k, v in analysis["metric_data"].items() if v["name"] not in shown_keys}
        if other:
            L.append("📊 OTHER METRICS")
            L.append("-" * 40)
            for k, v in other.items():
                L.append(f"  {v['name']}: avg {v['avg']:.1f}, peak {v['max']:.1f} ({v['samples']} samples)")
            L.append("")

        # ═══ Improvement areas ═══
        if improvements:
            L.append(f"🎯 IMPROVEMENT AREAS ({len(improvements)} found)")
            L.append("-" * 40)
            for imp in improvements:
                impact_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "ℹ️"}.get(imp["impact"], "📌")
                L.append(f"  {impact_icon} [{imp['impact'].upper()}] {imp['area']}")
                L.append(f"     {imp['detail']}")
                L.append(f"     → Action: {imp['action']}")
                L.append("")

        # ═══ Activity log ═══
        if analysis["recent_ops"]:
            L.append("📅 RECENT ACTIVITY")
            L.append("-" * 40)
            L.append(f"  {analysis['activity_count']} operations in the last 7 days")
            for op in analysis["recent_ops"][:3]:
                t = (op.get("time") or "")[:16]
                L.append(f"  {t}  {op.get('operation', '')[:50]}  [{op.get('status', '')}]")
            L.append("")

        # ═══ Azure Advisor ═══
        if analysis["advisor_recs"]:
            L.append("🏷️  AZURE ADVISOR")
            L.append("-" * 40)
            for r in analysis["advisor_recs"]:
                L.append(f"  [{(r.get('impact') or '?').upper()}] {r.get('problem', '')[:70]}")
                sol = r.get("solution", "")
                if sol:
                    L.append(f"    → {sol[:90]}")
            L.append("")

        # ═══ Tags ═══
        if cfg["tags"]:
            L.append("🏷️  RESOURCE TAGS")
            L.append("-" * 40)
            for k, v in list(cfg["tags"].items())[:6]:
                L.append(f"  {k}: {v}")
            L.append("")

        return "\n".join(L)

    @staticmethod
    def _friendly_type_name(resource_type: str) -> str:
        """Convert Azure resource type to human-friendly name."""
        mapping = {
            "microsoft.synapse/workspaces/sqlpools": "Synapse Dedicated SQL Pool",
            "microsoft.synapse/workspaces/bigdatapools": "Synapse Spark Pool",
            "microsoft.synapse/workspaces": "Synapse Workspace",
            "microsoft.sql/servers/databases": "SQL Data Warehouse (Dedicated SQL Pool)",
            "microsoft.sql/servers": "SQL Server",
            "microsoft.compute/virtualmachines": "Virtual Machine",
            "microsoft.web/sites": "App Service / Web App",
            "microsoft.datafactory/factories": "Data Factory",
            "microsoft.storage/storageaccounts": "Storage Account",
            "microsoft.documentdb/databaseaccounts": "Cosmos DB",
            "microsoft.cache/redis": "Redis Cache",
            "microsoft.containerregistry/registries": "Container Registry",
            "microsoft.dbformysql/servers": "MySQL Database",
        }
        return mapping.get(resource_type.lower(), resource_type)

    @staticmethod
    def _suggest_downsize(current_sku: str, avg_util: float) -> str:
        """Suggest a downsized SKU based on utilization."""
        sku_order = [
            "DW100c", "DW200c", "DW300c", "DW400c", "DW500c",
            "DW1000c", "DW1500c", "DW2000c", "DW2500c", "DW3000c",
            "DW5000c", "DW6000c", "DW7500c", "DW10000c", "DW15000c", "DW30000c",
        ]
        try:
            idx = next(i for i, s in enumerate(sku_order) if s.lower() == current_sku.lower())
        except StopIteration:
            return "DW100c"
        # If near-idle, go to minimum
        if avg_util < 5:
            return "DW100c"
        # Otherwise drop by roughly proportional amount
        target_idx = max(0, int(idx * (avg_util / 100) * 1.5))
        return sku_order[target_idx]

    @staticmethod
    def _infer_type_from_id(resource_id: str) -> str:
        """Infer resource type from Azure resource ID path."""
        rid = resource_id.lower()
        if "/sqlpools/" in rid:
            return "microsoft.synapse/workspaces/sqlpools"
        if "/bigdatapools/" in rid:
            return "microsoft.synapse/workspaces/bigdatapools"
        if "/microsoft.synapse/workspaces" in rid:
            return "microsoft.synapse/workspaces"
        if "/microsoft.sql/servers" in rid and "/databases/" in rid:
            return "microsoft.sql/servers/databases"
        if "/microsoft.sql/servers" in rid:
            return "microsoft.sql/servers"
        if "/microsoft.compute/virtualmachines" in rid:
            return "microsoft.compute/virtualmachines"
        if "/microsoft.web/sites" in rid:
            return "microsoft.web/sites"
        if "/microsoft.datafactory/factories" in rid:
            return "microsoft.datafactory/factories"
        if "/microsoft.storage/storageaccounts" in rid:
            return "microsoft.storage/storageaccounts"
        if "/microsoft.documentdb/databaseaccounts" in rid:
            return "microsoft.documentdb/databaseaccounts"
        if "/microsoft.cache/redis" in rid:
            return "microsoft.cache/redis"
        if "/microsoft.containerregistry/registries" in rid:
            return "microsoft.containerregistry/registries"
        # Extract from providers path
        parts = rid.split("/providers/")
        if len(parts) > 1:
            type_parts = parts[-1].split("/")
            if len(type_parts) >= 2:
                return "/".join(type_parts[:2])
        return ""
