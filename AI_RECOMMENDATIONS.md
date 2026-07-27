# AI Cost Recommendation Engine - Official Azure Integration

## Overview

The **Enhanced AI Cost Recommendation Engine** integrates with **official Microsoft Azure services** to provide accurate, authoritative cost optimization recommendations based on Azure's own best practices and documentation.

## 🔷 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│         AI Cost Recommendation Engine                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Azure Advisor API                                        │
│     └─ Official Microsoft recommendations from your          │
│        actual Azure subscription                             │
│                                                              │
│  2. Azure Well-Architected Framework (WAF)                   │
│     └─ All 9 cost optimization design principles             │
│        from Microsoft's official framework                   │
│                                                              │
│  3. Azure Pricing API                                        │
│     └─ Real-time pricing data for accurate                   │
│        savings calculations                                  │
│                                                              │
│  4. Azure OpenAI (Optional)                                  │
│     └─ Advanced AI-powered analysis using GPT-4              │
│                                                              │
│  5. Rule-based Engine (Fallback)                             │
│     └─ Built-in best practices for offline use               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## ✨ Features

### 1. Azure Advisor Integration

**Official Microsoft recommendations from your subscription**

- ✅ Fetches real recommendations using Azure Advisor API
- ✅ Provides impact level (High, Medium, Low)
- ✅ Includes potential savings in USD
- ✅ Links to Azure portal for implementation
- ✅ Supports filtering by impact level

**Official Documentation:**
- https://learn.microsoft.com/en-us/azure/advisor/
- https://learn.microsoft.com/en-us/azure/advisor/advisor-cost-recommendations

### 2. Azure Well-Architected Framework

**All 9 cost optimization principles from Microsoft**

1. **Develop cost model and forecasts** - Establish cost measurement
2. **Design with cost optimization in mind** - Make cost-effective choices
3. **Monitor and optimize continuously** - Track spending patterns
4. **Establish budgets and alerts** - Set spending limits
5. **Implement cost governance** - Control cloud spending
6. **Optimize resource efficiency** - Right-size and eliminate waste
7. **Use cost-effective pricing models** - Leverage reservations and spots
8. **Automate cost operations** - Reduce operational costs
9. **Continuously optimize costs** - Regular review cycles

**Official Documentation:**
- https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/
- https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/principles

### 3. Azure Pricing API

**Real-time pricing for accurate savings calculations**

- ✅ Live pricing data from Azure Retail Prices API
- ✅ Calculate exact reservation savings (1-year, 3-year)
- ✅ Spot VM savings estimates (up to 90%)
- ✅ Storage tier comparison (Hot vs Cool vs Archive)
- ✅ SQL Database pricing models
- ✅ No authentication required

**Official Documentation:**
- https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices

### 4. Azure OpenAI (Optional)

**Advanced AI-powered recommendations**

- Uses GPT-4 for sophisticated cost analysis
- Contextual recommendations based on usage patterns
- Requires Azure OpenAI resource

### 5. Rule-based Engine

**Built-in best practices for offline use**

- Works without Azure subscription
- Based on industry-standard optimization patterns
- Fallback when APIs are unavailable

## 🚀 Quick Start

### Prerequisites

```bash
# Install required packages
pip install azure-mgmt-advisor azure-mgmt-resourcegraph azure-identity azure-mgmt-costmanagement
```

### Authentication Setup

#### Option 1: Azure CLI (Recommended for Development)

```bash
# Install Azure CLI
# Download from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

# Login to Azure
az login

# Set your subscription
az account set --subscription "your-subscription-id"

# Get your subscription ID
az account show --query id --output tsv
```

#### Option 2: Service Principal (Production)

```bash
# Create Service Principal with Reader role
az ad sp create-for-rbac \
  --name "CostMonitoringSP" \
  --role "Reader" \
  --scopes /subscriptions/{subscription-id}

# Save the output:
# - appId -> AZURE_CLIENT_ID
# - password -> AZURE_CLIENT_SECRET
# - tenant -> AZURE_TENANT_ID
```

### Environment Configuration

Create `.env` file:

```env
# Required for Azure Advisor API
AZURE_SUBSCRIPTION_ID=your-subscription-id-here

# Optional: Service Principal
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here
AZURE_CLIENT_SECRET=your-client-secret-here

# Optional: Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4

# Database
DATABASE_URL=sqlite+aiosqlite:///cost_monitoring.db
```

## 💻 Usage

### Basic Usage

```python
from src.monitoring.recommendations.ai_engine import AIRecommendationEngine

# Initialize with Azure integrations
engine = AIRecommendationEngine(use_azure_services=True)

# Generate comprehensive recommendations
result = await engine.generate_comprehensive_recommendations(
    include_advisor=True,   # Azure Advisor API
    include_waf=True,       # Well-Architected Framework
    include_pricing=True    # Azure Pricing API
)

# Access recommendations by source
advisor_recs = result["advisor_recommendations"]
waf_recs = result["waf_recommendations"]
pricing_insights = result["pricing_insights"]
ai_recs = result["ai_recommendations"]

# View summary
summary = result["summary"]
print(f"Total Recommendations: {summary['total_recommendations']}")
print(f"Potential Savings: ${summary['total_potential_monthly_savings']}")
```

### Test Each Integration

```bash
# Test Azure Advisor
python -m src.monitoring.recommendations.azure_advisor

# Test Well-Architected Framework
python -m src.monitoring.recommendations.azure_waf_cost

# Test Azure Pricing API
python -m src.monitoring.recommendations.azure_pricing

# Test Complete Engine
python -m src.monitoring.recommendations.ai_engine
```

## 📋 Example Output

```
================================================================================
🔷 COMPREHENSIVE AZURE COST RECOMMENDATIONS
================================================================================

📋 Fetching Azure Advisor recommendations...
   ✓ Found 3 official Azure Advisor recommendations

🏗️  Applying Azure Well-Architected Framework principles...
   ✓ Generated 15 WAF-based recommendations

💰 Calculating savings with Azure Pricing API...
   ✓ Calculated potential savings scenarios

🤖 Generating AI/rule-based recommendations...
   ✓ Generated 5 AI-powered recommendations

================================================================================
📋 RECOMMENDATIONS BY SOURCE
================================================================================

🔷 AZURE ADVISOR (Official Microsoft Recommendations)
--------------------------------------------------------------------------------

1. [HIGH IMPACT]
   Right-size underutilized virtual machines
   💡 Your Standard_D4s_v3 VM has been underutilized. Consider downsizing to Standard_D2s_v3
   💰 Savings: USD $1,234.56
   📖 https://portal.azure.com/#blade/Microsoft_Azure_Expert/AdvisorMenuBlade/Cost


🏗️  AZURE WELL-ARCHITECTED FRAMEWORK
--------------------------------------------------------------------------------

1. [HIGH] Use cost-effective pricing models
   Service: Microsoft.Compute
   💡 Purchase Azure Reserved VM Instances for predictable workloads
   💰 Potential Savings: 50.0%
   ⏱️  Effort: 1-2 hours
   📖 https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/
   Action Items:
     • Identify VMs running 24x7 with stable workloads
     • Review reservation recommendations in Azure portal
     • Purchase 1-year or 3-year reservations


💰 AZURE PRICING API - SAVINGS SCENARIOS
--------------------------------------------------------------------------------

Current Monthly Cost: $5,000.00

📅 1-Year Reserved Instances:
   Monthly: $3,000.00
   Savings: $2,000.00/month (40.0%)
   Total Savings: $24,000.00 over 1 year

📅 3-Year Reserved Instances:
   Monthly: $1,900.00
   Savings: $3,100.00/month (62.0%)
   Total Savings: $111,600.00 over 3 years

⚡ Spot VMs (for fault-tolerant workloads):
   Monthly: $1,000.00
   Savings: $4,000.00/month (80.0%)
   Best For: Batch processing, dev/test, fault-tolerant workloads

📖 https://learn.microsoft.com/en-us/azure/cost-management-billing/


🤖 AI ENGINE RECOMMENDATIONS
--------------------------------------------------------------------------------

1. Microsoft.Compute [HIGH]
   Current Cost: $2,500.00
   💰 Potential Savings: $750.00
   💡 Implement Reserved Instances, Spot VMs, and right-sizing
   ⏱️  Effort: 2-4 hours
   Action Items:
     • Purchase Azure Reserved VM Instances for 1-3 years
     • Use Spot VMs for dev/test and batch workloads
     • Right-size VMs based on utilization metrics

================================================================================
📊 SUMMARY
================================================================================
Total Recommendations: 24
  - Azure Advisor: 3
  - Well-Architected Framework: 15
  - AI Engine: 6

💰 Total Potential Monthly Savings: $5,234.56

Recommendation Sources:
  ✓ Azure Advisor (Official Microsoft)
  ✓ Azure Well-Architected Framework
  ✓ Azure Pricing API
  ✓ AI Engine

================================================================================
✓ All recommendations generated successfully!
================================================================================
```

## 🔐 Required Azure Permissions

### For Azure Advisor API:
- **Reader** role on subscription

### For Resource Graph:
- **Reader** role on subscription

### For Cost Management:
- **Cost Management Reader** role on subscription

### Grant Permissions:

```bash
# Grant Reader role
az role assignment create \
  --assignee {service-principal-id} \
  --role "Reader" \
  --scope /subscriptions/{subscription-id}

# Grant Cost Management Reader
az role assignment create \
  --assignee {service-principal-id} \
  --role "Cost Management Reader" \
  --scope /subscriptions/{subscription-id}
```

## 📚 Official Documentation Links

### Azure Services
- [Azure Advisor](https://learn.microsoft.com/en-us/azure/advisor/)
- [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/)
- [Cost Optimization Pillar](https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/)
- [Azure Pricing API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices)
- [Azure Cost Management](https://learn.microsoft.com/en-us/azure/cost-management-billing/)

### Cost Optimization Resources
- [Azure Reservations](https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/)
- [Spot VMs](https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms)
- [Azure Hybrid Benefit](https://learn.microsoft.com/en-us/azure/cost-management-billing/hybrid-benefit/)
- [Right-sizing Recommendations](https://learn.microsoft.com/en-us/azure/advisor/advisor-cost-recommendations)

### Authentication
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Service Principal](https://learn.microsoft.com/en-us/azure/active-directory/develop/howto-create-service-principal-portal)
- [DefaultAzureCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential)

## 🛠️ Troubleshooting

### "AZURE_SUBSCRIPTION_ID not set"
```bash
# Set environment variable
export AZURE_SUBSCRIPTION_ID="your-subscription-id"

# Or in PowerShell
$env:AZURE_SUBSCRIPTION_ID="your-subscription-id"
```

### "Failed to fetch Azure Advisor recommendations"
```bash
# Check authentication
az account show

# Check permissions
az role assignment list --assignee {your-user-or-sp-id} --all
```

### "No recommendations found"
- Azure Advisor generates recommendations based on actual usage
- It may take 24-48 hours after deploying resources
- Some recommendations only appear after 7+ days of usage data

## 🎯 Best Practices

1. **Regular Reviews**: Run recommendations weekly
2. **Prioritize High Impact**: Focus on High and Medium impact recommendations first
3. **Test Changes**: Validate in dev/test before production
4. **Track Savings**: Monitor actual savings after implementation
5. **Automate**: Integrate with CI/CD for continuous optimization

## 📝 Contributing

To add new recommendation sources:
1. Create new module in `src/monitoring/recommendations/`
2. Implement recommendation interface
3. Update `ai_engine.py` to include new source
4. Add tests and documentation

## 📄 License

MIT License - See LICENSE file

## 🤝 Support

For issues or questions:
- GitHub Issues: [Create Issue](https://github.com/your-repo/issues)
- Azure Support: https://azure.microsoft.com/support/
- Documentation: This file

---

**Last Updated:** November 4, 2025  
**Version:** 2.0.0  
**Maintainer:** Azure Cost Monitoring Team
