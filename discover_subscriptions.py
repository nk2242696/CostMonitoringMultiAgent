"""
Azure Subscription Discovery Tool

Use this script to discover available Azure subscriptions and configure
the multi-subscription cost collector.
"""

import os
import sys
from datetime import datetime
from typing import List, Dict

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.monitoring.azure_cost_collector import AzureCostCollector


def discover_subscriptions():
    """Discover and display available Azure subscriptions"""
    
    print("🔍 AZURE SUBSCRIPTION DISCOVERY")
    print("=" * 60)
    
    try:
        # Initialize collector
        collector = AzureCostCollector()
        
        print("📡 Connecting to Azure...")
        subscriptions = collector.get_subscriptions()
        
        if not subscriptions:
            print("❌ No subscriptions found!")
            print("\n💡 Make sure you have:")
            print("   1. Azure CLI installed and logged in: az login")
            print("   2. OR environment variables set:")
            print("      - AZURE_TENANT_ID")
            print("      - AZURE_CLIENT_ID") 
            print("      - AZURE_CLIENT_SECRET")
            return []
            
        print(f"✅ Found {len(subscriptions)} subscriptions:\n")
        
        # Display subscriptions in a table format
        print(f"{'#':<3} {'Name':<40} {'ID':<36} {'State':<10}")
        print("-" * 95)
        
        for i, sub in enumerate(subscriptions, 1):
            print(f"{i:<3} {sub['display_name'][:39]:<40} {sub['subscription_id']:<36} {sub['state']:<10}")
        
        return subscriptions
        
    except Exception as e:
        print(f"❌ Error discovering subscriptions: {e}")
        return []


def test_subscription_access(subscriptions: List[Dict]):
    """Test cost data access for each subscription"""
    
    print(f"\n🧪 TESTING SUBSCRIPTION ACCESS")
    print("=" * 60)
    
    collector = AzureCostCollector()
    accessible_subs = []
    
    for i, sub in enumerate(subscriptions, 1):
        sub_id = sub['subscription_id']
        sub_name = sub['display_name']
        
        print(f"\n{i}. Testing {sub_name}...")
        
        try:
            # Try to get current month costs (quick test)
            costs = collector.get_current_month_costs_by_service(sub_id)
            total_cost = sum(float(cost.get('current_cost', 0)) for cost in costs)
            
            print(f"   ✅ Accessible - {len(costs)} services, ${total_cost:.2f} current month")
            accessible_subs.append({
                'subscription_id': sub_id,
                'subscription_name': sub_name,
                'service_count': len(costs),
                'current_month_cost': total_cost
            })
            
        except Exception as e:
            print(f"   ❌ Not accessible - {str(e)}")
    
    return accessible_subs


def generate_config_file(accessible_subs: List[Dict]):
    """Generate configuration file for multi-subscription collection"""
    
    if not accessible_subs:
        print("\n❌ No accessible subscriptions found. Cannot generate config.")
        return
        
    print(f"\n📝 GENERATING CONFIGURATION")
    print("=" * 60)
    
    config_content = f'''# Multi-Subscription Configuration - Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Configure which Azure subscriptions to collect cost data from

# Discovered Subscriptions ({len(accessible_subs)} accessible):
SUBSCRIPTION_IDS = [
'''
    
    for sub in accessible_subs:
        config_content += f'    "{sub["subscription_id"]}",  # {sub["subscription_name"]} (${sub["current_month_cost"]:.2f}/month)\n'
    
    config_content += ''']

# Azure Authentication Settings
AZURE_TENANT_ID=""     # Leave empty to use Azure CLI auth
AZURE_CLIENT_ID=""
AZURE_CLIENT_SECRET=""

# Collection Settings  
MAX_CONCURRENT_SUBSCRIPTIONS=3  # Adjust based on Azure API limits
DEFAULT_DAYS_BACK=30           # Number of days to collect
BATCH_SIZE=100                 # Database batch size

# Usage Instructions:
# 1. Uncomment the subscription IDs you want to collect from
# 2. Run: python multi_subscription_collector.py
# 3. Or import and use: from multi_subscription_collector import MultiSubscriptionCostCollector
'''
    
    # Save config file
    config_file = "multi_subscription_config_generated.py"
    with open(config_file, 'w') as f:
        f.write(config_content)
        
    print(f"✅ Configuration saved to: {config_file}")
    print(f"\n📋 Summary:")
    print(f"   • {len(accessible_subs)} accessible subscriptions")
    print(f"   • Total monthly cost: ${sum(sub['current_month_cost'] for sub in accessible_subs):.2f}")
    
    print(f"\n🚀 Next Steps:")
    print(f"   1. Review {config_file}")
    print(f"   2. Edit subscription list as needed")
    print(f"   3. Run: python multi_subscription_collector.py")


def main():
    """Main discovery and configuration process"""
    
    print("🎯 AZURE MULTI-SUBSCRIPTION SETUP WIZARD")
    print("=" * 70)
    
    # Step 1: Discover subscriptions
    subscriptions = discover_subscriptions()
    
    if not subscriptions:
        return
        
    # Step 2: Test access to each subscription  
    accessible_subs = test_subscription_access(subscriptions)
    
    if not accessible_subs:
        print("\n❌ No subscriptions are accessible for cost data collection.")
        print("\n💡 This might be due to:")
        print("   • Missing permissions (Cost Management Reader role required)")
        print("   • Authentication issues")
        print("   • Subscription state (must be 'Enabled')")
        return
        
    # Step 3: Generate configuration
    generate_config_file(accessible_subs)
    
    print(f"\n✅ Setup complete! You can now collect cost data from {len(accessible_subs)} subscriptions.")


if __name__ == "__main__":
    main()