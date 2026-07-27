"""
AI-Powered Cost Recommendation Engine with Official Azure Integrations

Features:
1. Azure Advisor API - Official Microsoft recommendations from your subscription
2. Azure Well-Architected Framework - All 9 cost optimization principles  
3. Azure Pricing API - Real-time pricing and accurate savings calculations
4. Azure OpenAI - Advanced AI-powered analysis (optional)
5. Rule-based fallback - Built-in best practices for offline use

Official Documentation:
- Azure Advisor: https://learn.microsoft.com/en-us/azure/advisor/
- WAF Cost Optimization: https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/
- Azure Pricing API: https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices
"""

import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from openai import AzureOpenAI
from pydantic import BaseModel

# Import official Azure integrations
try:
    from .azure_advisor import AzureAdvisorClient, AzureAdvisorRecommendation
    AZURE_ADVISOR_AVAILABLE = True
except ImportError:
    AZURE_ADVISOR_AVAILABLE = False

try:
    from .azure_waf_cost import AzureWAFCostOptimization, WAFRecommendation
    AZURE_WAF_AVAILABLE = True
except ImportError:
    AZURE_WAF_AVAILABLE = False

try:
    from .azure_pricing import AzurePricingClient
    AZURE_PRICING_AVAILABLE = True
except ImportError:
    AZURE_PRICING_AVAILABLE = False


class CostRecommendation(BaseModel):
    """Cost optimization recommendation."""
    service_name: str
    current_cost: float
    potential_savings: float
    recommendation: str
    priority: str  # high, medium, low
    action_items: List[str]
    estimated_effort: str


class AIRecommendationEngine:
    """
    Enhanced AI-powered recommendation engine with official Azure integrations.
    
    Recommendation Sources (in priority order):
    1. Azure Advisor API - Real recommendations from your Azure subscription
    2. Azure Well-Architected Framework - Microsoft's 9 cost optimization principles
    3. Azure Pricing API - Real-time pricing for accurate savings calculations
    4. Azure OpenAI - Advanced AI analysis (optional)
    5. Rule-based - Built-in best practices (fallback)
    """
    
    def __init__(self, use_azure_services: bool = True):
        """
        Initialize the recommendation engine.
        
        Args:
            use_azure_services: Enable Azure Advisor, WAF, and Pricing integrations
        """
        # Azure OpenAI setup (optional)
        self.openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.openai_key = os.environ.get("AZURE_OPENAI_KEY")
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        
        if self.openai_endpoint and self.openai_key:
            self.client = AzureOpenAI(
                api_key=self.openai_key,
                api_version="2024-02-01",
                azure_endpoint=self.openai_endpoint
            )
            print("✓ Azure OpenAI configured")
        else:
            self.client = None
            print("⚠️  Azure OpenAI not configured - using rule-based recommendations")
        
        # Initialize Azure service integrations
        self.use_azure_services = use_azure_services
        self.advisor_client = None
        self.waf_engine = None
        self.pricing_client = None
        
        if use_azure_services:
            # Azure Advisor client
            if AZURE_ADVISOR_AVAILABLE:
                try:
                    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
                    if subscription_id:
                        self.advisor_client = AzureAdvisorClient(subscription_id=subscription_id)
                        print("✓ Azure Advisor client initialized")
                    else:
                        print("⚠️  AZURE_SUBSCRIPTION_ID not set - Advisor disabled")
                except Exception as e:
                    print(f"⚠️  Failed to initialize Azure Advisor: {e}")
            
            # Azure Well-Architected Framework engine
            if AZURE_WAF_AVAILABLE:
                self.waf_engine = AzureWAFCostOptimization()
                print("✓ Azure WAF Cost Optimization initialized")
            
            # Azure Pricing client
            if AZURE_PRICING_AVAILABLE:
                self.pricing_client = AzurePricingClient()
                print("✓ Azure Pricing API client initialized")
        
        # Database setup
        self.db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///test_cost_system.db")
        self.engine = create_async_engine(self.db_url, echo=False)
        self.AsyncSessionLocal = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def get_high_cost_services(self, days: int = 30) -> List[Dict]:
        """Get services with highest costs."""
        async with self.AsyncSessionLocal() as session:
            result = await session.execute(text(f"""
                SELECT 
                    service_name,
                    ROUND(SUM(cost), 2) as total_cost,
                    COUNT(*) as record_count,
                    ROUND(AVG(cost), 2) as avg_cost,
                    ROUND(MAX(cost), 2) as max_cost
                FROM cost_records
                WHERE timestamp >= datetime('now', '-{days} days')
                GROUP BY service_name
                HAVING total_cost > 100
                ORDER BY total_cost DESC
            """))
            
            services = []
            for row in result.fetchall():
                services.append({
                    "service_name": row[0],
                    "total_cost": float(row[1]),
                    "record_count": row[2],
                    "avg_cost": float(row[3]),
                    "max_cost": float(row[4])
                })
            
            return services
    
    def _generate_rule_based_recommendations(
        self, service: Dict
    ) -> CostRecommendation:
        """Generate recommendations using rule-based logic."""
        service_name = service["service_name"]
        total_cost = service["total_cost"]
        avg_cost = service["avg_cost"]
        
        # Simple rule-based recommendations
        recommendations = {
            "Microsoft.Compute": {
                "recommendation": "Consider using Azure Reserved Instances or Spot VMs for non-critical workloads. Review VM sizes and right-size underutilized instances.",
                "action_items": [
                    "Analyze VM utilization metrics (CPU, memory)",
                    "Identify VMs running <30% utilization",
                    "Purchase Reserved Instances for predictable workloads",
                    "Use Spot VMs for batch processing",
                    "Enable auto-shutdown for dev/test VMs"
                ],
                "potential_savings": total_cost * 0.30  # 30% potential savings
            },
            "Microsoft.Storage": {
                "recommendation": "Implement lifecycle management policies to move data to cooler storage tiers. Delete old snapshots and unused disks.",
                "action_items": [
                    "Review blob storage access patterns",
                    "Move infrequently accessed data to Cool/Archive tier",
                    "Delete old snapshots older than 30 days",
                    "Identify and remove unattached disks",
                    "Enable blob versioning cleanup"
                ],
                "potential_savings": total_cost * 0.25
            },
            "Microsoft.Sql": {
                "recommendation": "Right-size database DTUs/vCores based on actual usage. Consider serverless tier for intermittent workloads.",
                "action_items": [
                    "Monitor DTU/vCore utilization",
                    "Right-size databases with <40% utilization",
                    "Use serverless for dev/test databases",
                    "Enable auto-pause for serverless DBs",
                    "Review and optimize expensive queries"
                ],
                "potential_savings": total_cost * 0.35
            },
            "Microsoft.Web": {
                "recommendation": "Optimize App Service plans by consolidating apps. Use consumption-based plans for low-traffic apps.",
                "action_items": [
                    "Consolidate multiple apps into fewer plans",
                    "Use consumption plans for Functions",
                    "Enable auto-scaling to handle traffic spikes",
                    "Review and remove unused slots",
                    "Consider Linux plans for lower costs"
                ],
                "potential_savings": total_cost * 0.20
            },
            "Microsoft.Network": {
                "recommendation": "Reduce data transfer costs by using CDN and optimizing data movement patterns.",
                "action_items": [
                    "Implement Azure CDN for static content",
                    "Optimize cross-region data transfers",
                    "Use ExpressRoute for high-volume transfers",
                    "Review and remove unused public IPs",
                    "Consolidate VNet peering connections"
                ],
                "potential_savings": total_cost * 0.15
            }
        }
        
        default_rec = {
            "recommendation": f"Review {service_name} usage patterns and implement cost optimization best practices.",
            "action_items": [
                f"Audit {service_name} resources",
                "Identify underutilized or unused resources",
                "Implement resource tagging for cost allocation",
                "Set up budget alerts",
                "Review service tier and pricing options"
            ],
            "potential_savings": total_cost * 0.20
        }
        
        rec = recommendations.get(service_name, default_rec)
        
        # Determine priority
        if total_cost > 500:
            priority = "high"
        elif total_cost > 200:
            priority = "medium"
        else:
            priority = "low"
        
        return CostRecommendation(
            service_name=service_name,
            current_cost=total_cost,
            potential_savings=round(rec["potential_savings"], 2),
            recommendation=rec["recommendation"],
            priority=priority,
            action_items=rec["action_items"],
            estimated_effort="2-4 hours"
        )
    
    async def _generate_ai_recommendations(
        self, service: Dict
    ) -> CostRecommendation:
        """
        Generate recommendations using Azure OpenAI GPT-4.
        
        Uses advanced AI to provide context-aware, specific recommendations
        based on usage patterns and Azure best practices.
        """
        if not self.client:
            return self._generate_rule_based_recommendations(service)
        
        # Enhanced prompt with Azure-specific context
        usage_pattern = 'consistent' if service['avg_cost'] * 1.5 > service['max_cost'] else 'variable with spikes'
        cost_level = 'high' if service['total_cost'] > 500 else 'medium' if service['total_cost'] > 200 else 'low'
        
        prompt = f"""You are a Microsoft Azure cost optimization expert with deep knowledge of Azure services, pricing models, and the Well-Architected Framework.

ANALYZE THIS AZURE SERVICE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service Type: {service['service_name']}
Monthly Cost: ${service['total_cost']:.2f} (${service['total_cost'] * 12:.2f}/year)
Usage Pattern: {usage_pattern}
Cost Level: {cost_level}
Average per Record: ${service['avg_cost']:.2f}
Peak Cost: ${service['max_cost']:.2f}
Number of Records: {service['record_count']}

PROVIDE EXPERT AZURE COST OPTIMIZATION:

1. **Specific Recommendation** (2-3 sentences):
   - Name exact Azure services/features (e.g., "Azure SQL Serverless", "Reserved VM Instances", "Spot VMs")
   - Be specific about SKUs, tiers, or pricing models
   - Reference Azure Well-Architected Framework principles

2. **Potential Savings Percentage** (realistic based on Azure pricing):
   - Reserved Instances: 40-72% savings
   - Spot VMs: 60-90% savings
   - Serverless: 30-70% savings during idle
   - Right-sizing: 20-40% savings
   - Storage tiering: 30-50% savings

3. **Priority Level**:
   - "high" if monthly cost > $500 OR potential savings > 40%
   - "medium" if cost $200-500 OR savings 20-40%
   - "low" if cost < $200 OR savings < 20%

4. **Action Items** (3-5 specific steps):
   - Include Azure portal navigation paths
   - Provide Azure CLI commands where applicable
   - Reference Azure Advisor recommendations
   - Include monitoring/validation steps

5. **Implementation Effort**: Realistic estimate (e.g., "30 minutes", "1-2 hours", "2-4 hours")

OUTPUT (valid JSON only, no markdown or explanation):
{{
    "recommendation": "Your specific Azure recommendation here",
    "potential_savings_percent": 35,
    "priority": "high",
    "action_items": [
        "Navigate to Azure portal > Cost Management + Billing > Reservations",
        "Review Azure Advisor cost recommendations for this service",
        "Purchase 3-year Reserved Instance for production workloads",
        "Enable auto-shutdown for dev/test resources",
        "Monitor savings using Azure Cost Analysis"
    ],
    "estimated_effort": "2-3 hours"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an Azure cloud cost optimization expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Parse AI response
            import json
            ai_response = json.loads(response.choices[0].message.content)
            
            potential_savings = service['total_cost'] * (ai_response.get('potential_savings_percent', 20) / 100)
            
            return CostRecommendation(
                service_name=service['service_name'],
                current_cost=service['total_cost'],
                potential_savings=round(potential_savings, 2),
                recommendation=ai_response.get('recommendation', 'Optimize resource usage'),
                priority=ai_response.get('priority', 'medium'),
                action_items=ai_response.get('action_items', []),
                estimated_effort=ai_response.get('estimated_effort', '2-4 hours')
            )
            
        except Exception as e:
            print(f"⚠️  AI recommendation failed: {e}, falling back to rules")
            return self._generate_rule_based_recommendations(service)
    
    async def generate_all_recommendations(
        self, use_ai: bool = True, force_ai: bool = False
    ) -> List[CostRecommendation]:
        """
        Generate recommendations for all high-cost services.
        
        Args:
            use_ai: Use AI-powered recommendations (default: True)
            force_ai: Require AI (fail if Azure OpenAI not configured)
        
        Returns:
            List of cost recommendations
        """
        services = await self.get_high_cost_services()
        recommendations = []
        
        # Check if AI is required but not available
        if force_ai and not self.client:
            raise ValueError(
                "AI-based recommendations requested but Azure OpenAI is not configured.\n"
                "Please set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, and AZURE_OPENAI_DEPLOYMENT "
                "environment variables."
            )
        
        recommendation_method = "AI-powered" if (use_ai and self.client) else "rule-based"
        print(f"\n🤖 Generating {recommendation_method} recommendations for {len(services)} services...")
        
        for service in services:
            if use_ai and self.client:
                rec = await self._generate_ai_recommendations(service)
            else:
                rec = self._generate_rule_based_recommendations(service)
            
            recommendations.append(rec)
            print(f"  ✓ {service['service_name']}: ${rec.potential_savings:.2f} potential savings")
        
        # Sort by potential savings
        recommendations.sort(key=lambda x: x.potential_savings, reverse=True)
        
        return recommendations
    
    async def generate_comprehensive_recommendations(
        self,
        include_advisor: bool = True,
        include_waf: bool = True,
        include_pricing: bool = True
    ) -> Dict:
        """
        Generate comprehensive recommendations from all sources.
        
        This is the MAIN METHOD that combines all official Azure sources:
        - Azure Advisor: Official recommendations from your subscription
        - Well-Architected Framework: Microsoft's cost optimization principles
        - Azure Pricing: Real-time pricing and savings calculations
        - AI/Rule-based: Enhanced recommendations
        
        Returns:
            Dictionary with recommendations from all sources
        """
        print("\n" + "=" * 70)
        print("🔷 COMPREHENSIVE AZURE COST RECOMMENDATIONS")
        print("=" * 70)
        
        result = {
            "advisor_recommendations": [],
            "waf_recommendations": [],
            "pricing_insights": {},
            "ai_recommendations": [],
            "summary": {}
        }
        
        # 1. Azure Advisor - Official Microsoft Recommendations
        if include_advisor and self.advisor_client:
            print("\n📋 Fetching Azure Advisor recommendations...")
            try:
                advisor_recs = self.advisor_client.get_cost_recommendations(
                    filter_by_impact=['High', 'Medium']
                )
                result["advisor_recommendations"] = [
                    {
                        "source": "Azure Advisor (Official)",
                        "impact": rec.impact,
                        "description": rec.description,
                        "recommendation": rec.recommendation,
                        "potential_savings": rec.potential_savings,
                        "currency": rec.potential_savings_currency,
                        "documentation": rec.action_url
                    }
                    for rec in advisor_recs
                ]
                print(f"   ✓ Found {len(advisor_recs)} official Azure Advisor recommendations")
            except Exception as e:
                print(f"   ⚠️  Advisor API failed: {e}")
        
        # 2. Well-Architected Framework - Microsoft's Best Practices
        if include_waf and self.waf_engine:
            print("\n🏗️  Applying Azure Well-Architected Framework principles...")
            services = await self.get_high_cost_services()
            waf_recs = []
            
            for service in services[:5]:  # Top 5 services
                service_waf = self.waf_engine.get_recommendations_by_service(
                    service_type=service['service_name'],
                    current_cost=service['total_cost']
                )
                
                for waf_rec in service_waf:
                    waf_recs.append({
                        "source": "Azure Well-Architected Framework",
                        "principle": waf_rec.principle_name,
                        "service": service['service_name'],
                        "recommendation": waf_rec.recommendation,
                        "rationale": waf_rec.rationale,
                        "priority": waf_rec.priority,
                        "savings_percent": waf_rec.estimated_savings_percent,
                        "effort": waf_rec.implementation_effort,
                        "action_items": waf_rec.action_items,
                        "documentation": waf_rec.documentation_url
                    })
            
            result["waf_recommendations"] = waf_recs
            print(f"   ✓ Generated {len(waf_recs)} WAF-based recommendations")
        
        # 3. Azure Pricing API - Real-time Savings Calculations
        if include_pricing and self.pricing_client:
            print("\n💰 Calculating savings with Azure Pricing API...")
            services = await self.get_high_cost_services()
            
            total_current_cost = sum(s['total_cost'] for s in services)
            
            # Calculate reservation savings
            reservation_1yr = self.pricing_client.calculate_reservation_savings(
                service_name="Virtual Machines",
                current_monthly_cost=total_current_cost,
                reservation_term=1
            )
            
            reservation_3yr = self.pricing_client.calculate_reservation_savings(
                service_name="Virtual Machines",
                current_monthly_cost=total_current_cost,
                reservation_term=3
            )
            
            # Calculate spot VM savings
            spot_savings = self.pricing_client.calculate_spot_vm_savings(
                current_monthly_cost=total_current_cost,
                eviction_rate="medium"
            )
            
            result["pricing_insights"] = {
                "current_monthly_cost": total_current_cost,
                "reservation_1_year": reservation_1yr,
                "reservation_3_year": reservation_3yr,
                "spot_vms": spot_savings,
                "documentation": "https://learn.microsoft.com/en-us/azure/cost-management-billing/"
            }
            print(f"   ✓ Calculated potential savings scenarios")
        
        # 4. AI-Powered Recommendations (using Azure OpenAI if available)
        ai_mode = "AI-powered (Azure OpenAI)" if self.client else "Rule-based (Azure OpenAI not configured)"
        print(f"\n🤖 Generating {ai_mode} recommendations...")
        
        # Use AI by default (will use rule-based as fallback if OpenAI not configured)
        ai_recs = await self.generate_all_recommendations(use_ai=True)
        
        source_name = "AI Engine (Azure OpenAI GPT-4)" if self.client else "AI Engine (Rule-based)"
        result["ai_recommendations"] = [
            {
                "source": source_name,
                "service": rec.service_name,
                "current_cost": rec.current_cost,
                "potential_savings": rec.potential_savings,
                "recommendation": rec.recommendation,
                "priority": rec.priority,
                "action_items": rec.action_items,
                "effort": rec.estimated_effort
            }
            for rec in ai_recs
        ]
        print(f"   ✓ Generated {len(ai_recs)} recommendations using {ai_mode}")
        
        # Summary
        total_advisor_savings = sum(
            r.get("potential_savings", 0) or 0 
            for r in result["advisor_recommendations"]
        )
        
        total_ai_savings = sum(
            r["potential_savings"] for r in result["ai_recommendations"]
        )
        
        result["summary"] = {
            "total_recommendations": (
                len(result["advisor_recommendations"]) +
                len(result["waf_recommendations"]) +
                len(result["ai_recommendations"])
            ),
            "advisor_count": len(result["advisor_recommendations"]),
            "waf_count": len(result["waf_recommendations"]),
            "ai_count": len(result["ai_recommendations"]),
            "total_potential_monthly_savings": round(total_advisor_savings + total_ai_savings, 2),
            "sources": [
                "Azure Advisor (Official Microsoft)",
                "Azure Well-Architected Framework",
                "Azure Pricing API",
                "AI Engine"
            ]
        }
        
        print("\n" + "=" * 70)
        print("✓ Comprehensive recommendations generated!")
        print("=" * 70)
        
        return result


async def main():
    """
    Test the enhanced recommendation engine with all Azure integrations.
    
    This demonstrates the comprehensive recommendation system that combines:
    1. Azure Advisor - Official recommendations from Microsoft
    2. Azure Well-Architected Framework - Cost optimization principles
    3. Azure Pricing API - Real-time pricing and savings
    4. AI/Rule-based - Enhanced recommendations
    """
    print("=" * 80)
    print("🔷 ENHANCED AI COST RECOMMENDATION ENGINE")
    print("   with Official Azure Integrations")
    print("=" * 80)
    
    # Initialize engine with Azure integrations
    engine = AIRecommendationEngine(use_azure_services=True)
    
    # Generate comprehensive recommendations from all sources
    result = await engine.generate_comprehensive_recommendations(
        include_advisor=True,
        include_waf=True,
        include_pricing=True
    )
    
    # Display results
    print("\n" + "=" * 80)
    print("📋 RECOMMENDATIONS BY SOURCE")
    print("=" * 80)
    
    # 1. Azure Advisor Recommendations
    if result["advisor_recommendations"]:
        print("\n🔷 AZURE ADVISOR (Official Microsoft Recommendations)")
        print("-" * 80)
        for i, rec in enumerate(result["advisor_recommendations"][:5], 1):
            print(f"\n{i}. [{rec['impact'].upper()} IMPACT]")
            print(f"   {rec['description']}")
            print(f"   � {rec['recommendation']}")
            if rec['potential_savings']:
                print(f"   💰 Savings: {rec['currency']} ${rec['potential_savings']:,.2f}")
            print(f"   📖 {rec['documentation']}")
    else:
        print("\n🔷 AZURE ADVISOR")
        print("-" * 80)
        print("   ℹ️  No Advisor recommendations (requires Azure subscription configuration)")
        print("   Set AZURE_SUBSCRIPTION_ID and authenticate with 'az login'")
    
    # 2. Well-Architected Framework Recommendations
    if result["waf_recommendations"]:
        print("\n\n🏗️  AZURE WELL-ARCHITECTED FRAMEWORK")
        print("-" * 80)
        for i, rec in enumerate(result["waf_recommendations"][:5], 1):
            print(f"\n{i}. [{rec['priority'].upper()}] {rec['principle']}")
            print(f"   Service: {rec['service']}")
            print(f"   💡 {rec['recommendation']}")
            print(f"   💰 Potential Savings: {rec['savings_percent']}%")
            print(f"   ⏱️  Effort: {rec['effort']}")
            print(f"   📖 {rec['documentation']}")
            print(f"   Action Items:")
            for action in rec['action_items'][:3]:
                print(f"     • {action}")
    
    # 3. Azure Pricing Insights
    if result["pricing_insights"]:
        insights = result["pricing_insights"]
        print("\n\n💰 AZURE PRICING API - SAVINGS SCENARIOS")
        print("-" * 80)
        print(f"\nCurrent Monthly Cost: ${insights['current_monthly_cost']:,.2f}")
        
        if "reservation_1_year" in insights:
            res1 = insights["reservation_1_year"]
            print(f"\n📅 1-Year Reserved Instances:")
            print(f"   Monthly: ${res1['reservation_monthly_cost']:,.2f}")
            print(f"   Savings: ${res1['monthly_savings']:,.2f}/month ({res1['discount_percent']}%)")
            print(f"   Total Savings: ${res1['total_term_savings']:,.2f} over 1 year")
        
        if "reservation_3_year" in insights:
            res3 = insights["reservation_3_year"]
            print(f"\n📅 3-Year Reserved Instances:")
            print(f"   Monthly: ${res3['reservation_monthly_cost']:,.2f}")
            print(f"   Savings: ${res3['monthly_savings']:,.2f}/month ({res3['discount_percent']}%)")
            print(f"   Total Savings: ${res3['total_term_savings']:,.2f} over 3 years")
        
        if "spot_vms" in insights:
            spot = insights["spot_vms"]
            print(f"\n⚡ Spot VMs (for fault-tolerant workloads):")
            print(f"   Monthly: ${spot['spot_monthly_cost']:,.2f}")
            print(f"   Savings: ${spot['monthly_savings']:,.2f}/month ({spot['discount_percent']}%)")
            print(f"   Best For: {spot['suitability']}")
        
        print(f"\n📖 {insights['documentation']}")
    
    # 4. AI/Rule-based Recommendations
    if result["ai_recommendations"]:
        print("\n\n🤖 AI ENGINE RECOMMENDATIONS")
        print("-" * 80)
        for i, rec in enumerate(result["ai_recommendations"][:5], 1):
            print(f"\n{i}. {rec['service']} [{rec['priority'].upper()}]")
            print(f"   Current Cost: ${rec['current_cost']:,.2f}")
            print(f"   💰 Potential Savings: ${rec['potential_savings']:,.2f}")
            print(f"   💡 {rec['recommendation']}")
            print(f"   ⏱️  Effort: {rec['effort']}")
            print(f"   Action Items:")
            for action in rec['action_items'][:3]:
                print(f"     • {action}")
    
    # Summary
    summary = result["summary"]
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total Recommendations: {summary['total_recommendations']}")
    print(f"  - Azure Advisor: {summary['advisor_count']}")
    print(f"  - Well-Architected Framework: {summary['waf_count']}")
    print(f"  - AI Engine: {summary['ai_count']}")
    print(f"\n💰 Total Potential Monthly Savings: ${summary['total_potential_monthly_savings']:,.2f}")
    print(f"\nRecommendation Sources:")
    for source in summary['sources']:
        print(f"  ✓ {source}")
    
    print("\n" + "=" * 80)
    print("✓ All recommendations generated successfully!")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
