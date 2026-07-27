"""
Example: Run the three-agent system with a custom problem statement
"""

from azure_architecture_agents import AzureArchitectureAgentSystem


def example_1_cost_monitoring():
    """Example 1: Cost monitoring dashboard (from your current project)"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Cost Monitoring Dashboard")
    print("="*80 + "\n")
    
    problem = """
We need to build a real-time cost monitoring dashboard for Azure subscriptions.

REQUIREMENTS:
- Collect cost data from multiple Azure subscriptions (5-10 subscriptions initially)
- Store time-series cost data for historical analysis (6+ months)
- Provide a web-based dashboard with visualizations (cost trends, breakdown by service/resource group)
- Generate AI-powered cost optimization recommendations
- Send alerts when costs exceed thresholds
- Support 10-20 concurrent users (internal finance/engineering teams)
- Must integrate with existing Azure AD for authentication
- Budget: $500-1000/month for Azure infrastructure

CONSTRAINTS:
- Small team (2 engineers), limited DevOps experience
- Must launch MVP in 6-8 weeks
- No Kubernetes expertise
- Prefer managed services to minimize operational overhead
- Cost is a major concern (we're monitoring costs for cost savings!)

CURRENT STACK:
- Python backend (FastAPI)
- PostgreSQL database
- Grafana for visualization
- Running on Docker containers locally
"""
    
    system = AzureArchitectureAgentSystem(work_dir="./examples/cost_monitoring_review")
    results = system.run_full_cycle(problem)
    
    print("\n✅ Review complete! Check ./examples/cost_monitoring_review/00_SUMMARY_REPORT.md")
    return results


def example_2_serverless_api():
    """Example 2: High-traffic serverless API"""
    print("\n" + "="*80)
    print("EXAMPLE 2: High-Traffic Serverless API")
    print("="*80 + "\n")
    
    problem = """
Build a serverless REST API for a mobile app backend.

REQUIREMENTS:
- Handle 1 million requests per day (peak: 500 requests/second)
- Average response time < 200ms (p95 < 500ms)
- Support authentication (OAuth2 + JWT)
- Connect to Azure SQL Database (existing, 50GB data)
- Store user-uploaded images (100GB/month growth)
- Send push notifications via Azure Notification Hubs
- Support iOS and Android clients
- Budget: $200-400/month

CONSTRAINTS:
- Team has Node.js expertise (prefer JavaScript/TypeScript)
- No prior Azure Functions experience
- Must support staged rollouts (blue-green deployments)
- Need automated testing in CI/CD
- 4-week timeline to production

CURRENT STACK:
- Express.js running on AWS EC2 (migrating to Azure)
- MongoDB (plan to migrate to Azure SQL)
"""
    
    system = AzureArchitectureAgentSystem(work_dir="./examples/serverless_api_review")
    results = system.run_full_cycle(problem)
    
    return results


def example_3_data_lake():
    """Example 3: Enterprise data lake"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Enterprise Data Lake")
    print("="*80 + "\n")
    
    problem = """
Build a data lake for centralized analytics across 20+ business units.

REQUIREMENTS:
- Ingest data from: SQL databases, APIs, CSV files, event streams
- Store 10TB of historical data (growing 500GB/month)
- Support SQL queries for business analysts (100+ users)
- Run Spark jobs for data transformations
- Schedule ETL pipelines (daily, hourly, real-time)
- Power BI integration for executive dashboards
- Data catalog and governance (data lineage, PII detection)
- Budget: $10K-15K/month

CONSTRAINTS:
- Mixed skill levels (SQL experts, few Spark engineers)
- Must meet SOX compliance requirements
- Sensitive financial data (PCI controls needed)
- 6-month phased rollout (pilot with 3 business units first)
- Prefer Azure-native services

CURRENT STATE:
- Data scattered across 50+ SQL Server databases
- Manual CSV exports to shared drives
- No central governance or catalog
- Analysts use Excel for everything
"""
    
    system = AzureArchitectureAgentSystem(work_dir="./examples/data_lake_review")
    results = system.run_full_cycle(problem)
    
    return results


def example_4_quick_validation():
    """Example 4: Quick validation of existing architecture"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Validate Existing Architecture")
    print("="*80 + "\n")
    
    problem = """
Review our current Azure setup and suggest improvements.

CURRENT ARCHITECTURE:
- Azure Kubernetes Service (AKS) with 5 nodes (Standard_D4s_v3)
- Azure SQL Database (Business Critical tier, 8 vCores)
- Azure Cache for Redis (Premium P1)
- Azure Application Gateway with WAF
- Azure Monitor + Log Analytics
- Running 3 microservices (authentication, payments, notifications)

CONCERNS:
- Monthly cost is $4,200 (expected $2,000)
- Complex deployment process (DevOps takes 3 hours per release)
- AKS nodes running at 20% utilization
- Application Gateway seems expensive for our traffic (5K requests/day)

QUESTION:
Can we simplify this and cut costs by 50% without sacrificing reliability?

CONSTRAINTS:
- Must maintain 99.9% uptime
- Cannot increase deployment complexity
- Team comfortable with current setup (change aversion)
"""
    
    system = AzureArchitectureAgentSystem(work_dir="./examples/optimization_review")
    results = system.run_full_cycle(problem)
    
    # Print cost savings analysis
    if results['review']['suggested_changes']:
        print("\n💰 COST OPTIMIZATION OPPORTUNITIES:")
        for change in results['review']['suggested_changes'][:3]:
            print(f"\n  • {change.get('change', 'N/A')}")
            print(f"    Rationale: {change.get('rationale', 'N/A')}")
            print(f"    Impact: {change.get('impact', 'N/A')}")
    
    return results


def example_5_interactive_mode():
    """Example 5: Run with human-in-the-loop approval"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Interactive Mode (Human Approval)")
    print("="*80 + "\n")
    
    print("This example demonstrates human-in-the-loop mode.")
    print("To enable: Modify _create_user_proxy() in azure_architecture_agents.py")
    print("Change human_input_mode from 'NEVER' to 'ALWAYS'")
    print("\nThis allows you to:")
    print("  - Approve/reject each agent's output")
    print("  - Request clarifications")
    print("  - Provide additional context")
    print("  - Override decisions")


def main():
    """Run all examples (comment out the ones you don't want)"""
    
    print("\n" + "🚀 "*30)
    print("AZURE ARCHITECTURE AGENT SYSTEM - EXAMPLES")
    print("🚀 "*30)
    
    # Uncomment the examples you want to run:
    
    # Example 1: Cost monitoring dashboard (most relevant to your project)
    example_1_cost_monitoring()
    
    # Example 2: Serverless API
    # example_2_serverless_api()
    
    # Example 3: Enterprise data lake
    # example_3_data_lake()
    
    # Example 4: Optimize existing architecture
    # example_4_quick_validation()
    
    # Example 5: Interactive mode (requires code modification)
    # example_5_interactive_mode()
    
    print("\n" + "✅ "*30)
    print("EXAMPLES COMPLETE")
    print("✅ "*30 + "\n")


if __name__ == "__main__":
    main()
