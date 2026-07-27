# 🔐 Azure Integration Setup Guide

## Prerequisites

Before integrating real Azure data, you need:

1. ✅ **Azure Subscription(s)** - Active Azure subscriptions you want to monitor
2. ✅ **Azure CLI** OR **Service Principal** - For authentication
3. ✅ **Cost Management API Access** - Reader permissions on subscriptions

---

## 🚀 Quick Start (3 Methods)

### Method 1: Azure CLI (Easiest - Recommended for Testing)

#### Step 1: Install Azure CLI
```powershell
# Download and install from: https://aka.ms/installazurecliwindows
# Or use winget:
winget install Microsoft.AzureCLI
```

#### Step 2: Login to Azure
```powershell
az login
```

#### Step 3: Verify Access
```powershell
# List your subscriptions
az account list --output table

# Set default subscription (optional)
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

#### Step 4: Test the Collector
```powershell
# From project root
python src/monitoring/azure_cost_collector.py
```

✅ **That's it!** The collector will use your Azure CLI credentials automatically.

---

### Method 2: Service Principal (Recommended for Production)

#### Step 1: Create Service Principal

```powershell
# Login to Azure
az login

# Create service principal with Reader role
$sp = az ad sp create-for-rbac --name "CostMonitoringApp" --role "Cost Management Reader" --scopes /subscriptions/YOUR_SUBSCRIPTION_ID | ConvertFrom-Json

# Save the output - you'll need these values:
# {
#   "appId": "xxxx-xxxx-xxxx-xxxx",       # This is CLIENT_ID
#   "password": "xxxx-xxxx-xxxx",          # This is CLIENT_SECRET
#   "tenant": "xxxx-xxxx-xxxx-xxxx"        # This is TENANT_ID
# }
```

#### Step 2: Grant Permissions

If you have multiple subscriptions, grant access to each:

```powershell
# For each subscription
az role assignment create `
  --assignee $sp.appId `
  --role "Cost Management Reader" `
  --scope "/subscriptions/YOUR_SUBSCRIPTION_ID"
```

#### Step 3: Set Environment Variables

Create a `.env` file in the project root:

```bash
# .env file
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# Optional: Specific subscriptions to monitor (comma-separated)
AZURE_SUBSCRIPTION_IDS=sub-id-1,sub-id-2,sub-id-3
```

**⚠️ IMPORTANT: Add `.env` to `.gitignore` to keep credentials safe!**

#### Step 4: Update docker-compose.yml

Add environment variables to the API service:

```yaml
api:
  build:
    context: .
    dockerfile: Dockerfile
  environment:
    - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/azure_cost_dev
    - AZURE_TENANT_ID=${AZURE_TENANT_ID}
    - AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
    - AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET}
    - AZURE_SUBSCRIPTION_IDS=${AZURE_SUBSCRIPTION_IDS}
  env_file:
    - .env
```

---

### Method 3: Managed Identity (For Production Deployment in Azure)

If deploying to Azure (AKS, Container Apps, VM), use Managed Identity:

#### Step 1: Enable Managed Identity
```powershell
# For Azure Container App
az containerapp identity assign --name cost-monitoring --resource-group myRG

# For AKS
az aks update --resource-group myRG --name myAKS --enable-managed-identity
```

#### Step 2: Grant Permissions
```powershell
# Get managed identity principal ID
$principalId = az containerapp identity show --name cost-monitoring --resource-group myRG --query principalId -o tsv

# Grant Cost Management Reader role
az role assignment create `
  --assignee $principalId `
  --role "Cost Management Reader" `
  --scope "/subscriptions/YOUR_SUBSCRIPTION_ID"
```

#### Step 3: No Credentials Needed!
The code will automatically use Managed Identity when deployed in Azure.

---

## 📦 Required Azure Packages

Add these to `requirements.txt`:

```txt
# Azure SDK packages for cost data collection
azure-identity==1.15.0
azure-mgmt-costmanagement==4.0.0
azure-mgmt-consumption==10.0.0
azure-mgmt-resource==23.0.0
azure-core==1.29.0

# For .env file support
python-dotenv==1.0.0
```

Install them:

```powershell
pip install azure-identity azure-mgmt-costmanagement azure-mgmt-consumption azure-mgmt-resource python-dotenv
```

---

## 🎯 What Data Can You Collect?

### 1. **Subscription List**
- All accessible subscriptions
- Subscription names and IDs
- Tenant information

### 2. **Cost Data**
- Daily/Monthly/Custom time ranges
- Costs by Service (VM, Storage, SQL, etc.)
- Costs by Resource Group
- Costs by Individual Resource
- Historical trends

### 3. **Service-Level Costs**
- Current month costs by Azure service
- Previous month comparisons
- Service-wise breakdowns

### 4. **Resource-Level Costs**
- Individual resource costs
- Resource tags and metadata
- Resource group allocation

### 5. **Cost Forecasts**
- 30/60/90 day forecasts
- Trend-based predictions
- Budget alerts

---

## 🔧 Configuration for Multiple Subscriptions

### Option A: Monitor All Subscriptions (Default)
```python
from azure_cost_collector import AzureCostCollector

collector = AzureCostCollector()
subscriptions = collector.get_subscriptions()

for sub in subscriptions:
    print(f"Collecting data for: {sub['display_name']}")
    costs = collector.get_current_month_costs_by_service(sub['subscription_id'])
```

### Option B: Monitor Specific Subscriptions
```python
# Set in .env file
AZURE_SUBSCRIPTION_IDS=sub-id-1,sub-id-2,sub-id-3

# Or in code
target_subscription_ids = [
    "12345678-1234-1234-1234-123456789012",
    "87654321-4321-4321-4321-210987654321"
]

for sub_id in target_subscription_ids:
    costs = collector.get_current_month_costs_by_service(sub_id)
```

---

## 🔄 Data Collection Schedule

### Automated Collection Script

Create `scripts/collect_azure_costs.py`:

```python
import os
from datetime import datetime
from src.monitoring.azure_cost_collector import AzureCostCollector
from src.monitoring.storage.database import Database

def collect_and_store_costs():
    """Collect Azure costs and store in database"""
    collector = AzureCostCollector()
    db = Database()
    
    # Get all subscriptions
    subscriptions = collector.get_subscriptions()
    print(f"Found {len(subscriptions)} subscriptions")
    
    for sub in subscriptions:
        sub_id = sub['subscription_id']
        sub_name = sub['display_name']
        
        print(f"\nProcessing: {sub_name}")
        
        # Get current month costs by service
        service_costs = collector.get_current_month_costs_by_service(sub_id)
        
        # Store in database
        for service in service_costs:
            db.insert_cost_record({
                'subscription_id': sub_id,
                'subscription_name': sub_name,
                'service_name': service['service_name'],
                'current_cost': service['current_cost'],
                'date': datetime.now(),
                'currency': 'USD'
            })
        
        print(f"  ✅ Stored {len(service_costs)} service costs")
    
    print("\n✅ Collection completed!")

if __name__ == "__main__":
    collect_and_store_costs()
```

### Schedule with Cron (Linux/Mac) or Task Scheduler (Windows)

**Windows Task Scheduler:**
```powershell
# Run every 6 hours
schtasks /create /tn "AzureCostCollection" /tr "python C:\path\to\collect_azure_costs.py" /sc hourly /mo 6
```

**Linux Cron:**
```bash
# Run every 6 hours
0 */6 * * * /usr/bin/python3 /path/to/collect_azure_costs.py
```

---

## 🧪 Testing the Integration

### Test Script
```powershell
# Test connectivity
python src/monitoring/azure_cost_collector.py

# Expected output:
# ✅ Found 3 subscriptions
# ✅ Retrieved costs for 12 services
# Top 5 services by cost:
#    1. Microsoft.Compute: $245.50
#    2. Microsoft.Sql: $189.30
#    3. Microsoft.Storage: $98.45
```

### Verify Data in Database
```powershell
docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "SELECT subscription_name, service_name, current_cost FROM azure_costs ORDER BY current_cost DESC LIMIT 10;"
```

---

## 📊 Update Grafana Dashboard

Once you have real data, update the Grafana queries:

### Query Example (replace static data):
```sql
-- Old query (static data)
SELECT service_name, 913.50 as cost FROM dummy_table

-- New query (real Azure data)
SELECT 
  service_name,
  SUM(current_cost) as cost,
  subscription_name
FROM azure_costs
WHERE date >= NOW() - INTERVAL '30 days'
GROUP BY service_name, subscription_name
ORDER BY cost DESC
LIMIT 20;
```

---

## 🔐 Security Best Practices

1. ✅ **Never commit credentials** - Use .env files and add to .gitignore
2. ✅ **Use Service Principal** - Don't use personal accounts in production
3. ✅ **Least Privilege** - Only grant "Cost Management Reader" role
4. ✅ **Rotate Secrets** - Change service principal secrets regularly
5. ✅ **Use Key Vault** - Store secrets in Azure Key Vault for production
6. ✅ **Enable Logging** - Monitor API access and usage

---

## 🎯 Next Steps

1. ✅ Choose authentication method (CLI or Service Principal)
2. ✅ Set up credentials
3. ✅ Install Azure packages: `pip install -r requirements.txt`
4. ✅ Test the collector: `python src/monitoring/azure_cost_collector.py`
5. ✅ Create data collection script
6. ✅ Schedule automated collection
7. ✅ Update database schema if needed
8. ✅ Modify Grafana dashboards to use real data
9. ✅ Generate AI recommendations based on real costs

---

## 📞 Troubleshooting

### Error: "No subscriptions found"
**Solution:** Check your Azure permissions. You need at least "Reader" role on subscriptions.

### Error: "Authentication failed"
**Solution:** 
- For CLI: Run `az login` again
- For Service Principal: Verify TENANT_ID, CLIENT_ID, CLIENT_SECRET

### Error: "Cost Management API not available"
**Solution:** Enable Cost Management API in Azure portal and ensure "Cost Management Reader" role is assigned.

### Error: "Subscription not registered"
**Solution:** Register Microsoft.CostManagement resource provider:
```powershell
az provider register --namespace Microsoft.CostManagement
```

---

## 📚 Additional Resources

- [Azure Cost Management API Docs](https://learn.microsoft.com/en-us/rest/api/cost-management/)
- [Azure SDK for Python](https://learn.microsoft.com/en-us/azure/developer/python/sdk/azure-sdk-overview)
- [Service Principal Creation Guide](https://learn.microsoft.com/en-us/azure/active-directory/develop/howto-create-service-principal-portal)
- [Azure CLI Installation](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)

---

**Ready to collect real Azure cost data! 🚀**
