"""
Setup Grafana alerts for Azure Cost Monitoring.
Creates alert rules for:
1. Budget exceeded
2. High month-over-month increase
3. Anomalous service cost spike
"""

# Alert Rule Configuration for Grafana

ALERT_RULES = """
# Grafana Alert Rules for Azure Cost Monitoring

## Alert 1: Budget Exceeded
**Condition**: Current month spending exceeds budget by more than 5%
**Severity**: Critical
**Trigger**: When budget utilization > 105%

## Alert 2: High MoM Cost Increase
**Condition**: Month-over-month cost increase > 15%
**Severity**: Warning
**Trigger**: When MoM change > 15%

## Alert 3: Service Cost Spike
**Condition**: Any service cost increases by > 50% in a single month
**Severity**: Warning
**Trigger**: When service MoM > 50%

## Alert 4: Approaching Budget Limit
**Condition**: Current spending is 90-100% of budget
**Severity**: Warning
**Trigger**: When budget utilization between 90% and 100%

---

# Microsoft Teams Webhook Setup

To send alerts to Microsoft Teams:

1. **Create Incoming Webhook in Teams**:
   - Open your Teams channel
   - Click "..." → "Connectors"
   - Search for "Incoming Webhook"
   - Click "Configure"
   - Name: "Azure Cost Alerts"
   - Copy the webhook URL

2. **Configure in Grafana**:
   - Go to: Alerting → Contact points
   - Click "New contact point"
   - Name: "Teams - Cost Alerts"
   - Integration: "Webhook" (or use Teams if available)
   - URL: Paste your Teams webhook URL
   - HTTP Method: POST

3. **Webhook Payload Template** (if using generic webhook):
```json
{
  "@type": "MessageCard",
  "@context": "http://schema.org/extensions",
  "themeColor": "{{ if eq .Status \"firing\" }}d63333{{ else }}2dc72d{{ end }}",
  "summary": "{{ .CommonAnnotations.summary }}",
  "title": "🚨 Azure Cost Alert: {{ .CommonLabels.alertname }}",
  "sections": [{
    "activityTitle": "{{ .CommonAnnotations.description }}",
    "facts": [{
      "name": "Status:",
      "value": "{{ .Status }}"
    }, {
      "name": "Severity:",
      "value": "{{ .CommonLabels.severity }}"
    }, {
      "name": "Subscription:",
      "value": "{{ .CommonLabels.subscription }}"
    }, {
      "name": "Triggered:",
      "value": "{{ .StartsAt }}"
    }],
    "markdown": true
  }],
  "potentialAction": [{
    "@type": "OpenUri",
    "name": "View Dashboard",
    "targets": [{
      "os": "default",
      "uri": "http://localhost:3000/d/azure-cost-trends/"
    }]
  }]
}
```

---

# SQL Queries for Alert Conditions

## Query 1: Budget Exceeded Check
```sql
WITH current_spend AS (
    SELECT SUM(cost) as total
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
),
budget AS (
    SELECT SUM(budget_amount) as total
    FROM cost_budgets
    WHERE is_active = true AND time_period = 'monthly'
)
SELECT 
    ROUND((c.total / NULLIF(b.total, 0) * 100)::numeric, 2) as budget_percent,
    CASE WHEN c.total > b.total THEN 1 ELSE 0 END as is_over_budget
FROM current_spend c, budget b;
```

## Query 2: MoM Increase Check
```sql
WITH current_month AS (
    SELECT SUM(cost) as total
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
),
previous_month AS (
    SELECT SUM(cost) as total
    FROM cost_records
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
      AND date < DATE_TRUNC('month', CURRENT_DATE)
      AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'
)
SELECT 
    ROUND(((c.total - p.total) / NULLIF(p.total, 0) * 100)::numeric, 2) as mom_percent
FROM current_month c, previous_month p;
```

## Query 3: Service Cost Spike Check
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
    COALESCE(c.service_name, p.service_name) as service,
    ROUND(((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / NULLIF(p.previous_cost, 0) * 100)::numeric, 2) as spike_percent
FROM current_month c
FULL OUTER JOIN previous_month p ON c.service_name = p.service_name
WHERE ((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / NULLIF(p.previous_cost, 0) * 100) > 50
ORDER BY spike_percent DESC;
```

---

# Step-by-Step Alert Setup in Grafana

1. **Navigate to Alerting**
   - Click "Alerting" in left menu
   - Click "Alert rules"
   - Click "New alert rule"

2. **Configure Alert Rule - Budget Exceeded**
   - Rule name: "Budget Exceeded Alert"
   - Folder: "Azure Cost Monitoring"
   - Query A: Use Budget Exceeded Check query above
   - Condition: `WHEN last() OF query(A, budget_percent, 5m) IS ABOVE 105`
   - Evaluation interval: 5 minutes
   - Pending period: 5 minutes
   - Annotations:
     - Summary: "Monthly budget exceeded"
     - Description: "Current spending is {{ $values.A.Value }}% of monthly budget"
   - Labels:
     - severity: "critical"
     - alertname: "BudgetExceeded"
   - Save

3. **Configure Alert Rule - MoM Increase**
   - Rule name: "High MoM Cost Increase"
   - Query A: Use MoM Increase Check query
   - Condition: `WHEN last() OF query(A, mom_percent, 5m) IS ABOVE 15`
   - Annotations:
     - Summary: "High month-over-month cost increase detected"
     - Description: "Costs increased by {{ $values.A.Value }}% compared to last month"
   - Labels:
     - severity: "warning"
     - alertname: "HighMoMIncrease"

4. **Configure Alert Rule - Service Spike**
   - Rule name: "Service Cost Spike Alert"
   - Query A: Use Service Cost Spike Check query
   - Condition: `WHEN last() OF query(A, spike_percent, 5m) IS ABOVE 50`
   - Annotations:
     - Summary: "Service cost spike detected"
     - Description: "{{ $labels.service }} costs spiked by {{ $values.A.Value }}%"
   - Labels:
     - severity: "warning"
     - alertname: "ServiceCostSpike"

5. **Create Notification Policy**
   - Go to: Alerting → Notification policies
   - Click "New policy"
   - Match labels: `severity=critical` or `severity=warning`
   - Contact point: "Teams - Cost Alerts"
   - Group by: `alertname`
   - Save

---

# Testing Alerts

Run these commands to test if alerts would trigger:

```bash
# Check if budget alert would trigger
docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "
WITH current_spend AS (SELECT SUM(cost) as total FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE) AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'), budget AS (SELECT SUM(budget_amount) as total FROM cost_budgets WHERE is_active = true AND time_period = 'monthly')
SELECT ROUND((c.total / NULLIF(b.total, 0) * 100)::numeric, 2) as budget_percent FROM current_spend c, budget b;
"

# Result: 103.79% - WOULD TRIGGER BUDGET ALERT (>105% threshold can be adjusted)

# Check MoM increase
docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "
WITH current_month AS (SELECT SUM(cost) as total FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE) AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160'), previous_month AS (SELECT SUM(cost) as total FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND date < DATE_TRUNC('month', CURRENT_DATE) AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160')
SELECT ROUND(((c.total - p.total) / NULLIF(p.total, 0) * 100)::numeric, 2) as mom_percent FROM current_month c, previous_month p;
"

# Result: -1.60% - Would NOT trigger (< 15% increase threshold)

# Check for service spikes
docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "
WITH current_month AS (SELECT service_name, SUM(cost) as current_cost FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE) AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160' GROUP BY service_name), previous_month AS (SELECT service_name, SUM(cost) as previous_cost FROM cost_records WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND date < DATE_TRUNC('month', CURRENT_DATE) AND subscription_id = '518f04e9-2b37-457e-b852-8f058cb3f160' GROUP BY service_name)
SELECT COALESCE(c.service_name, p.service_name) as service, ROUND(((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / NULLIF(p.previous_cost, 0) * 100)::numeric, 2) as spike_percent FROM current_month c FULL OUTER JOIN previous_month p ON c.service_name = p.service_name WHERE ((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / NULLIF(p.previous_cost, 0) * 100) > 50 ORDER BY spike_percent DESC;
"

# If any service has > 50% increase, would trigger
```

---

# Demo Script for Alerts

1. **Show Alert Configuration in Grafana**
   - Navigate to Alerting → Alert rules
   - Show the 3 configured rules
   - Explain thresholds and conditions

2. **Show Teams Integration**
   - Navigate to Alerting → Contact points
   - Show Teams webhook configuration
   - Explain notification routing

3. **Trigger a Test Alert**
   - Temporarily lower budget threshold to 100%
   - Show alert firing in Grafana
   - Show notification in Teams channel
   - Reset threshold back

4. **Show Alert History**
   - Navigate to Alerting → Alert history
   - Show previous fired alerts
   - Explain resolution workflow

5. **Dashboard Alert Annotations**
   - Show how alerts appear as annotations on dashboard panels
   - Explain correlation with cost spikes
"""

print(ALERT_RULES)

# Save configuration
with open('ALERT_SETUP_GUIDE.md', 'w', encoding='utf-8') as f:
    f.write(ALERT_RULES)

print("\n✅ Alert setup guide created: ALERT_SETUP_GUIDE.md")
print("\n📋 Quick Setup Checklist:")
print("   1. ☐ Create Teams incoming webhook")
print("   2. ☐ Add webhook to Grafana Contact Points")
print("   3. ☐ Create 3 alert rules (Budget, MoM, Service Spike)")
print("   4. ☐ Configure notification policy")
print("   5. ☐ Test alerts with threshold adjustments")
print("\n🎯 Current Status:")
print("   - Budget: 103.79% (would trigger at >105%)")
print("   - MoM: -1.60% (would trigger at >15%)")
print("   - Service Spikes: Check with query above")
