"""
Run Azure Architecture Agents using your existing Azure OpenAI setup
"""
import os
from azure_architecture_agents import AzureArchitectureAgentSystem


def main():
    """Run the architecture agent system with your existing credentials"""
    
    print("="*80)
    print("🤖 Azure Architecture Agent System")
    print("="*80)
    
    # Use your existing Azure OpenAI credentials
    api_key = os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://openai-opvc0011.openai.azure.com/")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    if not api_key:
        raise ValueError("AZURE_OPENAI_KEY environment variable is required")
    
    # Set as environment variables for AutoGen
    os.environ["AZURE_OPENAI_API_KEY"] = api_key
    os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
    os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = deployment
    os.environ["AZURE_OPENAI_API_VERSION"] = "2024-02-15-preview"
    
    print(f"\n✅ Using Azure OpenAI:")
    print(f"   Endpoint: {endpoint}")
    print(f"   Deployment: {deployment}")
    print(f"   Key: {api_key[:20]}...\n")
    
    # Example problem: Your actual cost monitoring system
    problem = """
We need to enhance our existing Azure cost monitoring system.

CURRENT SETUP:
- Python backend (FastAPI) running in Docker
- PostgreSQL database storing cost data
- Grafana for visualization
- Collecting costs from 5-10 Azure subscriptions
- Multi-agent chat system using Azure OpenAI (gpt-4o)
- Redis for caching
- Celery for background tasks

NEW REQUIREMENTS:
- Scale to 50+ Azure subscriptions (currently 5-10)
- Add predictive cost forecasting (ML-based)
- Implement automated budget alerts with Slack/Teams integration
- Add compliance scanning (unused resources, untagged resources)
- Improve query performance (currently slow on 6+ months of data)
- Add multi-tenancy support (different teams/business units)
- Deploy to production on Azure (currently local Docker only)
- Support 100+ concurrent users (currently ~10)

CONSTRAINTS:
- Budget: $2000-3000/month for Azure infrastructure
- Team: 2 engineers, limited DevOps experience
- Timeline: 3 months to production
- Must maintain current functionality during migration
- Security: SOC 2 compliance required
- Data retention: 2 years of cost history

TECHNICAL DEBT:
- No automated testing
- Manual deployments
- No proper CI/CD
- Database not optimized (full table scans)
- No monitoring/alerting for the monitoring system itself

GOALS:
1. Migrate to Azure with proper architecture
2. Improve performance 10x
3. Reduce operational overhead
4. Keep costs under control
"""

    print("📝 Problem Statement:")
    print("-" * 80)
    print(problem)
    print("-" * 80)
    
    # Initialize the system
    system = AzureArchitectureAgentSystem(work_dir="./architecture_review")
    
    # Run the three-agent cycle
    print("\n🚀 Starting three-agent architecture review...\n")
    results = system.run_full_cycle(problem)
    
    print("\n" + "="*80)
    print("✅ Architecture Review Complete!")
    print("="*80)
    print(f"\n📄 Full report saved to: ./architecture_review/00_SUMMARY_REPORT.md")
    print(f"📊 Individual agent outputs in: ./architecture_review/")
    print("\nNext steps:")
    print("1. Review the architecture proposal")
    print("2. Check effort and complexity assessment")
    print("3. Read the final approval decision")
    print("4. Address any mandatory changes")
    print("\n")
    
    return results


if __name__ == "__main__":
    try:
        results = main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
