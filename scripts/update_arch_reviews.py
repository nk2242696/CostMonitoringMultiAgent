"""Update architecture review descriptions with detailed implementation steps."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "dev")

from src.common.database import get_database
from src.models import AIRecommendation

DETAILS = {
    "Microsoft Fabric": """**Service:** Microsoft Fabric | **Resources:** 1 | **Monthly Cost:** $453.12

## Current Issue
Microsoft Fabric capacity units (CU) are running 24/7 including non-business hours. Analysis shows only 30% active utilization during business hours and near-zero usage overnight/weekends.

## Proposed Solutions

### 1. Capacity Pause/Resume Scheduling — Saves ~$226/month (50%)
Pause Fabric capacity during non-business hours (7 PM – 8 AM weekdays + weekends).
- Risk: LOW — no data loss, only compute paused

### 2. Right-size Capacity SKU — Saves ~$90/month (20%)
Current F64 is over-provisioned. Downsize to F32 based on actual CU consumption.
- Risk: MEDIUM — monitor query performance after resize

### 3. Workspace Governance — Saves ~$45/month (10%)
Consolidate workloads and prevent developer sprawl across workspaces.

## Implementation Steps
1. Enable Azure Automation runbook to pause/resume capacity on schedule
2. Set up monitoring alerts for CU utilization > 80%
3. Analyze CU consumption over 7 days with pause/resume active
4. Evaluate F32 SKU based on peak usage, resize during maintenance window
5. Audit workspaces and consolidate duplicate/test datasets
6. Implement workspace-level RBAC to prevent uncontrolled provisioning""",

    "Logic Apps": """**Service:** Logic Apps | **Resources:** 13 | **Monthly Cost:** $333.79

## Current Issue
13 Logic Apps use polling triggers (every 1-5 minutes), generating millions of unnecessary executions. Several workflows process records one-at-a-time instead of batching.

## Proposed Solutions

### 1. Switch Polling to Event-Based Triggers — Saves ~$117/month (35%)
Replace Recurrence/HTTP polling with Service Bus, Event Grid, or webhook triggers.
- Risk: LOW — event-based is more reliable than polling

### 2. Batch Operations — Saves ~$67/month (20%)
Consolidate single-record workflows into batch runs using ForEach with concurrency.

### 3. Migrate High-Volume Workflows to Functions — Saves ~$50/month (15%)
Logic Apps costing > $20/month with simple logic are cheaper as Azure Functions.

## Implementation Steps
1. Inventory all 13 Logic Apps — trigger types, execution counts, per-run cost
2. Identify top 5 by execution count, replace polling with Event Grid triggers
3. Implement batching for record-processing workflows
4. Migrate simple high-frequency Logic Apps to Azure Functions (Consumption plan)
5. Set up execution count alerts to catch regressions
6. Monitor cost reduction over 2 weeks and validate savings""",

    "Virtual Machines": """**Service:** Virtual Machines | **Resources:** 1 | **Monthly Cost:** $278.13

## Current Issue
VM running 24/7 at Standard_D4s_v3 (4 vCPU, 16 GB) but Azure Monitor shows avg CPU 12%, memory 35%. This is a dev/test workload running outside business hours unnecessarily.

## Proposed Solutions

### 1. Right-Size to B2ms Burstable — Saves ~$139/month (50%)
Switch D4s_v3 → B2ms (2 vCPU, 8 GB). B-series handles the observed low-CPU pattern at 60% lower cost.
- Risk: LOW — burstable handles intermittent workloads well

### 2. Auto-Shutdown Schedule — Saves ~$83/month (30%)
Shut down 7 PM – 8 AM weekdays + weekends. Saves 65% of runtime hours.

### 3. Reserved Instance 1-Year — Saves ~$97/month (35%)
If VM must stay D4s_v3 24/7, a 1-year RI commitment saves 35%.

### 4. Azure Hybrid Benefit — Saves ~$42/month (15%)
Apply existing Windows Server licenses for additional savings.

## Implementation Steps
1. Review Azure Monitor CPU/memory metrics for last 30 days
2. Enable auto-shutdown at 7 PM UTC with email notification
3. Test workload on Standard_B2ms in parallel deployment
4. Resize VM during maintenance window if B2ms test passes
5. Apply Azure Hybrid Benefit if Windows Server licensed
6. Evaluate 1-year RI purchase if steady-state confirmed""",

    "Functions": """**Service:** Azure Functions | **Resources:** 1 | **Monthly Cost:** $177.70

## Current Issue
Function app on Premium EP1 plan (1 always-ready instance) but execution is bursty — active only 15% of the time. Premium has fixed minimum cost even when idle.

## Proposed Solutions

### 1. Switch to Consumption Plan — Saves ~$106/month (60%)
Functions with < 5 min execution and < 1M executions/month are 60% cheaper on Consumption.
- Risk: MEDIUM — cold start increases by 2-5 seconds

### 2. Reduce Always-Ready Instances — Saves ~$53/month (30%)
If Premium needed for VNET, set always-ready to 0 and rely on scale-out.

### 3. Consolidate Function Apps — Saves ~$35/month (20%)
Multiple function apps on separate plans can share one Premium plan.

## Implementation Steps
1. Audit function execution metrics — duration, frequency, memory
2. Identify functions with < 5 min execution and no VNET dependency
3. Migrate qualifying functions to Consumption plan
4. Set max scale-out limit (e.g., 5 instances) to prevent cost spikes
5. Consolidate remaining Premium function apps onto shared plan
6. Monitor cold start impact and revert if SLA affected""",

    "Microsoft Defender for Cloud": """**Service:** Microsoft Defender for Cloud | **Resources:** 36 | **Monthly Cost:** $67.32

## Current Issue
All Defender plans enabled across 36 resources including dev/test environments. Plan 2 (enhanced) enabled for servers that only need Plan 1 (basic).

## Proposed Solutions

### 1. Disable Plans for Dev/Test — Saves ~$20/month (30%)
Exclude dev/test resource groups from Defender or use free tier.
- Risk: LOW — dev/test has lower security requirements

### 2. Downgrade Server Plan 2 → Plan 1 — Saves ~$10/month (15%)
Plan 1 covers vulnerability scanning + EDR. Plan 2 adds file integrity monitoring — often unnecessary.

### 3. Disable Unused Resource Type Plans — Saves ~$7/month (10%)
Turn off Defender for resource types with < 3 resources (DNS, Key Vault).

## Implementation Steps
1. List all Defender plans per subscription with per-resource cost breakdown
2. Tag resources as prod/dev/test if not already tagged
3. Disable Defender plans for dev/test resource groups
4. Downgrade Servers Plan 2 → Plan 1 on non-critical workloads
5. Disable plans for resource types with < 3 resources
6. Review Defender security score to confirm no critical gaps""",
}

db = get_database()
s = db.get_session_factory()()
from sqlalchemy import text
updated = 0
for svc_name, detail in DETAILS.items():
    result = s.execute(
        text("UPDATE ai_recommendations SET description = :desc WHERE recommendation_type = 'architecture_review' AND title LIKE :pattern"),
        {"desc": detail, "pattern": f"%{svc_name}%"}
    )
    updated += result.rowcount
s.commit()
s.close()
print(f"Updated {updated} architecture review records with detailed solutions")
