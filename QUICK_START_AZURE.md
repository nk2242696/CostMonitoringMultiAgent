# 🚀 Quick Start - Azure Integration

## Step-by-Step Guide to Connect Real Azure Data

### ✅ Step 1: Install Azure Packages

```powershell
# Install required Azure SDK packages
pip install azure-identity azure-mgmt-costmanagement azure-mgmt-consumption azure-mgmt-resource python-dotenv
```

### ✅ Step 2: Choose Authentication Method

#### **Option A: Azure CLI (Easiest - 2 minutes)**

1. Install Azure CLI:
   - Download from: https://aka.ms/installazurecliwindows
   - Or: `winget install Microsoft.AzureCLI`

2. Login:
   ```powershell
   az login
   ```

3. Verify:
   ```powershell
   az account list --output table
   ```

4. **Done!** The code will use your Azure CLI credentials automatically.

---

#### **Option B: Service Principal (Production - 5 minutes)**

1. **Create Service Principal:**
   ```powershell
   az login
   
   # Create SP with Cost Management Reader role
   $sp = az ad sp create-for-rbac `
     --name "CostMonitoringApp" `
     --role "Cost Management Reader" `
     --scopes /subscriptions/YOUR_SUBSCRIPTION_ID `
     | ConvertFrom-Json
   
   # Save these values:
   Write-Host "AZURE_TENANT_ID=$($sp.tenant)"
   Write-Host "AZURE_CLIENT_ID=$($sp.appId)"
   Write-Host "AZURE_CLIENT_SECRET=$($sp.password)"
   ```

2. **For Multiple Subscriptions:**
   ```powershell
   # Grant access to each subscription
   $subscriptions = @(
       "subscription-id-1",
       "subscription-id-2",
       "subscription-id-3"
   )
   
   foreach ($subId in $subscriptions) {
       az role assignment create `
         --assignee $sp.appId `
         --role "Cost Management Reader" `
         --scope "/subscriptions/$subId"
       
       Write-Host "✅ Granted access to subscription: $subId"
   }
   ```

3. **Create .env file** in project root:
   ```bash
   # .env
   AZURE_TENANT_ID=your-tenant-id-here
   AZURE_CLIENT_ID=your-client-id-here
   AZURE_CLIENT_SECRET=your-client-secret-here
   
   # Optional: Specific subscriptions (comma-separated)
   AZURE_SUBSCRIPTION_IDS=sub-id-1,sub-id-2,sub-id-3
   ```

4. **⚠️ Add to .gitignore:**
   ```powershell
   # Add this line to .gitignore
   echo ".env" >> .gitignore
   ```

---

### ✅ Step 3: Test Azure Connection

```powershell
# Test the Azure cost collector
python src/monitoring/azure_cost_collector.py
```

**Expected Output:**
```
======================================================================
Azure Cost Data Collector - Test Run
======================================================================

1. Fetching subscriptions...
✅ Found 3 subscriptions:
   - Production Subscription (12345678-1234-1234-1234-123456789012)
   - Development Subscription (87654321-4321-4321-4321-210987654321)
   - Testing Subscription (11111111-2222-3333-4444-555555555555)

2. Using subscription: Production Subscription

3. Fetching current month costs by service...
✅ Retrieved costs for 8 services

Top 5 services by cost:
   1. Microsoft.Compute: $1,245.50
   2. Microsoft.Sql: $843.20
   3. Microsoft.Storage: $456.78
   4. Microsoft.Web: $234.90
   5. Microsoft.Network: $189.45

4. Fetching last 7 days cost data...
✅ Retrieved 56 cost records

======================================================================
✅ Test completed successfully!
======================================================================
```

---

### ✅ Step 4: Collect Real Azure Cost Data

```powershell
# Run the data collection script
python scripts/collect_azure_costs.py
```

This will:
- ✅ Fetch all accessible subscriptions
- ✅ Collect current month costs by service
- ✅ Get last 7 days of daily costs
- ✅ Retrieve top 50 resource-level costs
- ✅ Store everything in PostgreSQL database

**Expected Output:**
```
======================================================================
🚀 Azure Cost Data Collection
======================================================================

🔐 Initializing Azure Cost Collector...
📋 Fetching accessible subscriptions...
✅ Found 3 accessible subscriptions
📌 Processing all 3 subscriptions

📊 Subscriptions to process:
   1. Production Subscription (12345678-...)
   2. Development Subscription (87654321-...)
   3. Testing Subscription (11111111-...)

======================================================================
Processing: Production Subscription
Subscription ID: 12345678-1234-1234-1234-123456789012
======================================================================
📊 Fetching current month costs by service...
✅ Stored 8 service cost records
📊 Fetching last 7 days daily costs...
✅ Stored 56 daily cost records
📊 Fetching resource-level costs...
✅ Stored 50 resource cost records

💰 Summary for Production Subscription:
   - Current month total: $3,234.56
   - Services tracked: 8
   - Resources tracked: 50
   - Total records inserted: 114

======================================================================
📈 COLLECTION SUMMARY
======================================================================
✅ Successful: 3/3 subscriptions
📊 Total records inserted: 342

📋 Sample data from database:

Subscription                   Service                              Cost    Records
------------------------------------------------------------------------------------------
Production Subscription        Microsoft.Compute           $1,245.50         15
Production Subscription        Microsoft.Sql                 $843.20         12
Development Subscription       Microsoft.Compute             $567.89         10
...

======================================================================
✅ Collection completed successfully!
======================================================================
```

---

### ✅ Step 5: Generate AI Recommendations (with Real Data)

```powershell
# Update AI engine to use real Azure data
python scripts/generate_ai_recommendations.py
```

---

### ✅ Step 6: View in Grafana Dashboard

1. **Start Docker containers:**
   ```powershell
   docker-compose up -d
   ```

2. **Open Grafana:**
   - URL: http://localhost:3000
   - Login: admin / admin123

3. **Navigate to:**
   - Dashboards → Azure AI Cost Recommendations

4. **You'll see:**
   - ✅ Real cost data from your Azure subscriptions
   - ✅ AI recommendations based on actual spending
   - ✅ Service-wise breakdown
   - ✅ Potential savings identified

---

## 🔄 Automated Collection (Optional)

### Schedule Regular Data Collection

**Option 1: Windows Task Scheduler**
```powershell
# Run every 6 hours
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\CostMonitoring\scripts\collect_azure_costs.py"
$trigger = New-ScheduledTaskTrigger -Daily -At 12am -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 1)
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "AzureCostCollection" -Description "Collect Azure cost data every 6 hours"
```

**Option 2: Docker Container with Scheduler**
Add to `docker-compose.yml`:
```yaml
scheduler:
  build:
    context: .
    dockerfile: Dockerfile
  command: python scripts/collect_azure_costs.py
  environment:
    - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/azure_cost_dev
  env_file:
    - .env
  depends_on:
    - postgres
  restart: unless-stopped
```

---

## 🎯 What You Get

### Real Azure Data:
- ✅ **Actual costs** from your subscriptions
- ✅ **Service-level breakdown** (Compute, SQL, Storage, etc.)
- ✅ **Resource-level details** (individual VMs, databases, etc.)
- ✅ **Daily trends** and patterns
- ✅ **Multi-subscription support**

### AI Recommendations:
- ✅ **Based on real spending patterns**
- ✅ **Specific to your resources**
- ✅ **Actionable with cost estimates**
- ✅ **Prioritized** (High/Medium/Low)

### Dashboards:
- ✅ **Live data visualization**
- ✅ **Historical trends**
- ✅ **Budget tracking**
- ✅ **Savings opportunities**

---

## 📊 Example Dashboard Queries (Updated for Real Data)

### Query 1: Current Month Costs by Service
```sql
SELECT 
    service_name,
    SUM(cost) as total_cost,
    COUNT(DISTINCT subscription_id) as num_subscriptions
FROM azure_costs
WHERE period_type = 'current_month'
GROUP BY service_name
ORDER BY total_cost DESC
LIMIT 10;
```

### Query 2: Daily Cost Trend
```sql
SELECT 
    date::date as day,
    SUM(cost) as daily_cost
FROM azure_costs
WHERE period_type = 'daily'
    AND date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY day
ORDER BY day;
```

### Query 3: Cost by Subscription
```sql
SELECT 
    subscription_name,
    SUM(cost) as total_cost
FROM azure_costs
WHERE period_type = 'current_month'
GROUP BY subscription_name
ORDER BY total_cost DESC;
```

---

## 🔐 Security Checklist

- [ ] `.env` file created with credentials
- [ ] `.env` added to `.gitignore`
- [ ] Service Principal has least privilege (Cost Management Reader only)
- [ ] Credentials NOT committed to git
- [ ] Database password changed from default
- [ ] Grafana admin password changed

---

## 🆘 Troubleshooting

### "No subscriptions found"
✅ **Fix:** Ensure you have at least "Reader" role on subscriptions
```powershell
az role assignment list --assignee YOUR_EMAIL --output table
```

### "Authentication failed"
✅ **Fix:** 
- For CLI: Run `az login` again
- For Service Principal: Verify credentials in `.env`

### "Cost Management API not available"
✅ **Fix:** Register resource provider
```powershell
az provider register --namespace Microsoft.CostManagement
az provider show --namespace Microsoft.CostManagement
```

### "No data in Grafana"
✅ **Fix:** 
1. Verify data collected: `python scripts/collect_azure_costs.py`
2. Check database: `docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "SELECT COUNT(*) FROM azure_costs;"`
3. Restart Grafana: `docker restart azure-cost-grafana`

---

## 📞 Next Steps

1. ✅ Complete Steps 1-6 above
2. ✅ Schedule automated collection
3. ✅ Customize Grafana dashboards
4. ✅ Set up alerts for budget overruns
5. ✅ Share dashboards with your team

---

**🎉 You're now monitoring REAL Azure costs with AI-powered recommendations!**
