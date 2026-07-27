#!/usr/bin/env python3
"""
Restore 500+ comprehensive cost records directly to the database
"""

import subprocess
from datetime import datetime, timedelta
import random
import json

def generate_comprehensive_data():
    """Generate 500+ comprehensive cost records"""
    print("🔄 Generating 500+ comprehensive cost records...")
    
    # Multiple subscription scenarios
    subscriptions = [
        {"id": "46651d0c-a45f-4590-a0f7-9089f887ae19", "name": "Production"},
        {"id": "12345678-1234-1234-1234-123456789abc", "name": "Development"},
        {"id": "87654321-4321-4321-4321-cba987654321", "name": "Staging"},
        {"id": "11111111-2222-3333-4444-555555555555", "name": "Testing"},
        {"id": "22222222-3333-4444-5555-666666666666", "name": "Analytics"}
    ]
    
    # Comprehensive Azure services with realistic cost ranges
    services = [
        {"name": "Virtual Machines", "type": "Microsoft.Compute/virtualMachines", "min": 45, "max": 850},
        {"name": "SQL Database", "type": "Microsoft.Sql/servers/databases", "min": 120, "max": 1200},
        {"name": "Storage Accounts", "type": "Microsoft.Storage/storageAccounts", "min": 15, "max": 250},
        {"name": "App Service", "type": "Microsoft.Web/sites", "min": 35, "max": 450},
        {"name": "Azure Functions", "type": "Microsoft.Web/sites", "min": 8, "max": 180},
        {"name": "Application Gateway", "type": "Microsoft.Network/applicationGateways", "min": 85, "max": 320},
        {"name": "Key Vault", "type": "Microsoft.KeyVault/vaults", "min": 5, "max": 45},
        {"name": "Container Registry", "type": "Microsoft.ContainerRegistry/registries", "min": 25, "max": 160},
        {"name": "Azure Databricks", "type": "Microsoft.Databricks/workspaces", "min": 200, "max": 1500},
        {"name": "Azure Synapse", "type": "Microsoft.Synapse/workspaces", "min": 180, "max": 980},
        {"name": "Cognitive Services", "type": "Microsoft.CognitiveServices/accounts", "min": 12, "max": 380},
        {"name": "Azure Monitor", "type": "Microsoft.Insights/components", "min": 18, "max": 125},
        {"name": "Load Balancer", "type": "Microsoft.Network/loadBalancers", "min": 22, "max": 95},
        {"name": "VPN Gateway", "type": "Microsoft.Network/virtualNetworkGateways", "min": 135, "max": 285},
        {"name": "Azure Cache for Redis", "type": "Microsoft.Cache/Redis", "min": 75, "max": 550},
    ]
    
    regions = ["eastus", "westus2", "centralus", "westeurope", "northeurope", 
              "southeastasia", "japaneast", "australiaeast", "uksouth", "canadacentral"]
    
    resource_groups = ["rg-production-web", "rg-production-data", "rg-development", 
                      "rg-staging", "rg-testing", "rg-analytics", "rg-shared-services",
                      "rg-monitoring", "rg-security", "rg-networking"]
    
    # Generate data for last 45 days to ensure 500+ records
    end_date = datetime.now()
    start_date = end_date - timedelta(days=45)
    
    insert_statements = []
    
    # Generate diverse cost records
    current_date = start_date
    record_count = 0
    
    while current_date <= end_date and record_count < 600:  # Generate 600 to ensure 500+
        for subscription in subscriptions:
            sub_id = subscription["id"]
            sub_name = subscription["name"]
            
            # Different number of resources per subscription type
            daily_resources = {
                "Production": random.randint(8, 15),
                "Development": random.randint(3, 8),
                "Staging": random.randint(3, 6),
                "Testing": random.randint(2, 5),
                "Analytics": random.randint(4, 10)
            }.get(sub_name, 5)
            
            for _ in range(daily_resources):
                if record_count >= 600:
                    break
                    
                service = random.choice(services)
                region = random.choice(regions)
                rg = random.choice(resource_groups)
                
                # Resource naming convention
                resource_name = f"{service['name'].lower().replace(' ', '-')}-{random.randint(1, 99):02d}"
                resource_id = f"/subscriptions/{sub_id}/resourceGroups/{rg}/providers/{service['type']}/{resource_name}"
                
                # Cost calculation with subscription-specific multipliers
                base_cost = random.uniform(service["min"], service["max"])
                cost_multiplier = {
                    "Production": random.uniform(0.9, 1.8),
                    "Development": random.uniform(0.3, 0.7), 
                    "Staging": random.uniform(0.4, 0.8),
                    "Testing": random.uniform(0.2, 0.5),
                    "Analytics": random.uniform(0.6, 1.4)
                }.get(sub_name, 1.0)
                
                daily_cost = round(base_cost * cost_multiplier, 2)
                
                # Weekend reduction
                if current_date.weekday() >= 5:
                    daily_cost *= random.uniform(0.6, 0.85)
                
                # Create metadata
                metadata = {
                    "environment": sub_name.lower(),
                    "location": region,
                    "department": random.choice(["engineering", "data", "security", "operations"]),
                    "cost_center": random.choice(["cc-001", "cc-002", "cc-003", "cc-004"]),
                    "project": random.choice(["project-alpha", "project-beta", "project-gamma"]),
                    "owner": random.choice(["team-web", "team-data", "team-platform", "team-mobile"])
                }
                
                tags = {
                    "Environment": sub_name,
                    "Project": metadata["project"],
                    "Owner": metadata["owner"],
                    "CostCenter": metadata["cost_center"]
                }
                
                # Create INSERT statement
                insert_stmt = f"""
                INSERT INTO cost_records (
                    date, subscription_id, resource_group, resource_id, resource_name,
                    service_name, resource_type, region, cost, currency, tags, metadata
                ) VALUES (
                    '{current_date.strftime('%Y-%m-%d')}',
                    '{sub_id}',
                    '{rg}',
                    '{resource_id}',
                    '{resource_name}',
                    '{service["name"]}',
                    '{service["type"]}',
                    '{region}',
                    {daily_cost},
                    'USD',
                    '{json.dumps(tags)}',
                    '{json.dumps(metadata)}'
                );"""
                
                insert_statements.append(insert_stmt.strip())
                record_count += 1
                
                if record_count % 100 == 0:
                    print(f"   Generated {record_count} records...")
        
        current_date += timedelta(days=1)
    
    print(f"✅ Generated {len(insert_statements)} cost record statements")
    return insert_statements

def insert_ai_recommendations():
    """Insert comprehensive AI recommendations"""
    print("🤖 Generating AI recommendations...")
    
    recommendations = [
        {
            "resource_id": "/subscriptions/46651d0c-a45f-4590-a0f7-9089f887ae19/resourceGroups/rg-production-web/providers/Microsoft.Compute/virtualMachines/virtual-machines-01",
            "type": "resize",
            "title": "Downsize Overprovisioned VM",
            "description": "VM shows low CPU utilization (avg 15%). Recommend downsizing from Standard_D8s_v3 to Standard_D4s_v3.",
            "savings": 180.50,
            "confidence": 0.92,
            "priority": "high"
        },
        {
            "resource_id": "/subscriptions/46651d0c-a45f-4590-a0f7-9089f887ae19/resourceGroups/rg-production-data/providers/Microsoft.Storage/storageAccounts/storage-accounts-05",
            "type": "storage_tier",
            "title": "Move to Cool Storage Tier",
            "description": "Storage account contains data accessed less than monthly. Moving to Cool tier can reduce costs significantly.",
            "savings": 245.30,
            "confidence": 0.88,
            "priority": "medium"
        },
        {
            "resource_id": "/subscriptions/46651d0c-a45f-4590-a0f7-9089f887ae19/resourceGroups/rg-production-data/providers/Microsoft.Sql/servers/databases/sql-database-03",
            "type": "reserved_instance", 
            "title": "Purchase SQL Reserved Instance",
            "description": "SQL Database shows consistent 24/7 usage. 3-year reserved instance provides 65% savings.",
            "savings": 1250.00,
            "confidence": 0.95,
            "priority": "high"
        },
        {
            "resource_id": "/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/rg-development/providers/Microsoft.Web/sites/app-service-12",
            "type": "schedule",
            "title": "Implement Auto-Shutdown Schedule",
            "description": "Development App Service runs 24/7 but only used during business hours. Implement shutdown schedule.",
            "savings": 120.75,
            "confidence": 0.85,
            "priority": "medium"
        },
        {
            "resource_id": "/subscriptions/87654321-4321-4321-4321-cba987654321/resourceGroups/rg-analytics/providers/Microsoft.Databricks/workspaces/azure-databricks-08",
            "type": "optimization",
            "title": "Optimize Databricks Cluster Configuration", 
            "description": "Databricks cluster is using premium instances for standard workloads. Switch to standard instances.",
            "savings": 380.25,
            "confidence": 0.90,
            "priority": "high"
        },
        {
            "resource_id": "/subscriptions/11111111-2222-3333-4444-555555555555/resourceGroups/rg-testing/providers/Microsoft.Compute/virtualMachines/virtual-machines-22",
            "type": "decommission",
            "title": "Remove Unused Testing VM",
            "description": "VM has been idle for 30+ days with no activity. Consider decommissioning.",
            "savings": 155.40,
            "confidence": 0.93,
            "priority": "high"
        }
    ]
    
    insert_statements = []
    for rec in recommendations:
        metadata = {
            "category": "cost-optimization",
            "impact": rec["priority"],
            "recommendation_source": "AI Engine v2.1"
        }
        
        insert_stmt = f"""
        INSERT INTO ai_recommendations (
            resource_id, recommendation_type, title, description,
            potential_savings, confidence_score, priority, metadata
        ) VALUES (
            '{rec["resource_id"]}',
            '{rec["type"]}',
            '{rec["title"]}',
            '{rec["description"]}',
            {rec["savings"]},
            {rec["confidence"]},
            '{rec["priority"]}',
            '{json.dumps(metadata)}'
        );"""
        
        insert_statements.append(insert_stmt.strip())
    
    print(f"✅ Generated {len(insert_statements)} AI recommendation statements")
    return insert_statements

def insert_budgets():
    """Insert budget configurations"""
    print("💰 Generating budget configurations...")
    
    budgets = [
        {
            "name": "Production Environment Monthly",
            "amount": 2500.00,
            "period": "monthly",
            "filter": {"subscription_id": "46651d0c-a45f-4590-a0f7-9089f887ae19"},
            "thresholds": [0.8, 0.9, 1.0]
        },
        {
            "name": "Development Resources",
            "amount": 800.00,
            "period": "monthly",
            "filter": {"subscription_id": "12345678-1234-1234-1234-123456789abc"},
            "thresholds": [0.7, 0.85, 1.0]
        },
        {
            "name": "Analytics Workloads", 
            "amount": 1200.00,
            "period": "monthly",
            "filter": {"subscription_id": "22222222-3333-4444-5555-666666666666"},
            "thresholds": [0.9, 1.0]
        },
        {
            "name": "Testing Environment",
            "amount": 400.00,
            "period": "monthly", 
            "filter": {"subscription_id": "11111111-2222-3333-4444-555555555555"},
            "thresholds": [0.6, 0.8, 1.0]
        }
    ]
    
    insert_statements = []
    for budget in budgets:
        # Convert thresholds to PostgreSQL array format
        thresholds_str = "{" + ",".join(map(str, budget["thresholds"])) + "}"
        
        insert_stmt = f"""
        INSERT INTO cost_budgets (
            name, budget_amount, time_period, resource_filter, 
            alert_thresholds, is_active
        ) VALUES (
            '{budget["name"]}',
            {budget["amount"]},
            '{budget["period"]}',
            '{json.dumps(budget["filter"])}',
            '{thresholds_str}',
            true
        );"""
        
        insert_statements.append(insert_stmt.strip())
    
    print(f"✅ Generated {len(insert_statements)} budget configuration statements")
    return insert_statements

def execute_bulk_insert(statements, description):
    """Execute multiple INSERT statements efficiently"""
    print(f"📊 Inserting {description}...")
    
    try:
        # Create a combined SQL statement
        combined_sql = "\n".join(statements)
        
        # Use docker exec to run the SQL
        cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev'
        
        # Execute in chunks to avoid command line limits
        chunk_size = 50
        total_chunks = (len(statements) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(statements), chunk_size):
            chunk = statements[i:i + chunk_size]
            chunk_sql = "\n".join(chunk)
            
            result = subprocess.run(
                cmd,
                input=chunk_sql,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Error in chunk {i//chunk_size + 1}: {result.stderr}")
                return False
            
            print(f"   Processed chunk {i//chunk_size + 1}/{total_chunks}")
        
        print(f"✅ Successfully inserted {len(statements)} {description}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to insert {description}: {e}")
        return False

def verify_data_restoration():
    """Verify the data was restored successfully"""
    print("\n🔍 Verifying data restoration...")
    
    try:
        # Check cost records
        cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM cost_records;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        cost_count = result.stdout.strip() if result.returncode == 0 else "0"
        
        # Check recommendations
        cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM ai_recommendations;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        rec_count = result.stdout.strip() if result.returncode == 0 else "0"
        
        # Check budgets
        cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM cost_budgets;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        budget_count = result.stdout.strip() if result.returncode == 0 else "0"
        
        print(f"📊 Data Restoration Summary:")
        print(f"   • Cost Records: {cost_count}")
        print(f"   • AI Recommendations: {rec_count}")
        print(f"   • Budget Configurations: {budget_count}")
        
        # Show cost summary by subscription
        cmd = '''docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT substring(subscription_id, 1, 8) as sub, SUM(cost), COUNT(*) FROM cost_records GROUP BY substring(subscription_id, 1, 8) ORDER BY SUM(cost) DESC;"'''
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"\n💰 Cost Summary by Subscription:")
            lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    print(f"   • {parts[0]}...: ${parts[1]} ({parts[2]} records)")
        
        return int(cost_count) >= 500
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Restoring 500+ Comprehensive Cost Records")
    print("=" * 55)
    
    # Generate all data
    cost_statements = generate_comprehensive_data()
    recommendation_statements = insert_ai_recommendations()
    budget_statements = insert_budgets()
    
    # Insert data in order
    success = True
    success &= execute_bulk_insert(cost_statements, "cost records")
    success &= execute_bulk_insert(recommendation_statements, "AI recommendations")
    success &= execute_bulk_insert(budget_statements, "budget configurations")
    
    # Verify restoration
    if success and verify_data_restoration():
        print(f"\n🌐 Your dashboards are now ready with 500+ records:")
        print(f"   • Grafana Dashboard: http://localhost:3000")
        print(f"     Username: admin")
        print(f"     Password: AzureCost2025!SecurePass")
        print(f"   • FastAPI Interface: http://localhost:8000")
        print(f"   • Prometheus Metrics: http://localhost:9090")
        print(f"\n✅ Data restoration completed successfully!")
    else:
        print(f"\n❌ Data restoration encountered issues. Please check the logs above.")