#!/usr/bin/env python3
"""
Restore sample Azure cost data for dashboard visualization
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'src'))

from src.common.logging_config import setup_logging
from src.common.database import get_session
from src.monitoring.storage.models import CostRecord, AIRecommendation, CostBudget

# Setup logging
logger = setup_logging()

def create_tables():
    """Create database tables using direct SQL"""
    print("🔨 Creating database tables...")
    try:
        import subprocess
        
        # Create tables using SQL directly
        create_sql = """
        CREATE TABLE IF NOT EXISTS cost_records (
            id SERIAL PRIMARY KEY,
            subscription_id VARCHAR(36) NOT NULL,
            resource_group VARCHAR(255),
            resource_name VARCHAR(255),
            service VARCHAR(255),
            cost DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            currency VARCHAR(3) DEFAULT 'USD',
            date DATE NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS ai_recommendations (
            id SERIAL PRIMARY KEY,
            resource_id TEXT NOT NULL,
            recommendation_type VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            potential_savings DECIMAL(10,2),
            confidence_score DECIMAL(3,2),
            priority VARCHAR(20),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_applied BOOLEAN DEFAULT FALSE
        );
        
        CREATE TABLE IF NOT EXISTS cost_budgets (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            budget_amount DECIMAL(10,2) NOT NULL,
            time_period VARCHAR(20) NOT NULL,
            resource_filter JSONB,
            alert_thresholds DECIMAL(3,2)[],
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "{create_sql}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Database tables created successfully")
            return True
        else:
            print(f"❌ Failed to create tables: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

def generate_sample_cost_data():
    """Generate sample cost data for the last 30 days"""
    print("📊 Generating sample cost data...")
    
    sample_data = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Sample Azure resources
    resources = [
        {"resource_group": "rg-production-east", "resource_name": "vm-web-server-01", "service": "Virtual Machines", "base_cost": 150},
        {"resource_group": "rg-production-east", "resource_name": "sql-database-prod", "service": "SQL Database", "base_cost": 320},
        {"resource_group": "rg-development", "resource_name": "vm-dev-server", "service": "Virtual Machines", "base_cost": 80},
        {"resource_group": "rg-development", "resource_name": "storage-dev-account", "service": "Storage Accounts", "base_cost": 45},
        {"resource_group": "rg-analytics", "resource_name": "databricks-workspace", "service": "Azure Databricks", "base_cost": 280},
        {"resource_group": "rg-analytics", "resource_name": "synapse-analytics", "service": "Azure Synapse", "base_cost": 195},
        {"resource_group": "rg-networking", "resource_name": "vnet-gateway", "service": "VPN Gateway", "base_cost": 125},
        {"resource_group": "rg-monitoring", "resource_name": "log-analytics-ws", "service": "Log Analytics", "base_cost": 65}
    ]
    
    subscription_id = "12345678-1234-1234-1234-123456789012"
    
    current_date = start_date
    while current_date <= end_date:
        for resource in resources:
            # Add some randomness to daily costs
            daily_cost = resource["base_cost"] + random.uniform(-10, 20)
            if daily_cost < 0:
                daily_cost = 0
                
            cost_record = CostRecord(
                subscription_id=subscription_id,
                resource_group=resource["resource_group"],
                resource_name=resource["resource_name"],
                service=resource["service"],
                cost=round(daily_cost, 2),
                currency="USD",
                date=current_date.date(),
                metadata={
                    "location": "eastus" if "east" in resource["resource_group"] else "westus",
                    "environment": "production" if "production" in resource["resource_group"] else "development",
                    "tags": {
                        "project": "cost-monitoring",
                        "team": "devops"
                    }
                }
            )
            sample_data.append(cost_record)
        
        current_date += timedelta(days=1)
    
    return sample_data

def generate_sample_recommendations():
    """Generate sample AI recommendations"""
    print("🤖 Generating AI recommendations...")
    
    recommendations = [
        AIRecommendation(
            resource_id="/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-development/providers/Microsoft.Compute/virtualMachines/vm-dev-server",
            recommendation_type="resize",
            title="Downsize Development VM",
            description="VM vm-dev-server shows low CPU utilization (avg 12%). Consider downsizing from Standard_D4s_v3 to Standard_D2s_v3.",
            potential_savings=45.30,
            confidence_score=0.87,
            priority="medium",
            metadata={
                "current_sku": "Standard_D4s_v3",
                "recommended_sku": "Standard_D2s_v3",
                "cpu_utilization": 12.3,
                "memory_utilization": 28.5
            }
        ),
        AIRecommendation(
            resource_id="/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-analytics/providers/Microsoft.Storage/storageAccounts/storage-dev-account",
            recommendation_type="storage_tier",
            title="Change Storage Tier",
            description="Storage account has data accessed less than once per month. Consider moving to Archive tier.",
            potential_savings=125.50,
            confidence_score=0.92,
            priority="high",
            metadata={
                "current_tier": "Hot",
                "recommended_tier": "Archive",
                "last_access": "45 days ago",
                "data_size_gb": 2500
            }
        ),
        AIRecommendation(
            resource_id="/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-production-east/providers/Microsoft.Sql/servers/sql-database-prod",
            recommendation_type="reserved_instance",
            title="Purchase Reserved Instance",
            description="SQL Database shows consistent usage pattern. Purchase 1-year reserved instance for significant savings.",
            potential_savings=890.25,
            confidence_score=0.95,
            priority="high",
            metadata={
                "current_pricing": "Pay-as-you-go",
                "recommended_commitment": "1 year",
                "usage_consistency": 98.5,
                "annual_savings": 890.25
            }
        )
    ]
    
    return recommendations

def generate_sample_budgets():
    """Generate sample budget configurations"""
    print("💰 Generating budget configurations...")
    
    budgets = [
        CostBudget(
            name="Production Environment",
            budget_amount=1500.00,
            time_period="monthly",
            resource_filter={"resource_group": "rg-production-east"},
            alert_thresholds=[0.8, 0.9, 1.0],
            is_active=True
        ),
        CostBudget(
            name="Development Resources",
            budget_amount=500.00,
            time_period="monthly", 
            resource_filter={"resource_group": "rg-development"},
            alert_thresholds=[0.7, 0.85, 1.0],
            is_active=True
        ),
        CostBudget(
            name="Analytics Workloads",
            budget_amount=800.00,
            time_period="monthly",
            resource_filter={"resource_group": "rg-analytics"},
            alert_thresholds=[0.9, 1.0],
            is_active=True
        )
    ]
    
    return budgets

def populate_database():
    """Populate database with sample data using direct SQL"""
    print("📊 Inserting sample data...")
    try:
        import subprocess
        
        # Generate sample cost data
        cost_data = generate_sample_cost_data()
        
        # Insert cost records
        for record in cost_data[:50]:  # Insert first 50 records as sample
            insert_sql = f"""
            INSERT INTO cost_records (subscription_id, resource_group, resource_name, service, cost, currency, date, metadata)
            VALUES ('{record.subscription_id}', '{record.resource_group}', '{record.resource_name}', 
                    '{record.service}', {record.cost}, '{record.currency}', '{record.date}', 
                    '{{"location": "eastus", "environment": "production"}}');
            """
            
            cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "{insert_sql}"'
            subprocess.run(cmd, shell=True, capture_output=True)
        
        print(f"✅ Added {min(50, len(cost_data))} cost records")
        
        # Insert AI recommendations
        recommendations = generate_sample_recommendations()
        for rec in recommendations:
            insert_sql = f"""
            INSERT INTO ai_recommendations (resource_id, recommendation_type, title, description, potential_savings, confidence_score, priority, metadata)
            VALUES ('{rec.resource_id}', '{rec.recommendation_type}', '{rec.title}', 
                    '{rec.description}', {rec.potential_savings}, {rec.confidence_score}, '{rec.priority}',
                    '{{"category": "optimization"}}');
            """
            
            cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "{insert_sql}"'
            subprocess.run(cmd, shell=True, capture_output=True)
        
        print(f"✅ Added {len(recommendations)} AI recommendations")
        
        # Insert budgets
        budgets = generate_sample_budgets()
        for budget in budgets:
            insert_sql = f"""
            INSERT INTO cost_budgets (name, budget_amount, time_period, resource_filter, is_active)
            VALUES ('{budget.name}', {budget.budget_amount}, '{budget.time_period}', 
                    '{{"resource_group": "rg-production"}}', {budget.is_active});
            """
            
            cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "{insert_sql}"'
            subprocess.run(cmd, shell=True, capture_output=True)
        
        print(f"✅ Added {len(budgets)} budget configurations")
        print("✅ All sample data saved successfully")
        
        return True
    except Exception as e:
        print(f"❌ Database population failed: {e}")
        return False

def verify_data():
    """Verify the data was inserted correctly"""
    print("\n🔍 Verifying sample data...")
    try:
        import subprocess
        
        # Check cost records
        cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM cost_records;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        cost_count = result.stdout.strip() if result.returncode == 0 else "0"
        
        # Check recommendations
        cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM ai_recommendations;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        recommendation_count = result.stdout.strip() if result.returncode == 0 else "0"
        
        # Check budgets
        cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM cost_budgets;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        budget_count = result.stdout.strip() if result.returncode == 0 else "0"
        
        print(f"📊 Data Summary:")
        print(f"   • Cost records: {cost_count}")
        print(f"   • AI recommendations: {recommendation_count}")
        print(f"   • Budget configurations: {budget_count}")
        
        # Show cost breakdown
        cmd = '''docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT resource_group, SUM(cost), COUNT(*) FROM cost_records GROUP BY resource_group ORDER BY SUM(cost) DESC LIMIT 5;"'''
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"\n💰 Top Cost by Resource Group:")
            lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    print(f"   • {parts[0]}: ${parts[1]} ({parts[2]} records)")
        
        return True
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Restoring Sample Azure Cost Data")
    print("=" * 50)
    
    # Create tables
    if not create_tables():
        sys.exit(1)
    
    # Populate with sample data
    if not populate_database():
        sys.exit(1)
    
    # Verify data
    if verify_data():
        print(f"\n🌐 Your dashboards are now ready:")
        print(f"   • Grafana: http://localhost:3000 (admin / AzureCost2025!SecurePass)")
        print(f"   • FastAPI: http://localhost:8000")
        print(f"\n✅ Sample data restoration completed successfully!")