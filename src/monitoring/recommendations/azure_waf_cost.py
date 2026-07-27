"""
Azure Well-Architected Framework - Cost Optimization Pillar

Implements all 9 design principles from Microsoft's official WAF Cost Optimization guidance.

Official Documentation:
https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/
https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/principles
"""

from typing import List, Dict, Optional
from pydantic import BaseModel
from enum import Enum


class WAFPrinciple(str, Enum):
    """Azure Well-Architected Framework Cost Optimization Principles."""
    
    # 9 Core Principles
    COST_MODEL = "cost_model"  # Develop a cost model
    ARCHITECTURE = "architecture"  # Design with cost in mind
    MONITOR = "monitor"  # Monitor and optimize
    BUDGET = "budget"  # Establish budgets and alerts
    GOVERNANCE = "governance"  # Implement governance
    EFFICIENCY = "efficiency"  # Optimize resources
    PRICING = "pricing"  # Use pricing models
    AUTOMATION = "automation"  # Automate operations
    CONTINUOUS = "continuous"  # Continuously optimize


class WAFRecommendation(BaseModel):
    """Well-Architected Framework recommendation."""
    
    principle: WAFPrinciple
    principle_name: str
    service_type: str
    recommendation: str
    rationale: str
    action_items: List[str]
    documentation_url: str
    priority: str  # critical, high, medium, low
    estimated_savings_percent: float
    implementation_effort: str
    compliance_tags: List[str] = []


class AzureWAFCostOptimization:
    """
    Azure Well-Architected Framework Cost Optimization recommendations.
    
    Based on Microsoft's official guidance:
    https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/
    """
    
    def __init__(self):
        """Initialize WAF Cost Optimization engine."""
        self.base_url = "https://learn.microsoft.com/en-us/azure/well-architected"
        self.principles = self._load_principles()
    
    def _load_principles(self) -> Dict[WAFPrinciple, Dict]:
        """Load all 9 WAF Cost Optimization principles with details."""
        return {
            WAFPrinciple.COST_MODEL: {
                "name": "Develop cost model and forecasts",
                "description": "Establish a cost model to measure and forecast cloud spend",
                "url": f"{self.base_url}/cost-optimization/cost-model",
                "key_actions": [
                    "Define cost allocation strategy",
                    "Create cost forecasting model",
                    "Implement chargeback/showback",
                    "Track cost per business unit"
                ]
            },
            WAFPrinciple.ARCHITECTURE: {
                "name": "Design with cost optimization in mind",
                "description": "Make cost-effective architectural decisions from the start",
                "url": f"{self.base_url}/cost-optimization/design-review",
                "key_actions": [
                    "Choose cost-effective Azure services",
                    "Design for scale and elasticity",
                    "Minimize data transfer costs",
                    "Leverage serverless where appropriate"
                ]
            },
            WAFPrinciple.MONITOR: {
                "name": "Monitor and optimize continuously",
                "description": "Track spending patterns and optimize regularly",
                "url": f"{self.base_url}/cost-optimization/monitor-optimize",
                "key_actions": [
                    "Set up Azure Cost Management",
                    "Configure cost alerts",
                    "Review cost analysis weekly",
                    "Identify cost anomalies"
                ]
            },
            WAFPrinciple.BUDGET: {
                "name": "Establish budgets and alerts",
                "description": "Set spending limits and get notified of overages",
                "url": f"{self.base_url}/cost-optimization/cost-governance",
                "key_actions": [
                    "Create budgets for each workload",
                    "Configure budget alerts at 50%, 75%, 90%",
                    "Set up action groups for notifications",
                    "Review budget vs. actual monthly"
                ]
            },
            WAFPrinciple.GOVERNANCE: {
                "name": "Implement cost governance",
                "description": "Control and manage cloud spending across organization",
                "url": f"{self.base_url}/cost-optimization/cost-governance",
                "key_actions": [
                    "Use Azure Policy for resource compliance",
                    "Implement resource tagging strategy",
                    "Set up management groups",
                    "Control resource provisioning"
                ]
            },
            WAFPrinciple.EFFICIENCY: {
                "name": "Optimize resource efficiency",
                "description": "Right-size resources and eliminate waste",
                "url": f"{self.base_url}/cost-optimization/optimize-resources",
                "key_actions": [
                    "Right-size VMs based on utilization",
                    "Remove unused resources",
                    "Use autoscaling",
                    "Implement lifecycle policies"
                ]
            },
            WAFPrinciple.PRICING: {
                "name": "Use cost-effective pricing models",
                "description": "Leverage reservations, spots, and hybrid benefits",
                "url": f"{self.base_url}/cost-optimization/pricing-models",
                "key_actions": [
                    "Purchase Azure Reservations (1-3 years)",
                    "Use Spot VMs for fault-tolerant workloads",
                    "Enable Azure Hybrid Benefit",
                    "Consider dev/test pricing"
                ]
            },
            WAFPrinciple.AUTOMATION: {
                "name": "Automate cost operations",
                "description": "Use automation to reduce operational costs",
                "url": f"{self.base_url}/cost-optimization/automation",
                "key_actions": [
                    "Auto-shutdown dev/test resources",
                    "Implement auto-scaling policies",
                    "Use Azure Functions for scheduled tasks",
                    "Automate resource provisioning"
                ]
            },
            WAFPrinciple.CONTINUOUS: {
                "name": "Continuously optimize costs",
                "description": "Regular review and optimization cycles",
                "url": f"{self.base_url}/cost-optimization/optimize-checklist",
                "key_actions": [
                    "Monthly cost optimization reviews",
                    "Quarterly architecture reviews",
                    "Act on Azure Advisor recommendations",
                    "Keep up with new cost-effective services"
                ]
            }
        }
    
    def get_recommendations_by_service(
        self, 
        service_type: str,
        current_cost: float
    ) -> List[WAFRecommendation]:
        """
        Get WAF-based recommendations for a specific Azure service.
        
        Args:
            service_type: Azure resource type (e.g., 'Microsoft.Compute')
            current_cost: Current monthly cost in USD
        
        Returns:
            List of WAF recommendations specific to the service
        """
        recommendations = []
        
        # Map service types to applicable principles
        service_principles = {
            "Microsoft.Compute": [
                self._compute_efficiency_recommendation(service_type, current_cost),
                self._compute_pricing_recommendation(service_type, current_cost),
                self._compute_automation_recommendation(service_type, current_cost),
            ],
            "Microsoft.Storage": [
                self._storage_efficiency_recommendation(service_type, current_cost),
                self._storage_lifecycle_recommendation(service_type, current_cost),
            ],
            "Microsoft.Sql": [
                self._sql_efficiency_recommendation(service_type, current_cost),
                self._sql_pricing_recommendation(service_type, current_cost),
            ],
            "Microsoft.Web": [
                self._web_efficiency_recommendation(service_type, current_cost),
                self._web_autoscaling_recommendation(service_type, current_cost),
            ],
            "Microsoft.Network": [
                self._network_efficiency_recommendation(service_type, current_cost),
                self._network_cdn_recommendation(service_type, current_cost),
            ]
        }
        
        # Get service-specific recommendations
        if service_type in service_principles:
            recommendations.extend(service_principles[service_type])
        
        # Always add monitoring and governance recommendations
        recommendations.extend([
            self._monitoring_recommendation(service_type, current_cost),
            self._governance_recommendation(service_type, current_cost)
        ])
        
        return recommendations
    
    def _compute_efficiency_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """VM right-sizing and efficiency."""
        return WAFRecommendation(
            principle=WAFPrinciple.EFFICIENCY,
            principle_name=self.principles[WAFPrinciple.EFFICIENCY]["name"],
            service_type=service_type,
            recommendation="Right-size virtual machines based on actual utilization metrics",
            rationale="VMs are often over-provisioned. Azure Advisor shows VMs with <5% CPU can be downsized or deallocated.",
            action_items=[
                "Review Azure Advisor VM size recommendations",
                "Analyze CPU, memory, and disk utilization over 30 days",
                "Downsize overprovisioned VMs to smaller SKUs",
                "Deallocate or delete unused VMs",
                "Use B-series VMs for variable workloads"
            ],
            documentation_url=f"{self.base_url}/cost-optimization/optimize-vm",
            priority="high" if cost > 500 else "medium",
            estimated_savings_percent=30.0,
            implementation_effort="2-4 hours",
            compliance_tags=["WAF:Cost", "Efficiency", "Right-sizing"]
        )
    
    def _compute_pricing_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Reserved instances and spot VMs."""
        return WAFRecommendation(
            principle=WAFPrinciple.PRICING,
            principle_name=self.principles[WAFPrinciple.PRICING]["name"],
            service_type=service_type,
            recommendation="Purchase Azure Reserved VM Instances for predictable workloads",
            rationale="Azure Reservations (1 or 3 year) provide up to 72% savings vs pay-as-you-go. Spot VMs offer up to 90% savings.",
            action_items=[
                "Identify VMs running 24x7 with stable workloads",
                "Review reservation recommendations in Azure portal",
                "Purchase 1-year or 3-year reservations",
                "Use Spot VMs for batch processing, dev/test",
                "Enable Azure Hybrid Benefit if you have Windows Server licenses"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/save-compute-costs-reservations",
            priority="critical" if cost > 1000 else "high",
            estimated_savings_percent=50.0,
            implementation_effort="1-2 hours",
            compliance_tags=["WAF:Cost", "Reservations", "Spot VMs", "FinOps"]
        )
    
    def _compute_automation_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Auto-shutdown for dev/test."""
        return WAFRecommendation(
            principle=WAFPrinciple.AUTOMATION,
            principle_name=self.principles[WAFPrinciple.AUTOMATION]["name"],
            service_type=service_type,
            recommendation="Implement auto-shutdown schedules for development and test VMs",
            rationale="Dev/test VMs don't need to run 24x7. Auto-shutdown can save 65% of costs for non-production workloads.",
            action_items=[
                "Enable auto-shutdown on all dev/test VMs",
                "Set shutdown time to 7 PM with timezone",
                "Configure startup schedules if needed",
                "Use Azure Automation runbooks for complex schedules",
                "Tag VMs for environment-based policies"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/automation/automation-solution-vm-management",
            priority="medium",
            estimated_savings_percent=65.0,
            implementation_effort="1 hour",
            compliance_tags=["WAF:Cost", "Automation", "Dev/Test"]
        )
    
    def _storage_efficiency_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Storage tier optimization."""
        return WAFRecommendation(
            principle=WAFPrinciple.EFFICIENCY,
            principle_name=self.principles[WAFPrinciple.EFFICIENCY]["name"],
            service_type=service_type,
            recommendation="Optimize blob storage tiers based on access patterns",
            rationale="Hot tier costs 10x more than Cool tier. Archive tier is 50x cheaper than Hot for rarely accessed data.",
            action_items=[
                "Analyze blob access patterns using Storage Analytics",
                "Move infrequently accessed blobs to Cool tier (>30 days)",
                "Move rarely accessed blobs to Archive tier (>180 days)",
                "Implement lifecycle management policies",
                "Delete old snapshots and unused storage"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview",
            priority="high" if cost > 300 else "medium",
            estimated_savings_percent=40.0,
            implementation_effort="2-3 hours",
            compliance_tags=["WAF:Cost", "Storage", "Lifecycle"]
        )
    
    def _storage_lifecycle_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Lifecycle management policies."""
        return WAFRecommendation(
            principle=WAFPrinciple.AUTOMATION,
            principle_name=self.principles[WAFPrinciple.AUTOMATION]["name"],
            service_type=service_type,
            recommendation="Implement automated lifecycle management policies",
            rationale="Automate data tiering and deletion to avoid manual management and reduce costs continuously.",
            action_items=[
                "Create lifecycle policy: Hot → Cool after 30 days",
                "Create lifecycle policy: Cool → Archive after 90 days",
                "Delete blobs older than retention period",
                "Archive log files after 180 days",
                "Set up blob versioning cleanup"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/storage/blobs/lifecycle-management-overview",
            priority="medium",
            estimated_savings_percent=25.0,
            implementation_effort="1-2 hours",
            compliance_tags=["WAF:Cost", "Storage", "Automation"]
        )
    
    def _sql_efficiency_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """SQL Database right-sizing."""
        return WAFRecommendation(
            principle=WAFPrinciple.EFFICIENCY,
            principle_name=self.principles[WAFPrinciple.EFFICIENCY]["name"],
            service_type=service_type,
            recommendation="Right-size Azure SQL Database based on DTU/vCore utilization",
            rationale="SQL databases are often over-provisioned. Monitor DTU usage and downscale if consistently below 50%.",
            action_items=[
                "Review DTU/vCore utilization in Azure portal",
                "Check query performance and identify slow queries",
                "Downsize if average DTU usage < 50% for 30 days",
                "Use elastic pools for multiple databases",
                "Consider serverless tier for variable workloads"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/azure-sql/database/scale-resources",
            priority="high" if cost > 400 else "medium",
            estimated_savings_percent=35.0,
            implementation_effort="2-3 hours",
            compliance_tags=["WAF:Cost", "Database", "Right-sizing"]
        )
    
    def _sql_pricing_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """SQL serverless and reserved capacity."""
        return WAFRecommendation(
            principle=WAFPrinciple.PRICING,
            principle_name=self.principles[WAFPrinciple.PRICING]["name"],
            service_type=service_type,
            recommendation="Use Azure SQL serverless tier for variable workloads and reserved capacity for steady workloads",
            rationale="Serverless auto-pauses during inactivity (saves ~70% during idle). Reserved capacity saves up to 33% for steady workloads.",
            action_items=[
                "Evaluate database usage patterns",
                "Switch to serverless for dev/test and variable workloads",
                "Purchase reserved capacity for production databases",
                "Use auto-pause delay of 1 hour for serverless",
                "Monitor costs after switching"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/azure-sql/database/serverless-tier-overview",
            priority="high",
            estimated_savings_percent=45.0,
            implementation_effort="1-2 hours",
            compliance_tags=["WAF:Cost", "Database", "Serverless", "Reservations"]
        )
    
    def _web_efficiency_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """App Service consolidation."""
        return WAFRecommendation(
            principle=WAFPrinciple.EFFICIENCY,
            principle_name=self.principles[WAFPrinciple.EFFICIENCY]["name"],
            service_type=service_type,
            recommendation="Consolidate multiple apps into fewer App Service plans",
            rationale="App Service plans are charged by the SKU, not the number of apps. Multiple apps can share one plan.",
            action_items=[
                "Inventory all App Service plans and apps",
                "Identify underutilized plans (<30% CPU/Memory)",
                "Consolidate apps from multiple S1 plans into one S2/S3",
                "Separate production and non-production apps",
                "Use deployment slots instead of separate apps"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans",
            priority="medium",
            estimated_savings_percent=30.0,
            implementation_effort="2-4 hours",
            compliance_tags=["WAF:Cost", "App Service", "Consolidation"]
        )
    
    def _web_autoscaling_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Auto-scaling for App Service."""
        return WAFRecommendation(
            principle=WAFPrinciple.AUTOMATION,
            principle_name=self.principles[WAFPrinciple.AUTOMATION]["name"],
            service_type=service_type,
            recommendation="Implement auto-scaling rules to match capacity with demand",
            rationale="Manual scaling keeps excess capacity during low traffic. Auto-scaling can reduce costs by 40% during off-peak hours.",
            action_items=[
                "Enable auto-scale on App Service plan",
                "Set scale-out rule: CPU > 70% for 5 minutes",
                "Set scale-in rule: CPU < 30% for 10 minutes",
                "Set minimum instances to 1, maximum to 5",
                "Monitor scaling activities and adjust thresholds"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/app-service/manage-scale-up",
            priority="medium",
            estimated_savings_percent=40.0,
            implementation_effort="1-2 hours",
            compliance_tags=["WAF:Cost", "App Service", "Auto-scaling"]
        )
    
    def _network_efficiency_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Network optimization."""
        return WAFRecommendation(
            principle=WAFPrinciple.EFFICIENCY,
            principle_name=self.principles[WAFPrinciple.EFFICIENCY]["name"],
            service_type=service_type,
            recommendation="Optimize network costs by reducing data egress and using regional services",
            rationale="Data egress charges can be significant. Keep data within region and use CDN to reduce egress.",
            action_items=[
                "Analyze data transfer patterns using Network Watcher",
                "Move resources to same region as data consumers",
                "Remove unused public IP addresses",
                "Delete unused Load Balancers and Application Gateways",
                "Use VNet peering instead of VPN for inter-VNet traffic"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/architecture/framework/cost/design-regions",
            priority="medium",
            estimated_savings_percent=20.0,
            implementation_effort="2-3 hours",
            compliance_tags=["WAF:Cost", "Network", "Data Transfer"]
        )
    
    def _network_cdn_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """CDN for egress reduction."""
        return WAFRecommendation(
            principle=WAFPrinciple.ARCHITECTURE,
            principle_name=self.principles[WAFPrinciple.ARCHITECTURE]["name"],
            service_type=service_type,
            recommendation="Use Azure CDN to reduce data egress costs",
            rationale="CDN caching reduces origin requests and egress charges. Can save 60% on bandwidth costs.",
            action_items=[
                "Enable Azure CDN for static content",
                "Configure cache rules for images, JS, CSS",
                "Use CDN for API responses where appropriate",
                "Set proper cache TTLs (1 hour for dynamic, 1 day for static)",
                "Monitor CDN hit ratio (target >80%)"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/cdn/cdn-overview",
            priority="medium" if cost > 200 else "low",
            estimated_savings_percent=60.0,
            implementation_effort="1-2 hours",
            compliance_tags=["WAF:Cost", "CDN", "Performance"]
        )
    
    def _monitoring_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Cost monitoring and alerting."""
        return WAFRecommendation(
            principle=WAFPrinciple.MONITOR,
            principle_name=self.principles[WAFPrinciple.MONITOR]["name"],
            service_type=service_type,
            recommendation="Set up comprehensive cost monitoring and alerting",
            rationale="Proactive monitoring prevents cost surprises. Cost alerts enable quick action on anomalies.",
            action_items=[
                "Create budget for this service",
                "Set alerts at 50%, 75%, 90%, 100% of budget",
                "Configure action group for email/SMS notifications",
                "Review Azure Cost Analysis weekly",
                "Enable anomaly detection in Cost Management"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/cost-mgt-alerts-monitor-usage-spending",
            priority="high",
            estimated_savings_percent=15.0,
            implementation_effort="30 minutes",
            compliance_tags=["WAF:Cost", "Monitoring", "Alerts", "FinOps"]
        )
    
    def _governance_recommendation(
        self, service_type: str, cost: float
    ) -> WAFRecommendation:
        """Cost governance and tagging."""
        return WAFRecommendation(
            principle=WAFPrinciple.GOVERNANCE,
            principle_name=self.principles[WAFPrinciple.GOVERNANCE]["name"],
            service_type=service_type,
            recommendation="Implement resource tagging and Azure Policy for cost governance",
            rationale="Tags enable cost allocation and chargeback. Azure Policy enforces compliance and prevents waste.",
            action_items=[
                "Tag all resources: Environment, Owner, CostCenter, Project",
                "Create Azure Policy to require tags on resources",
                "Set up policy to prevent expensive SKU creation",
                "Use Azure Policy to enforce resource naming conventions",
                "Review untagged resources monthly"
            ],
            documentation_url="https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/tag-resources",
            priority="medium",
            estimated_savings_percent=10.0,
            implementation_effort="1-2 hours",
            compliance_tags=["WAF:Cost", "Governance", "Tagging", "Policy"]
        )
    
    def get_all_principles(self) -> Dict[WAFPrinciple, Dict]:
        """Get all 9 WAF Cost Optimization principles."""
        return self.principles
    
    def get_principle_checklist(self) -> Dict[str, List[str]]:
        """Get actionable checklist for all principles."""
        checklist = {}
        for principle, details in self.principles.items():
            checklist[details["name"]] = details["key_actions"]
        return checklist


def main():
    """Test Azure WAF Cost Optimization module."""
    print("=" * 70)
    print("🏗️  Azure Well-Architected Framework - Cost Optimization")
    print("=" * 70)
    
    waf = AzureWAFCostOptimization()
    
    # Example: Get recommendations for a VM service costing $800/month
    print("\n📋 WAF Recommendations for Microsoft.Compute ($800/month)")
    print("=" * 70)
    
    recommendations = waf.get_recommendations_by_service(
        service_type="Microsoft.Compute",
        current_cost=800.0
    )
    
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. [{rec.priority.upper()}] {rec.recommendation}")
        print(f"   Principle: {rec.principle_name}")
        print(f"   Potential Savings: {rec.estimated_savings_percent}%")
        print(f"   Effort: {rec.implementation_effort}")
        print(f"   📖 Documentation: {rec.documentation_url}")
        print(f"   Action Items:")
        for action in rec.action_items[:3]:
            print(f"     • {action}")
    
    # Show all 9 principles
    print("\n" + "=" * 70)
    print("📚 All 9 WAF Cost Optimization Principles")
    print("=" * 70)
    
    principles = waf.get_all_principles()
    for principle, details in principles.items():
        print(f"\n✓ {details['name']}")
        print(f"  {details['description']}")
        print(f"  📖 {details['url']}")


if __name__ == "__main__":
    main()
