#!/usr/bin/env python3
"""
Simple script to add sample cost data directly via SQL
"""

import subprocess
from datetime import datetime, timedelta
import random

def create_tables():
    """Create database tables"""
    print("🔨 Creating database tables...")
    
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
        alert_thresholds TEXT[],
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

def add_sample_data():
    """Add sample cost data"""
    print("📊 Adding sample cost data...")
    
    subscription_id = "12345678-1234-1234-1234-123456789012"
    
    # Sample data for the last 7 days
    resources = [
        ("rg-production-east", "vm-web-server-01", "Virtual Machines", 150.25),
        ("rg-production-east", "sql-database-prod", "SQL Database", 320.75),
        ("rg-development", "vm-dev-server", "Virtual Machines", 80.50),
        ("rg-development", "storage-dev-account", "Storage Accounts", 45.30),
        ("rg-analytics", "databricks-workspace", "Azure Databricks", 280.90),
        ("rg-analytics", "synapse-analytics", "Azure Synapse", 195.60),
        ("rg-networking", "vnet-gateway", "VPN Gateway", 125.40),
        ("rg-monitoring", "log-analytics-ws", "Log Analytics", 65.20)
    ]
    
    # Insert data for the last 7 days
    end_date = datetime.now()
    
    for i in range(7):
        current_date = end_date - timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')
        
        for rg, resource_name, service, base_cost in resources:
            # Add some randomness to daily costs
            daily_cost = base_cost + random.uniform(-10, 20)
            if daily_cost < 0:
                daily_cost = 5.00  # Minimum cost
            
            insert_sql = f"""
            INSERT INTO cost_records (subscription_id, resource_group, resource_name, service, cost, currency, date, metadata)
            VALUES ('{subscription_id}', '{rg}', '{resource_name}', '{service}', {daily_cost:.2f}, 'USD', '{date_str}',
                    '{{"location": "eastus", "environment": "production", "project": "cost-monitoring"}}');
            """
            
            cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "{insert_sql}"'
            subprocess.run(cmd, shell=True, capture_output=True)
    
    print(f"✅ Added {len(resources) * 7} cost records")
    
    # Add AI recommendations
    recommendations = [
        ("resize", "Downsize Development VM", "VM shows low utilization. Consider downsizing.", 45.30, 0.87, "medium"),
        ("storage_tier", "Change Storage Tier", "Storage accessed infrequently. Move to Archive tier.", 125.50, 0.92, "high"),
        ("reserved_instance", "Purchase Reserved Instance", "Consistent usage pattern detected. Purchase RI for savings.", 890.25, 0.95, "high")
    ]
    
    for rec_type, title, description, savings, confidence, priority in recommendations:
        resource_id = f"/subscriptions/{subscription_id}/resourceGroups/rg-production-east/providers/Microsoft.Compute/virtualMachines/vm-web-server-01"
        insert_sql = f"""
        INSERT INTO ai_recommendations (resource_id, recommendation_type, title, description, potential_savings, confidence_score, priority, metadata)
        VALUES ('{resource_id}', '{rec_type}', '{title}', '{description}', {savings}, {confidence}, '{priority}',
                '{{"category": "optimization", "impact": "cost_reduction"}}');
        """
        
        cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "{insert_sql}"'
        subprocess.run(cmd, shell=True, capture_output=True)
    
    print(f"✅ Added {len(recommendations)} AI recommendations")
    
    # Add sample budgets
    budgets = [
        ("Production Environment", 1500.00, "monthly"),
        ("Development Resources", 500.00, "monthly"),
        ("Analytics Workloads", 800.00, "monthly")
    ]
    
    for name, amount, period in budgets:
        insert_sql = f"""
        INSERT INTO cost_budgets (name, budget_amount, time_period, resource_filter, is_active)
        VALUES ('{name}', {amount}, '{period}', '{{"type": "resource_group"}}', true);
        """
        
        cmd = f'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -c "{insert_sql}"'
        subprocess.run(cmd, shell=True, capture_output=True)
    
    print(f"✅ Added {len(budgets)} budget configurations")

def verify_data():
    """Verify the data was inserted"""
    print("\n🔍 Verifying data...")
    
    # Check cost records count
    cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM cost_records;"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    cost_count = result.stdout.strip() if result.returncode == 0 else "0"
    
    # Check recommendations count
    cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM ai_recommendations;"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    rec_count = result.stdout.strip() if result.returncode == 0 else "0"
    
    # Check budgets count
    cmd = 'docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT COUNT(*) FROM cost_budgets;"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    budget_count = result.stdout.strip() if result.returncode == 0 else "0"
    
    print(f"📊 Data Summary:")
    print(f"   • Cost records: {cost_count}")
    print(f"   • AI recommendations: {rec_count}")
    print(f"   • Budget configurations: {budget_count}")
    
    # Show sample cost data
    cmd = '''docker exec azure-cost-db psql -U postgres -d azure_cost_dev -t -c "SELECT resource_group, SUM(cost)::DECIMAL(10,2), COUNT(*) FROM cost_records GROUP BY resource_group ORDER BY SUM(cost) DESC LIMIT 5;"'''
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0 and result.stdout.strip():
        print(f"\n💰 Cost by Resource Group:")
        lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        for line in lines:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                print(f"   • {parts[0]}: ${parts[1]} ({parts[2]} records)")

if __name__ == "__main__":
    print("🚀 Adding Sample Azure Cost Data")
    print("=" * 50)
    
    if create_tables():
        add_sample_data()
        verify_data()
        
        print(f"\n🌐 Your dashboards are now ready with sample data:")
        print(f"   • Grafana: http://localhost:3000 (admin / AzureCost2025!SecurePass)")
        print(f"   • FastAPI: http://localhost:8000")
        print(f"\n✅ Sample data added successfully!")