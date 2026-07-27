"""
Azure Cost Data Collector
Fetches real cost and usage data from Azure Cost Management API
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.resource import SubscriptionClient
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)


class AzureCostCollector:
    """Collects cost and usage data from Azure subscriptions"""
    
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Azure Cost Collector
        
        Args:
            tenant_id: Azure AD Tenant ID (optional, uses env var AZURE_TENANT_ID)
            client_id: Service Principal Client ID (optional, uses env var AZURE_CLIENT_ID)
            client_secret: Service Principal Secret (optional, uses env var AZURE_CLIENT_SECRET)
        """
        self.tenant_id = tenant_id or os.getenv('AZURE_TENANT_ID')
        self.client_id = client_id or os.getenv('AZURE_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('AZURE_CLIENT_SECRET')
        
        # Initialize credential
        self.credential = self._get_credential()
        
    def _get_credential(self):
        """Get Azure credential using Service Principal or Default credentials"""
        try:
            if self.tenant_id and self.client_id and self.client_secret:
                logger.info("Using Service Principal authentication")
                return ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
            else:
                logger.info("Using Default Azure credential (Azure CLI, Managed Identity, etc.)")
                return DefaultAzureCredential()
        except Exception as e:
            logger.error(f"Failed to initialize Azure credentials: {e}")
            raise
    
    def get_subscriptions(self) -> List[Dict]:
        """
        Get list of all accessible Azure subscriptions
        
        Returns:
            List of subscription dictionaries with id, name, and state
        """
        try:
            subscription_client = SubscriptionClient(self.credential)
            subscriptions = []
            
            for sub in subscription_client.subscriptions.list():
                subscriptions.append({
                    'subscription_id': sub.subscription_id,
                    'display_name': sub.display_name,
                    'state': sub.state,
                    'tenant_id': sub.tenant_id
                })
            
            logger.info(f"Found {len(subscriptions)} subscriptions")
            return subscriptions
            
        except AzureError as e:
            logger.error(f"Error fetching subscriptions: {e}")
            raise
    
    def get_cost_data(
        self,
        subscription_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "Daily"
    ) -> List[Dict]:
        """
        Get cost data for a specific subscription
        
        Args:
            subscription_id: Azure subscription ID
            start_date: Start date for cost query (default: 30 days ago)
            end_date: End date for cost query (default: today)
            granularity: Data granularity - "Daily", "Monthly" (default: Daily)
        
        Returns:
            List of cost records with date, service, resource group, and cost
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        try:
            cost_client = CostManagementClient(self.credential)
            scope = f"/subscriptions/{subscription_id}"
            
            # Build query parameters
            query_body = {
                "type": "Usage",
                "timeframe": "Custom",
                "timePeriod": {
                    "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    "to": end_date.strftime("%Y-%m-%dT23:59:59Z")
                },
                "dataset": {
                    "granularity": granularity,
                    "aggregation": {
                        "totalCost": {
                            "name": "Cost",
                            "function": "Sum"
                        }
                    },
                    "grouping": [
                        {
                            "type": "Dimension",
                            "name": "ServiceName"
                        },
                        {
                            "type": "Dimension",
                            "name": "ResourceGroupName"
                        }
                    ]
                }
            }
            
            logger.info(f"Querying cost data for subscription {subscription_id}")
            result = cost_client.query.usage(scope, query_body)
            
            # Parse results
            cost_data = []
            if result.rows:
                for row in result.rows:
                    # Row format: [cost, date, service_name, resource_group]
                    cost_data.append({
                        'date': row[1] if len(row) > 1 else None,
                        'service_name': row[2] if len(row) > 2 else 'Unknown',
                        'resource_group': row[3] if len(row) > 3 else 'Unknown',
                        'cost': float(row[0]) if row[0] else 0.0,
                        'currency': 'USD',
                        'subscription_id': subscription_id
                    })
            
            logger.info(f"Retrieved {len(cost_data)} cost records")
            return cost_data
            
        except AzureError as e:
            logger.error(f"Error fetching cost data for subscription {subscription_id}: {e}")
            raise
    
    def get_current_month_costs_by_service(
        self,
        subscription_id: str
    ) -> List[Dict]:
        """
        Get current month's costs grouped by service
        
        Args:
            subscription_id: Azure subscription ID
        
        Returns:
            List of dictionaries with service name and total cost
        """
        first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        today = datetime.now()
        
        try:
            cost_client = CostManagementClient(self.credential)
            scope = f"/subscriptions/{subscription_id}"
            
            query_body = {
                "type": "Usage",
                "timeframe": "Custom",
                "timePeriod": {
                    "from": first_day.strftime("%Y-%m-%dT00:00:00Z"),
                    "to": today.strftime("%Y-%m-%dT23:59:59Z")
                },
                "dataset": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {
                            "name": "Cost",
                            "function": "Sum"
                        }
                    },
                    "grouping": [
                        {
                            "type": "Dimension",
                            "name": "ServiceName"
                        }
                    ]
                }
            }
            
            logger.info(f"Querying current month costs by service for subscription {subscription_id}")
            result = cost_client.query.usage(scope, query_body)
            
            service_costs = []
            if result.rows:
                for row in result.rows:
                    # Row format: [cost, service_name]
                    service_costs.append({
                        'service_name': row[1] if len(row) > 1 else 'Unknown',
                        'current_cost': float(row[0]) if row[0] else 0.0,
                        'currency': 'USD',
                        'subscription_id': subscription_id,
                        'period': 'current_month'
                    })
            
            # Sort by cost descending
            service_costs.sort(key=lambda x: x['current_cost'], reverse=True)
            
            logger.info(f"Retrieved costs for {len(service_costs)} services")
            return service_costs
            
        except AzureError as e:
            logger.error(f"Error fetching service costs: {e}")
            raise
    
    def get_resource_costs(
        self,
        subscription_id: str,
        resource_group: Optional[str] = None
    ) -> List[Dict]:
        """
        Get costs by individual resources
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Optional resource group filter
        
        Returns:
            List of resource cost dictionaries
        """
        first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        today = datetime.now()
        
        try:
            cost_client = CostManagementClient(self.credential)
            scope = f"/subscriptions/{subscription_id}"
            
            grouping = [
                {"type": "Dimension", "name": "ResourceId"},
                {"type": "Dimension", "name": "ServiceName"},
                {"type": "Dimension", "name": "ResourceGroupName"}
            ]
            
            # Add resource group filter if specified
            filters = None
            if resource_group:
                filters = {
                    "dimensions": {
                        "name": "ResourceGroupName",
                        "operator": "In",
                        "values": [resource_group]
                    }
                }
            
            query_body = {
                "type": "Usage",
                "timeframe": "Custom",
                "timePeriod": {
                    "from": first_day.strftime("%Y-%m-%dT00:00:00Z"),
                    "to": today.strftime("%Y-%m-%dT23:59:59Z")
                },
                "dataset": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {
                            "name": "Cost",
                            "function": "Sum"
                        }
                    },
                    "grouping": grouping
                }
            }
            
            if filters:
                query_body["dataset"]["filter"] = filters
            
            logger.info(f"Querying resource costs for subscription {subscription_id}")
            result = cost_client.query.usage(scope, query_body)
            
            resource_costs = []
            if result.rows:
                for row in result.rows:
                    # Row format: [cost, resource_id, service_name, resource_group]
                    resource_costs.append({
                        'resource_id': row[1] if len(row) > 1 else 'Unknown',
                        'service_name': row[2] if len(row) > 2 else 'Unknown',
                        'resource_group': row[3] if len(row) > 3 else 'Unknown',
                        'cost': float(row[0]) if row[0] else 0.0,
                        'currency': 'USD',
                        'subscription_id': subscription_id
                    })
            
            # Sort by cost descending
            resource_costs.sort(key=lambda x: x['cost'], reverse=True)
            
            logger.info(f"Retrieved costs for {len(resource_costs)} resources")
            return resource_costs
            
        except AzureError as e:
            logger.error(f"Error fetching resource costs: {e}")
            raise
    
    def get_forecast(
        self,
        subscription_id: str,
        days_ahead: int = 30
    ) -> Dict:
        """
        Get cost forecast for subscription
        
        Args:
            subscription_id: Azure subscription ID
            days_ahead: Number of days to forecast (default: 30)
        
        Returns:
            Dictionary with forecast data
        """
        try:
            cost_client = CostManagementClient(self.credential)
            scope = f"/subscriptions/{subscription_id}"
            
            start_date = datetime.now()
            end_date = start_date + timedelta(days=days_ahead)
            
            query_body = {
                "type": "Usage",
                "timeframe": "Custom",
                "timePeriod": {
                    "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    "to": end_date.strftime("%Y-%m-%dT23:59:59Z")
                },
                "dataset": {
                    "granularity": "Daily",
                    "aggregation": {
                        "totalCost": {
                            "name": "Cost",
                            "function": "Sum"
                        }
                    }
                },
                "includeActualCost": False,
                "includeFreshPartialCost": False
            }
            
            logger.info(f"Querying forecast for subscription {subscription_id}")
            result = cost_client.query.usage(scope, query_body)
            
            forecast_data = {
                'subscription_id': subscription_id,
                'forecast_period_days': days_ahead,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'daily_forecast': []
            }
            
            if result.rows:
                total_forecast = 0
                for row in result.rows:
                    daily_cost = float(row[0]) if row[0] else 0.0
                    total_forecast += daily_cost
                    forecast_data['daily_forecast'].append({
                        'date': row[1] if len(row) > 1 else None,
                        'forecasted_cost': daily_cost
                    })
                
                forecast_data['total_forecasted_cost'] = total_forecast
            
            logger.info(f"Retrieved forecast: ${forecast_data.get('total_forecasted_cost', 0):.2f}")
            return forecast_data
            
        except AzureError as e:
            logger.error(f"Error fetching forecast: {e}")
            raise


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize collector
    collector = AzureCostCollector()
    
    print("\n" + "="*70)
    print("Azure Cost Data Collector - Test Run")
    print("="*70)
    
    try:
        # Get subscriptions
        print("\n1. Fetching subscriptions...")
        subscriptions = collector.get_subscriptions()
        print(f"✅ Found {len(subscriptions)} subscriptions:")
        for sub in subscriptions:
            print(f"   - {sub['display_name']} ({sub['subscription_id']})")
        
        if subscriptions:
            # Use first subscription for testing
            test_sub_id = subscriptions[0]['subscription_id']
            print(f"\n2. Using subscription: {subscriptions[0]['display_name']}")
            
            # Get current month costs by service
            print("\n3. Fetching current month costs by service...")
            service_costs = collector.get_current_month_costs_by_service(test_sub_id)
            print(f"✅ Retrieved costs for {len(service_costs)} services")
            print("\nTop 5 services by cost:")
            for i, service in enumerate(service_costs[:5], 1):
                print(f"   {i}. {service['service_name']}: ${service['current_cost']:.2f}")
            
            # Get cost data for last 7 days
            print("\n4. Fetching last 7 days cost data...")
            start = datetime.now() - timedelta(days=7)
            cost_data = collector.get_cost_data(test_sub_id, start_date=start)
            print(f"✅ Retrieved {len(cost_data)} cost records")
            
            print("\n" + "="*70)
            print("✅ Test completed successfully!")
            print("="*70)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you have:")
        print("1. Azure CLI installed and logged in (az login)")
        print("2. OR set environment variables:")
        print("   - AZURE_TENANT_ID")
        print("   - AZURE_CLIENT_ID")
        print("   - AZURE_CLIENT_SECRET")
