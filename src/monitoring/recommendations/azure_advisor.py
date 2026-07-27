"""
Azure Advisor Integration Module

Fetches official cost optimization recommendations from Azure Advisor API.
Azure Advisor is Microsoft's official recommendation engine for best practices.

Official Documentation:
https://learn.microsoft.com/en-us/azure/advisor/advisor-overview
https://learn.microsoft.com/en-us/azure/advisor/advisor-cost-recommendations
"""

from typing import List, Dict, Optional
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.advisor import AdvisorManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from pydantic import BaseModel
import os


class AzureAdvisorRecommendation(BaseModel):
    """Official Azure Advisor recommendation."""
    
    id: str
    name: str
    resource_type: str
    category: str  # Cost, Security, Reliability, Performance, OperationalExcellence
    impact: str  # High, Medium, Low
    description: str
    recommendation: str
    potential_savings: Optional[float] = None
    potential_savings_currency: Optional[str] = "USD"
    action_url: str
    suppression_ids: List[str] = []


class AzureAdvisorClient:
    """Client for fetching Azure Advisor recommendations."""
    
    def __init__(
        self,
        subscription_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Azure Advisor client.
        
        Authentication Methods:
        1. DefaultAzureCredential (Azure CLI, Managed Identity, Environment Variables)
        2. Service Principal (tenant_id, client_id, client_secret)
        
        Environment Variables:
        - AZURE_SUBSCRIPTION_ID
        - AZURE_TENANT_ID
        - AZURE_CLIENT_ID
        - AZURE_CLIENT_SECRET
        """
        self.subscription_id = subscription_id or os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not self.subscription_id:
            raise ValueError(
                "Azure Subscription ID is required. Set AZURE_SUBSCRIPTION_ID environment variable "
                "or pass subscription_id parameter."
            )
        
        # Authentication
        if tenant_id and client_id and client_secret:
            # Service Principal authentication
            self.credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            print("✓ Using Service Principal authentication")
        else:
            # Default Azure credential (tries multiple methods)
            self.credential = DefaultAzureCredential()
            print("✓ Using DefaultAzureCredential authentication")
        
        # Initialize clients
        self.advisor_client = AdvisorManagementClient(
            credential=self.credential,
            subscription_id=self.subscription_id
        )
        
        self.resource_graph_client = ResourceGraphClient(
            credential=self.credential
        )
        
        print(f"✓ Connected to Azure subscription: {self.subscription_id[:8]}...")
    
    def get_cost_recommendations(
        self,
        filter_by_impact: Optional[List[str]] = None
    ) -> List[AzureAdvisorRecommendation]:
        """
        Fetch cost optimization recommendations from Azure Advisor.
        
        Args:
            filter_by_impact: Filter by impact level (High, Medium, Low)
        
        Returns:
            List of official Azure cost recommendations
        """
        try:
            print("\n🔍 Fetching Azure Advisor cost recommendations...")
            
            # Get all recommendations
            recommendations = self.advisor_client.recommendations.list(
                filter=f"Category eq 'Cost'"
            )
            
            results = []
            for rec in recommendations:
                # Extract potential savings
                potential_savings = None
                currency = "USD"
                
                if rec.extended_properties:
                    savings_amount = rec.extended_properties.get('savingsAmount')
                    savings_currency = rec.extended_properties.get('savingsCurrency')
                    
                    if savings_amount:
                        try:
                            potential_savings = float(savings_amount)
                            currency = savings_currency or "USD"
                        except (ValueError, TypeError):
                            pass
                
                # Filter by impact if specified
                if filter_by_impact and rec.impact not in filter_by_impact:
                    continue
                
                advisor_rec = AzureAdvisorRecommendation(
                    id=rec.id,
                    name=rec.name,
                    resource_type=rec.impacted_field or "Unknown",
                    category=rec.category,
                    impact=rec.impact,
                    description=rec.short_description.problem if rec.short_description else "No description",
                    recommendation=rec.short_description.solution if rec.short_description else "See Azure portal",
                    potential_savings=potential_savings,
                    potential_savings_currency=currency,
                    action_url=f"https://portal.azure.com/#blade/Microsoft_Azure_Expert/AdvisorMenuBlade/Cost",
                    suppression_ids=rec.suppression_ids if rec.suppression_ids else []
                )
                
                results.append(advisor_rec)
                
                print(f"  ✓ {rec.impact} impact: {advisor_rec.description[:80]}...")
            
            print(f"\n✓ Found {len(results)} cost optimization recommendations")
            return results
            
        except Exception as e:
            print(f"⚠️  Failed to fetch Azure Advisor recommendations: {e}")
            print("   Make sure you have proper Azure credentials and permissions.")
            print("   Required permissions: Reader role on subscription")
            return []
    
    def get_resource_costs(self, resource_type: Optional[str] = None) -> List[Dict]:
        """
        Query actual Azure resource costs using Resource Graph.
        
        Args:
            resource_type: Filter by resource type (e.g., 'Microsoft.Compute/virtualMachines')
        
        Returns:
            List of resources with cost information
        """
        try:
            print("\n🔍 Querying Azure resources using Resource Graph...")
            
            # Build query
            query = """
            Resources
            | where type != 'microsoft.resources/subscriptions'
            | extend resourceType = type
            | project id, name, type, location, resourceGroup, subscriptionId
            | limit 100
            """
            
            if resource_type:
                query = query.replace(
                    "| where type != 'microsoft.resources/subscriptions'",
                    f"| where type =~ '{resource_type}'"
                )
            
            # Execute query
            request = QueryRequest(
                subscriptions=[self.subscription_id],
                query=query
            )
            
            response = self.resource_graph_client.resources(request)
            
            resources = []
            if response.data:
                for row in response.data:
                    resources.append({
                        'id': row.get('id'),
                        'name': row.get('name'),
                        'type': row.get('type'),
                        'location': row.get('location'),
                        'resource_group': row.get('resourceGroup')
                    })
            
            print(f"✓ Found {len(resources)} resources")
            return resources
            
        except Exception as e:
            print(f"⚠️  Failed to query resources: {e}")
            return []
    
    def get_summary_statistics(self) -> Dict:
        """Get summary statistics of recommendations."""
        recommendations = self.get_cost_recommendations()
        
        if not recommendations:
            return {
                'total_recommendations': 0,
                'high_impact': 0,
                'medium_impact': 0,
                'low_impact': 0,
                'total_potential_savings': 0.0
            }
        
        total_savings = sum(
            rec.potential_savings for rec in recommendations 
            if rec.potential_savings is not None
        )
        
        return {
            'total_recommendations': len(recommendations),
            'high_impact': sum(1 for r in recommendations if r.impact == 'High'),
            'medium_impact': sum(1 for r in recommendations if r.impact == 'Medium'),
            'low_impact': sum(1 for r in recommendations if r.impact == 'Low'),
            'total_potential_savings': round(total_savings, 2)
        }


async def main():
    """Test Azure Advisor integration."""
    print("=" * 70)
    print("🔷 Azure Advisor Integration - Official Cost Recommendations")
    print("=" * 70)
    
    try:
        # Initialize client
        client = AzureAdvisorClient()
        
        # Get recommendations
        recommendations = client.get_cost_recommendations(
            filter_by_impact=['High', 'Medium']
        )
        
        if not recommendations:
            print("\n⚠️  No recommendations found or authentication failed.")
            print("   To test with real Azure data:")
            print("   1. Set AZURE_SUBSCRIPTION_ID environment variable")
            print("   2. Login with: az login")
            print("   3. Run this script again")
            return
        
        # Display recommendations
        print("\n" + "=" * 70)
        print("💰 OFFICIAL AZURE ADVISOR COST RECOMMENDATIONS")
        print("=" * 70)
        
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. [{rec.impact.upper()} IMPACT] {rec.description}")
            print(f"   Resource: {rec.resource_type}")
            print(f"   Recommendation: {rec.recommendation}")
            
            if rec.potential_savings:
                print(f"   💰 Potential Savings: {rec.potential_savings_currency} ${rec.potential_savings:,.2f}")
            
            print(f"   📖 View in Portal: {rec.action_url}")
        
        # Summary
        stats = client.get_summary_statistics()
        print("\n" + "=" * 70)
        print("📊 SUMMARY")
        print("=" * 70)
        print(f"Total Recommendations: {stats['total_recommendations']}")
        print(f"High Impact: {stats['high_impact']}")
        print(f"Medium Impact: {stats['medium_impact']}")
        print(f"Low Impact: {stats['low_impact']}")
        print(f"Total Potential Savings: ${stats['total_potential_savings']:,.2f}")
        
    except ValueError as e:
        print(f"\n⚠️  Configuration Error: {e}")
        print("\nQuick Setup:")
        print("1. Set your Azure Subscription ID:")
        print("   $env:AZURE_SUBSCRIPTION_ID='your-subscription-id'")
        print("2. Login to Azure CLI:")
        print("   az login")
        print("3. Run this script again")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
