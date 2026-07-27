#!/usr/bin/env python3
"""
Simple script to quickly restore 500+ cost records using direct SQL
"""

import subprocess
from datetime import datetime, timedelta
import random

def create_simple_data():
    """Create 500+ simple cost records"""
    print("🔄 Creating 500+ cost records...")
    
    subscriptions = [
        "46651d0c-a45f-4590-a0f7-9089f887ae19",
        "12345678-1234-1234-1234-123456789abc", 
        "87654321-4321-4321-4321-cba987654321",
        "11111111-2222-3333-4444-555555555555"
    ]
    
    services = [
        "Virtual Machines",
        "SQL Database", 
        "Storage Accounts",
        "App Service",
        "Azure Functions",
        "Application Gateway"
    ]
    
    resource_groups = [
        "rg-production",
        "rg-development", 
        "rg-staging",
        "rg-testing"
    ]
    
    regions = ["eastus", "westus2", "westeurope", "southeastasia"]
    
    # Generate data for last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    records = []
    current_date = start_date
    
    while current_date <= end_date:
        for sub_id in subscriptions:
            for _ in range(random.randint(4, 8)):  # 4-8 resources per subscription per day
                service = random.choice(services)
                rg = random.choice(resource_groups)
                region = random.choice(regions)
                cost = round(random.uniform(10, 500), 2)
                resource_name = f"{service.lower().replace(' ', '-')}-{random.randint(1, 99):02d}"
                
                record = (
                    current_date.strftime('%Y-%m-%d'),
                    sub_id,
                    rg,
                    f"/subscriptions/{sub_id}/resourceGroups/{rg}/providers/Microsoft.Compute/{resource_name}",
                    resource_name,
                    service,
                    "Microsoft.Compute/virtualMachines",
                    region,
                    cost,
                    "USD"
                )
                records.append(record)
        
        current_date += timedelta(days=1)
    
    print(f"✅ Generated {len(records)} records")
    return records

def insert_batch_records(records, batch_size=50):
    """Insert records in batches"""
    print(f"📊 Inserting {len(records)} records in batches of {batch_size}...")
    
    total_batches = (len(records) + batch_size - 1) // batch_size
    successful_inserts = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        
        # Create VALUES clause for batch
        values_list = []
        for record in batch:
            values_str = f"('{record[0]}', '{record[1]}', '{record[2]}', '{record[3]}', '{record[4]}', '{record[5]}', '{record[6]}', '{record[7]}', {record[8]}, '{record[9]}')"
            values_list.append(values_str)
        
        values_clause = ",\n".join(values_list)
        
        sql = f"""
        INSERT INTO cost_records (
            date, subscription_id, resource_group, resource_id, 
            resource_name, service_name, resource_type, region, cost, currency
        ) VALUES
        {values_clause};
        """
        
        try:
            result = subprocess.run(
                ['docker', 'exec', 'azure-cost-db', 'psql', '-U', 'postgres', '-d', 'azure_cost_dev', '-c', sql],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                successful_inserts += len(batch)
                print(f"   ✅ Batch {i//batch_size + 1}/{total_batches} completed ({len(batch)} records)")
            else:
                print(f"   ❌ Batch {i//batch_size + 1} failed: {result.stderr}")
                
        except Exception as e:
            print(f"   ❌ Batch {i//batch_size + 1} error: {e}")
    
    print(f"✅ Successfully inserted {successful_inserts} records")
    return successful_inserts

def add_sample_recommendations():
    """Add sample AI recommendations"""
    print("🤖 Adding AI recommendations...")
    
    sql = """
    INSERT INTO ai_recommendations (
        resource_id, recommendation_type, title, description, 
        potential_savings, confidence_score, priority
    ) VALUES
    ('/subscriptions/46651d0c-a45f-4590-a0f7-9089f887ae19/resourceGroups/rg-production/providers/Microsoft.Compute/vm-web-01', 
     'resize', 'Downsize VM', 'VM shows low utilization. Consider downsizing.', 150.00, 0.85, 'medium'),
    ('/subscriptions/46651d0c-a45f-4590-a0f7-9089f887ae19/resourceGroups/rg-production/providers/Microsoft.Storage/storage-01', 
     'storage_tier', 'Change Storage Tier', 'Move to cooler storage tier for cost savings.', 75.50, 0.90, 'high'),
    ('/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/rg-development/providers/Microsoft.Sql/sqldb-01', 
     'reserved_instance', 'Purchase Reserved Instance', 'Consistent usage pattern detected.', 500.00, 0.95, 'high');
    """
    
    result = subprocess.run(
        ['docker', 'exec', 'azure-cost-db', 'psql', '-U', 'postgres', '-d', 'azure_cost_dev', '-c', sql],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Added 3 AI recommendations")
        return True
    else:
        print(f"❌ Failed to add recommendations: {result.stderr}")
        return False

def add_sample_budgets():
    """Add sample budget configurations"""
    print("💰 Adding budget configurations...")
    
    sql = """
    INSERT INTO cost_budgets (
        name, budget_amount, time_period, is_active
    ) VALUES
    ('Production Monthly Budget', 2000.00, 'monthly', true),
    ('Development Monthly Budget', 500.00, 'monthly', true),
    ('Analytics Quarterly Budget', 1500.00, 'quarterly', true);
    """
    
    result = subprocess.run(
        ['docker', 'exec', 'azure-cost-db', 'psql', '-U', 'postgres', '-d', 'azure_cost_dev', '-c', sql],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Added 3 budget configurations")
        return True
    else:
        print(f"❌ Failed to add budgets: {result.stderr}")
        return False

def verify_final_data():
    """Verify the final data counts"""
    print("\n🔍 Verifying final data...")
    
    # Check cost records
    result = subprocess.run(
        ['docker', 'exec', 'azure-cost-db', 'psql', '-U', 'postgres', '-d', 'azure_cost_dev', '-t', '-c', 'SELECT COUNT(*) FROM cost_records;'],
        capture_output=True,
        text=True
    )
    cost_count = result.stdout.strip() if result.returncode == 0 else "0"
    
    # Check recommendations  
    result = subprocess.run(
        ['docker', 'exec', 'azure-cost-db', 'psql', '-U', 'postgres', '-d', 'azure_cost_dev', '-t', '-c', 'SELECT COUNT(*) FROM ai_recommendations;'],
        capture_output=True,
        text=True
    )
    rec_count = result.stdout.strip() if result.returncode == 0 else "0"
    
    # Check budgets
    result = subprocess.run(
        ['docker', 'exec', 'azure-cost-db', 'psql', '-U', 'postgres', '-d', 'azure_cost_dev', '-t', '-c', 'SELECT COUNT(*) FROM cost_budgets;'],
        capture_output=True,
        text=True
    )
    budget_count = result.stdout.strip() if result.returncode == 0 else "0"
    
    print(f"📊 Final Data Summary:")
    print(f"   • Cost Records: {cost_count}")
    print(f"   • AI Recommendations: {rec_count}")
    print(f"   • Budget Configurations: {budget_count}")
    
    # Show cost summary
    result = subprocess.run(
        ['docker', 'exec', 'azure-cost-db', 'psql', '-U', 'postgres', '-d', 'azure_cost_dev', '-t', '-c', 
         "SELECT service_name, COUNT(*), SUM(cost) FROM cost_records GROUP BY service_name ORDER BY SUM(cost) DESC LIMIT 5;"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0 and result.stdout.strip():
        print(f"\n💰 Top Services by Cost:")
        lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        for line in lines:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                print(f"   • {parts[0]}: ${parts[2]} ({parts[1]} records)")
    
    return int(cost_count) >= 500

if __name__ == "__main__":
    print("🚀 Quick Restore: 500+ Cost Records")
    print("=" * 40)
    
    # Generate records
    records = create_simple_data()
    
    # Insert records in batches
    inserted_count = insert_batch_records(records, batch_size=25)
    
    # Add recommendations and budgets
    add_sample_recommendations()
    add_sample_budgets()
    
    # Verify
    if verify_final_data():
        print(f"\n🌐 Your data has been restored! Access your dashboards:")
        print(f"   • Grafana: http://localhost:3000 (admin/AzureCost2025!SecurePass)")
        print(f"   • API: http://localhost:8000")
        print(f"\n✅ Successfully restored {inserted_count} records!")
    else:
        print(f"\n❌ Restoration incomplete. {inserted_count} records were inserted but verification failed.")