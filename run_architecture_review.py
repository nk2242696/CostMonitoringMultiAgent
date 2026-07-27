"""
Executable script to run Azure architecture reviews using the three-agent system
Provides CLI interface for quick architecture assessments
"""

import sys
import argparse
from pathlib import Path
from azure_architecture_agents import AzureArchitectureAgentSystem


# Predefined problem templates for common scenarios
PROBLEM_TEMPLATES = {
    "cost_monitoring": """
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
""",
    
    "microservices_migration": """
We need to migrate a monolithic e-commerce application to microservices on Azure.

REQUIREMENTS:
- Break down monolith into 5-7 microservices (User, Order, Payment, Inventory, Notification)
- Support 100K daily active users with peak traffic of 5K concurrent requests
- 99.9% uptime SLA
- Global user base (US, Europe, Asia)
- PCI-DSS compliance for payment processing
- Real-time inventory updates
- Event-driven architecture for order processing
- Budget: $5K-8K/month

CONSTRAINTS:
- Current monolith runs on Azure VMs (Windows Server)
- Team has limited microservices experience
- Must maintain zero downtime during migration
- 6-month migration timeline
- Existing SQL Server database (2TB data)
- Legacy code is .NET Framework 4.8
""",
    
    "data_platform": """
We need to build a modern data analytics platform on Azure.

REQUIREMENTS:
- Ingest data from 10+ sources (APIs, databases, SaaS tools, IoT devices)
- Process 500GB/day of streaming and batch data
- Support SQL analytics, ML model training, and BI dashboards
- Data retention: 2 years hot, 5 years cold
- Serve 50+ data analysts and 10+ data scientists
- Real-time dashboards with < 30 second latency
- Automated data quality checks and anomaly detection
- Budget: $10K-15K/month

CONSTRAINTS:
- Team has Python/SQL skills but limited data engineering experience
- Must be GDPR compliant (EU customer data)
- No prior Azure Synapse or Databricks experience
- Prefer low-code/no-code where possible
- 4-month timeline to first production workload
""",
    
    "iot_solution": """
We need to build an IoT telemetry collection and processing platform.

REQUIREMENTS:
- Collect telemetry from 10,000 IoT devices (temperature, humidity, location)
- Device sends data every 60 seconds (10K events/minute)
- Store raw telemetry for 90 days, aggregated data for 5 years
- Real-time alerting for threshold breaches (< 10 second latency)
- Predictive maintenance ML models
- Device management (provisioning, updates, monitoring)
- Web dashboard for operations team
- Budget: $3K-5K/month

CONSTRAINTS:
- Devices use MQTT protocol
- Limited bandwidth (cellular connections)
- Must handle network interruptions gracefully
- Team has no IoT experience
- 3-month MVP timeline
"""
}


def load_problem_statement(args) -> str:
    """Load problem statement from file, template, or CLI argument"""
    if args.template:
        if args.template not in PROBLEM_TEMPLATES:
            print(f"Error: Unknown template '{args.template}'")
            print(f"Available templates: {', '.join(PROBLEM_TEMPLATES.keys())}")
            sys.exit(1)
        return PROBLEM_TEMPLATES[args.template]
    
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        return file_path.read_text()
    
    elif args.problem:
        return args.problem
    
    else:
        print("Error: Must provide --problem, --file, or --template")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run Azure Architecture Review using three-agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use predefined template
  python run_architecture_review.py --template cost_monitoring

  # Use custom problem statement from file
  python run_architecture_review.py --file problem_statement.txt

  # Provide problem statement directly
  python run_architecture_review.py --problem "Build a serverless API with 1M requests/day"

  # List available templates
  python run_architecture_review.py --list-templates

  # Specify custom output directory
  python run_architecture_review.py --template data_platform --output ./reviews/data_platform_v1
"""
    )
    
    parser.add_argument(
        "--problem",
        type=str,
        help="Problem statement as string"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        help="Path to file containing problem statement"
    )
    
    parser.add_argument(
        "--template",
        type=str,
        choices=list(PROBLEM_TEMPLATES.keys()),
        help="Use predefined problem template"
    )
    
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List available problem templates"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="./azure_architecture_review",
        help="Output directory for review results (default: ./azure_architecture_review)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # List templates if requested
    if args.list_templates:
        print("\nAvailable Problem Templates:")
        print("=" * 60)
        for name, template in PROBLEM_TEMPLATES.items():
            # Extract first line as description
            description = template.strip().split('\n')[0]
            print(f"\n{name}:")
            print(f"  {description}")
        print("\n" + "=" * 60)
        return
    
    # Load problem statement
    problem_statement = load_problem_statement(args)
    
    # Display problem statement
    print("\n" + "=" * 80)
    print("PROBLEM STATEMENT")
    print("=" * 80)
    print(problem_statement)
    print("=" * 80 + "\n")
    
    # Confirm execution
    response = input("Proceed with architecture review? (y/n): ")
    if response.lower() != 'y':
        print("Review cancelled.")
        return
    
    # Initialize and run the agent system
    try:
        system = AzureArchitectureAgentSystem(work_dir=args.output)
        results = system.run_full_cycle(problem_statement)
        
        # Display summary
        print("\n" + "=" * 80)
        print("REVIEW COMPLETE")
        print("=" * 80)
        print(f"\n✅ Decision: {results['decision']['decision_status']}")
        print(f"📊 Priority: {results['decision']['execution_priority']}")
        print(f"📁 Outputs: {args.output}/")
        
        if results['decision']['mandatory_changes']:
            print("\n⚠️  Mandatory Changes Required:")
            for change in results['decision']['mandatory_changes']:
                print(f"  • {change}")
        
        if results['review']['effort_assessment']:
            print(f"\n📈 Effort: {results['review']['effort_assessment']}")
            print(f"⏱️  Time: {results['review']['time_to_implement_estimate']}")
        
        print("\n" + "=" * 80)
        print(f"\n📄 Read the full report: {args.output}/00_SUMMARY_REPORT.md\n")
        
    except Exception as e:
        print(f"\n❌ Error during review: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
