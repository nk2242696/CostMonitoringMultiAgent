#!/usr/bin/env python3
"""
Generate sample multi-subscription cost data for testing the dashboard.
This creates realistic test data to demonstrate multi-subscription features.
"""
import os
import sys
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.common.database import get_session
from src.monitoring.storage.models import CostRecord

def generate_test_data():
    """Generate sample multi-subscription cost data."""
    
    print("🧪 Generating Multi-Subscription Test Data")
    print("=" * 50)
    
    # Sample subscriptions
    subscriptions = [
        {"id": "46651d0c-a45f-4590-a0f7-9089f887ae19", "name": "Production"},
        {"id": "12345678-1234-1234-1234-123456789abc", "name": "Development"},
        {"id": "87654321-4321-4321-4321-cba987654321", "name": "Staging"},
        {"id": "11111111-2222-3333-4444-555555555555", "name": "Testing"}
    ]
    
    # Sample services and their typical cost ranges
    services = {
        "Microsoft.Compute": {"min": 50, "max": 500, "resources": ["vm-web-01", "vm-app-01", "vm-db-01"]},
        "Microsoft.Storage": {"min": 10, "max": 100, "resources": ["storage001", "storage002", "storage003"]},
        "Microsoft.Network": {"min": 20, "max": 200, "resources": ["vnet-main", "lb-frontend", "appgw-01"]},
        "Microsoft.Sql": {"min": 100, "max": 800, "resources": ["sqldb-prod", "sqldb-dev", "sqldb-test"]},
        "Microsoft.Web": {"min": 30, "max": 300, "resources": ["webapp-api", "webapp-ui", "funcapp-01"]},
        "Microsoft.KeyVault": {"min": 5, "max": 50, "resources": ["kv-secrets", "kv-certs", "kv-keys"]},
        "Microsoft.ContainerRegistry": {"min": 25, "max": 150, "resources": ["acr-images", "acr-builds"]},
        "Microsoft.Insights": {"min": 15, "max": 120, "resources": ["appinsights-prod", "appinsights-dev"]}
    }
    
    regions = ["eastus", "westus2", "westeurope", "southeastasia", "australiaeast"]
    resource_groups = ["rg-production", "rg-development", "rg-staging", "rg-testing", "rg-shared"]
    
    # Generate data for the last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    session = next(get_session())
    
    try:
        # Clear existing test data (except original subscription)
        original_sub = "46651d0c-a45f-4590-a0f7-9089f887ae19"
        test_subs = [sub["id"] for sub in subscriptions if sub["id"] != original_sub]
        
        if test_subs:
            delete_count = session.query(CostRecord).filter(
                CostRecord.subscription_id.in_(test_subs)
            ).count()
            
            if delete_count > 0:
                session.query(CostRecord).filter(
                    CostRecord.subscription_id.in_(test_subs)
                ).delete(synchronize_session=False)
                print(f"🗑️ Removed {delete_count} existing test records")
        
        total_records = 0
        
        # Generate cost data for each subscription
        for subscription in subscriptions:
            sub_id = subscription["id"]
            sub_name = subscription["name"]
            
            print(f"\n📊 Generating data for {sub_name} ({sub_id[:8]}...)")
            
            current_date = start_date
            sub_records = 0
            
            while current_date <= end_date:
                # Generate costs for each service on this day
                for service_name, config in services.items():
                    for resource_name in config["resources"]:
                        # Different cost patterns for different subscription types
                        cost_multiplier = {
                            "Production": random.uniform(0.8, 1.5),
                            "Development": random.uniform(0.3, 0.8), 
                            "Staging": random.uniform(0.4, 0.9),
                            "Testing": random.uniform(0.2, 0.6)
                        }.get(sub_name, 1.0)
                        
                        base_cost = random.uniform(config["min"], config["max"])
                        daily_cost = base_cost * cost_multiplier
                        
                        # Add some weekend/weekday variation
                        if current_date.weekday() >= 5:  # Weekend
                            daily_cost *= random.uniform(0.6, 0.9)
                        
                        # Add some random variation
                        daily_cost *= random.uniform(0.85, 1.15)
                        
                        record = CostRecord(
                            date=current_date,
                            subscription_id=sub_id,
                            resource_group=random.choice(resource_groups),
                            resource_id=f"/subscriptions/{sub_id}/resourceGroups/{random.choice(resource_groups)}/providers/{service_name}/{resource_name}",
                            resource_name=resource_name,
                            service_name=service_name,
                            resource_type=service_name.replace("Microsoft.", ""),
                            region=random.choice(regions),
                            cost=Decimal(str(round(daily_cost, 2))),
                            currency="USD",
                            tags={
                                "Environment": sub_name,
                                "CostCenter": f"CC-{random.randint(1000, 9999)}",
                                "Owner": f"team-{random.choice(['alpha', 'beta', 'gamma'])}"
                            },
                            cost_metadata={
                                "generated": True,
                                "test_data": True
                            }
                        )
                        
                        session.add(record)
                        sub_records += 1
                        total_records += 1
                
                current_date += timedelta(days=1)
            
            print(f"   ✅ Generated {sub_records} records for {sub_name}")
        
        # Commit all the data
        session.commit()
        print(f"\n🎉 Successfully generated {total_records} cost records!")
        
        # Show summary by subscription
        print(f"\n📈 Data Summary:")
        for subscription in subscriptions:
            sub_id = subscription["id"]
            sub_name = subscription["name"]
            
            sub_total = session.query(CostRecord).filter(
                CostRecord.subscription_id == sub_id,
                CostRecord.date >= start_date
            ).count()
            
            cost_total = session.query(CostRecord).filter(
                CostRecord.subscription_id == sub_id,
                CostRecord.date >= start_date
            ).with_entities(
                CostRecord.cost
            ).all()
            
            total_cost = sum(float(record.cost) for record in cost_total) if cost_total else 0
            
            print(f"   • {sub_name}: {sub_total} records, ${total_cost:,.2f} total cost")
        
        print(f"\n🌐 View your multi-subscription dashboard:")
        print(f"   • Grafana: http://localhost:3000/d/azure-multi-sub")
        print(f"   • API Dashboard: http://localhost:8000")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error generating test data: {e}")
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    success = generate_test_data()
    sys.exit(0 if success else 1)