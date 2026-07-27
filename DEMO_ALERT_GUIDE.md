## 🚨 Azure Cost Monitoring - Alert Setup & Demo Guide

### ✅ Current Alert Status

**Budget Status**: 103.79% of $120,000 monthly budget
- Current spend: $124,543.37
- **Over budget by**: $4,543.37

**MoM Change**: -1.60% (decrease from October)
- October: $126,572.40
- November: $124,543.37

**Service Cost Spikes Detected** (>20% increase):
1. **Load Balancer**: +45.58% ($10,872 → $15,827) ⚠️
2. **Azure Functions**: +28.63% ($14,131 → $18,177) ⚠️
3. **Key Vault**: +27.04% ($11,501 → $14,612) ⚠️
4. **Container Registry**: +26.74% ($9,717 → $12,316) ⚠️

---

### 📋 Alert Rules Configuration

#### Alert 1: Budget Exceeded (CRITICAL)
- **Threshold**: > 105% of budget
- **Current**: 103.79% (close to threshold!)
- **Action**: Send Teams notification
- **Query**:
```sql
WITH current_spend AS (
    SELECT SUM(cost) as total FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
    AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
),
budget AS (
    SELECT SUM(budget_amount) as total FROM cost_budgets
    WHERE is_active = true AND time_period = 'monthly'
)
SELECT ROUND((c.total / b.total * 100)::numeric, 2) as budget_percent
FROM current_spend c, budget b;
```

#### Alert 2: High MoM Increase (WARNING)
- **Threshold**: > 15% increase month-over-month
- **Current**: -1.60% (no alert)
- **Would trigger if**: Costs increase >15% next month

#### Alert 3: Service Cost Spike (WARNING)
- **Threshold**: > 50% increase for any service
- **Current**: Load Balancer at 45.58% (close!)
- **Would trigger if**: Any service >50% increase

---

### 🔧 Teams Webhook Setup

**Step 1: Create Webhook in Teams**
1. Open your Teams channel (e.g., "Cost Monitoring")
2. Click "..." menu → "Connectors"
3. Search "Incoming Webhook"
4. Click "Configure"
5. Name: "Azure Cost Alerts"
6. Upload icon (optional)
7. Click "Create"
8. **Copy the webhook URL** (looks like: https://outlook.office.com/webhook/...)

**Step 2: Configure in Grafana**
1. Navigate to: **Alerting** → **Contact points**
2. Click "**+ New contact point**"
3. Fill in:
   - **Name**: `Teams - Cost Alerts`
   - **Integration**: Select "**Webhook**"
   - **URL**: Paste your Teams webhook URL
   - **HTTP Method**: **POST**
   - **Title**: `Azure Cost Alert: {{ .GroupLabels.alertname }}`
   - **Message**: 
```
🚨 **{{ .GroupLabels.alertname }}**

**Status**: {{ .Status }}
**Severity**: {{ .CommonLabels.severity }}
**Details**: {{ .CommonAnnotations.description }}

**Triggered**: {{ .StartsAt }}

[View Dashboard](http://localhost:3000/d/azure-cost-trends/)
```
4. Click "**Test**" to verify
5. Click "**Save contact point**"

**Step 3: Create Notification Policy**
1. Go to: **Alerting** → **Notification policies**
2. Click "**+ New specific policy**"
3. Configure:
   - **Matching labels**: `severity = critical` OR `severity = warning`
   - **Contact point**: `Teams - Cost Alerts`
   - **Group by**: `alertname`
   - **Group wait**: 30 seconds
   - **Group interval**: 5 minutes
   - **Repeat interval**: 12 hours
4. Click "**Save policy**"

---

### 📊 Create Alert Rules in Grafana

**Alert 1: Budget Exceeded**

1. Navigate: **Alerting** → **Alert rules** → **+ New alert rule**
2. Configure:

**Rule name**: `Budget Exceeded Alert`

**Section 1 - Set an alert rule query and condition**:
- **Query A**:
  - Data source: `PostgreSQL`
  - Query:
```sql
WITH current_spend AS (
    SELECT SUM(cost) as total FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
),
budget AS (
    SELECT SUM(budget_amount) as total FROM cost_budgets
    WHERE is_active = true AND time_period = 'monthly'
)
SELECT NOW() as time, ROUND((c.total / NULLIF(b.total, 0) * 100)::numeric, 2) as value
FROM current_spend c, budget b;
```

- **Expression B**: `Reduce` (Last value)
- **Expression C**: `Threshold` (IS ABOVE 100)

**Section 2 - Set alert evaluation behavior**:
- **Folder**: `Azure Cost Monitoring` (create new)
- **Evaluation group**: `cost-alerts` (create new, interval: 5m)
- **Pending period**: 5 minutes

**Section 3 - Add details for your alert**:
- **Summary**: `Monthly budget exceeded`
- **Description**: `Current spending is {{ $values.B.Value }}% of $120,000 monthly budget (${{ humanize $values.A.Value }})`
- **Runbook URL**: (optional)
- **Dashboard UID**: `azure-cost-trends`
- **Panel ID**: `100` (Budget Status panel)

**Labels**:
- `severity`: `critical`
- `alertname`: `BudgetExceeded`
- `subscription`: `518f04e9-2b37-457e-b852-8f058cb3f160`

3. Click "**Save rule and exit**"

---

**Alert 2: Service Cost Spike**

1. **New alert rule** → `Service Cost Spike Alert`

**Query A**:
```sql
WITH current_month AS (
    SELECT service_name, SUM(cost) as current_cost
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
    GROUP BY service_name
),
previous_month AS (
    SELECT service_name, SUM(cost) as previous_cost
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
      AND date < DATE_TRUNC('month', CURRENT_DATE)
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
    GROUP BY service_name
)
SELECT 
    NOW() as time,
    COALESCE(c.service_name, p.service_name) as metric,
    ROUND(((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / 
           NULLIF(p.previous_cost, 0) * 100)::numeric, 2) as value
FROM current_month c
FULL OUTER JOIN previous_month p ON c.service_name = p.service_name
WHERE ((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / 
       NULLIF(p.previous_cost, 0) * 100) > 30
ORDER BY value DESC;
```

**Condition**: `IS ABOVE 40`
- **Summary**: `Service cost spike detected`
- **Description**: `{{ $labels.metric }} costs increased by {{ $values.B.Value }}% this month`
- **Labels**: 
  - `severity`: `warning`
  - `alertname`: `ServiceCostSpike`

---

### 🎯 Demo Script for Presentation

**1. Show Dashboard (3 mins)**
- Open: `http://localhost:3000/d/azure-cost-trends/`
- Highlight:
  - Current spend: $124,543.37
  - Budget: $120,000
  - Budget Status: **Over Budget** (red indicator)
  - Budget Utilization: 103.79%
  - MoM Change: -1.60% (slight decrease)

**2. Show Alert Configuration (4 mins)**
- Navigate: **Alerting** → **Alert rules**
- Show:
  - Budget Exceeded Alert (threshold: 105%)
  - Service Cost Spike Alert (threshold: 40%)
- Explain evaluation intervals (5 minutes)
- Show alert state (Normal, Pending, Firing, Resolved)

**3. Show Teams Integration (3 mins)**
- Navigate: **Alerting** → **Contact points**
- Show Teams webhook configuration
- Explain:
  - Webhook URL (masked for security)
  - Message template with variables
  - Test button functionality

**4. Show Service Spikes (3 mins)**
- Navigate back to dashboard
- Point to "Month-over-Month Change by Service" table
- Highlight:
  - **Load Balancer: +45.58%** (approaching 50% threshold)
  - **Azure Functions: +28.63%**
  - **Key Vault: +27.04%**
- Explain: "These would trigger alerts if thresholds lowered to 30%"

**5. Trigger Test Alert (5 mins)**
- Temporarily change Budget Exceeded threshold from 105% to 100%
- Wait 1 minute for evaluation
- Navigate: **Alerting** → **Alert rules**
- Show alert status change to **Firing**
- Show Teams notification (if webhook configured)
- Reset threshold back to 105%

**6. Show Alert History (2 mins)**
- Navigate: **Alerting** → **History**
- Show previous alert instances
- Explain state transitions (Normal → Pending → Firing → Resolved)

---

### 🧪 Test Commands

**Check current alert trigger status:**

```powershell
# Budget check
docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "
WITH current_spend AS (SELECT SUM(cost) as total FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE) AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'), budget AS (SELECT SUM(budget_amount) as total FROM cost_budgets WHERE is_active = true AND time_period = 'monthly')
SELECT ROUND((c.total / NULLIF(b.total, 0) * 100)::numeric, 2) as budget_percent FROM current_spend c, budget b;
"
# Result: 103.79

# Service spikes check
docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "
WITH current_month AS (SELECT service_name, SUM(cost) as current_cost FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE) AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160' GROUP BY service_name), previous_month AS (SELECT service_name, SUM(cost) as previous_cost FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND date < DATE_TRUNC('month', CURRENT_DATE) AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160' GROUP BY service_name)
SELECT COALESCE(c.service_name, p.service_name) as service, ROUND(((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / NULLIF(p.previous_cost, 0) * 100)::numeric, 2) as spike FROM current_month c FULL OUTER JOIN previous_month p ON c.service_name = p.service_name WHERE ((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / NULLIF(p.previous_cost, 0) * 100) > 20 ORDER BY spike DESC;
"
# Result: Load Balancer 45.58%, Azure Functions 28.63%, etc.
```

---

### 📱 Teams Alert Example

When alert fires, Teams will receive:

```
🚨 Azure Cost Alert: BudgetExceeded

Status: Firing
Severity: critical
Details: Current spending is 103.79% of $120,000 monthly budget ($124,543.37)

Triggered: 2025-11-25T10:30:00Z

[View Dashboard]
```

---

### ✅ Pre-Demo Checklist

- [ ] Grafana running: `docker ps | grep grafana`
- [ ] Database accessible: `docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "SELECT COUNT(*) FROM cost_records;"`
- [ ] Dashboard loads: Open `http://localhost:3000/d/azure-cost-trends/`
- [ ] Teams webhook URL ready (if demoing actual notifications)
- [ ] Alert rules created in Grafana
- [ ] Contact point configured
- [ ] Notification policy configured
- [ ] Test alert threshold noted (change 105% → 100% for demo)

---

### 🔍 Troubleshooting

**MoM panel showing "No data":**
- Check subscription variable is selected
- Verify data exists: `SELECT COUNT(*) FROM cost_records WHERE subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160';`
- Refresh dashboard or restart Grafana: `docker restart azure-cost-grafana`

**Alert not firing:**
- Check evaluation interval (5 minutes default)
- Verify query returns data
- Check alert state in Alert rules page
- Review evaluation logs

**Teams notification not received:**
- Verify webhook URL is correct
- Test webhook with "Send test" button
- Check Teams channel permissions
- Verify notification policy routing

---

This setup provides a complete alerting system for your Azure Cost Monitoring demo! 🎉
