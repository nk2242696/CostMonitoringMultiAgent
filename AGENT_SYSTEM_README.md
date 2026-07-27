# Azure Architecture Review - Three-Agent System

A production-ready multi-agent system using **AutoGen** to propose, critique, and approve Azure cloud architectures with brutal honesty about costs, complexity, and execution reality.

## 🎯 Overview

This system implements a three-agent collaborative workflow:

1. **Agent 1: Azure Architecture Agent** - Proposes end-to-end solutions with explicit cost awareness
2. **Agent 2: Engineering Reviewer** - Critically assesses effort, complexity, and time-to-implement
3. **Agent 3: Final Approver** - Makes the final decision: Approve, Approve with Changes, or Reject

### Key Features

- ✅ **Cost-Aware by Default** - Explicitly calls out expensive Azure services and alternatives
- ✅ **Execution Reality Check** - Assesses actual implementation effort, not just theoretical designs
- ✅ **No Hand-Waving** - Challenges vague statements like "highly scalable" without evidence
- ✅ **Sequential Refinement** - Each agent builds on the previous agent's output
- ✅ **Structured Outputs** - JSON-formatted decisions for downstream automation
- ✅ **Human-Readable Reports** - Markdown summaries for stakeholders

## 🚀 Quick Start

### Prerequisites

```bash
# Install dependencies
pip install pyautogen openai python-dotenv

# Or add to requirements.txt
echo "pyautogen>=0.2.0" >> requirements.txt
echo "openai>=1.0.0" >> requirements.txt
echo "python-dotenv>=1.0.0" >> requirements.txt
pip install -r requirements.txt
```

### Environment Setup

Create a `.env` file:

```bash
# For Azure OpenAI
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# OR for OpenAI
OPENAI_API_KEY=your-openai-key-here
```

### Run Architecture Review

#### Option 1: Use Predefined Templates

```bash
# List available templates
python run_architecture_review.py --list-templates

# Run review using template
python run_architecture_review.py --template cost_monitoring
```

#### Option 2: Provide Custom Problem Statement

```bash
# From file
python run_architecture_review.py --file my_problem.txt

# Directly as argument
python run_architecture_review.py --problem "Build a serverless API handling 1M requests/day with cost < $200/month"
```

#### Option 3: Programmatic Usage

```python
from azure_architecture_agents import AzureArchitectureAgentSystem

problem = """
Build a real-time analytics dashboard for IoT devices.
- 10,000 devices sending data every minute
- Store data for 1 year
- Support 100 concurrent dashboard users
- Budget: $2K/month
"""

system = AzureArchitectureAgentSystem(work_dir="./review_output")
results = system.run_full_cycle(problem)

print(f"Decision: {results['decision']['decision_status']}")
```

## 📁 Output Structure

After running a review, you'll get:

```
azure_architecture_review/
├── 00_SUMMARY_REPORT.md              # Executive summary
├── 01_architecture_proposal.txt      # Agent 1 raw output
├── 01_architecture_proposal.json     # Structured proposal
├── 02_engineering_review.txt         # Agent 2 raw output
├── 02_engineering_review.json        # Structured review
├── 03_final_decision.txt             # Agent 3 raw output
└── 03_final_decision.json            # Structured decision
```

## 🤖 Agent Details

### Agent 1: Azure Architecture & Recommendations Agent

**Role:** Senior Azure Cloud Architect (15+ years experience)

**Outputs:**
- Architecture overview (3-5 sentences)
- Recommended Azure services by category (compute, storage, database, networking, monitoring, security)
- Cost-sensitive components with alternatives
- Design decisions with rationale
- Trade-offs (performance vs cost vs scalability)
- Risks and assumptions

**Example Output:**

```json
{
  "architecture_overview": "Deploy FastAPI backend on Azure Container Apps with PostgreSQL Flexible Server...",
  "recommended_services": {
    "compute": "Azure Container Apps (Consumption tier) - $0 when idle, scales 0-10 instances",
    "database": "PostgreSQL Flexible Server (Burstable B1ms) - ~$15/month with auto-pause",
    "storage": "Azure Blob Storage (Hot tier) - $0.018/GB/month for dashboard exports"
  },
  "cost_sensitive_components": [
    {
      "service": "Azure Kubernetes Service",
      "why_expensive": "24/7 control plane costs ~$70/month + node pools",
      "cheaper_alternative": "Azure Container Apps (consumption-based)",
      "recommendation": "Use AKS only if multi-cluster or complex networking required"
    }
  ]
}
```

### Agent 2: Engineering Reviewer (Effort, Complexity, Time)

**Role:** Principal Engineer / Delivery Reviewer

**Outputs:**
- Review summary (3-4 sentence critical assessment)
- Effort assessment (Low / Medium / High)
- Complexity hotspots with mitigation strategies
- Time-to-implement estimate (realistic)
- Suggested changes with impact analysis
- Over-engineering flags
- Hidden costs (VPN Gateway, Firewall, Log Analytics ingestion)
- Skill gaps required for execution

**Example Output:**

```json
{
  "review_summary": "Solid architecture for MVP but Azure Application Gateway is overkill...",
  "effort_assessment": "Medium",
  "time_to_implement_estimate": "6-7 weeks with 2 engineers",
  "complexity_hotspots": [
    {
      "area": "Azure AD authentication with FastAPI",
      "complexity_level": "Medium",
      "why": "Requires understanding OAuth2 flows and token validation",
      "mitigation": "Use Microsoft's msal-python library and FastAPI middleware"
    }
  ],
  "hidden_costs": [
    "Log Analytics ingestion: $2.76/GB after 5GB/day free tier",
    "VNet integration for Container Apps: Requires NAT Gateway (~$35/month)"
  ]
}
```

### Agent 3: Final Approver & Decision Agent

**Role:** Staff+ Architect / Engineering Leader

**Outputs:**
- Decision status (Approved / Approved with Changes / Rejected)
- Key feedback (3-4 sentence overall assessment)
- Mandatory changes before execution
- Deferred items (can wait until v2)
- Post-implementation watchlist (metrics to monitor)
- Execution priority (Critical / High / Medium / Low)

**Example Output:**

```json
{
  "decision_status": "Approved with Changes",
  "key_feedback": "Strong foundation for MVP. Main concern is monitoring setup...",
  "mandatory_changes": [
    "Must add Azure Budget alerts before deploying to production",
    "Must document runbook for scaling Container Apps during traffic spikes",
    "Replace Application Gateway with Container Apps built-in ingress to save $150/month"
  ],
  "deferred_items": [
    "Multi-region deployment can wait until after validating single-region performance",
    "Advanced APM (Application Insights Profiler) defer until product-market fit"
  ],
  "post_implementation_watchlist": [
    {
      "metric": "Azure Cost per Day",
      "threshold": "$50/day",
      "action": "Investigate if exceeded; check for runaway resources"
    }
  ],
  "execution_priority": "High"
}
```

## 🔧 Configuration

### Custom LLM Configuration

```python
from azure_architecture_agents import AzureArchitectureAgentSystem

# Custom Azure OpenAI config
config_list = [{
    "model": "gpt-4-turbo",
    "api_key": "your-key",
    "base_url": "https://your-resource.openai.azure.com/",
    "api_type": "azure",
    "api_version": "2024-02-15-preview"
}]

system = AzureArchitectureAgentSystem(
    config_list=config_list,
    work_dir="./custom_output"
)
```

### Human-in-the-Loop Mode

Enable interactive approvals:

```python
# In azure_architecture_agents.py, modify _create_user_proxy():
return autogen.UserProxyAgent(
    name="User",
    human_input_mode="ALWAYS",  # Changed from "NEVER"
    max_consecutive_auto_reply=0,
    code_execution_config=False
)
```

## 📋 Available Problem Templates

Run `python run_architecture_review.py --list-templates` to see all templates:

1. **cost_monitoring** - Real-time cost monitoring dashboard
2. **microservices_migration** - Monolith to microservices migration
3. **data_platform** - Modern data analytics platform
4. **iot_solution** - IoT telemetry collection and processing

## 🎯 Use Cases

### 1. Pre-Project Architecture Review

Get a reality check before committing to a design:

```bash
python run_architecture_review.py --file architecture_proposal.txt
```

### 2. Cost Optimization Analysis

Review existing architecture for cost savings:

```bash
python run_architecture_review.py --problem "Review current AKS setup with 5 nodes, suggest cheaper alternatives maintaining same performance"
```

### 3. Technology Selection

Compare options for a specific requirement:

```bash
python run_architecture_review.py --problem "Choose between Azure SQL, PostgreSQL, and Cosmos DB for 500GB e-commerce database with 10K transactions/day"
```

### 4. Team Skill Assessment

Understand implementation complexity:

```bash
# The reviewer agent will flag skill gaps
python run_architecture_review.py --template microservices_migration
```

## 🚨 Important Notes

### What This System Does Well

- ✅ Surfaces hidden costs early (VPN Gateway, Firewall, Log Analytics)
- ✅ Challenges over-engineering (e.g., "Do you really need Kubernetes?")
- ✅ Provides realistic time estimates
- ✅ Balances Azure's "recommended" options with cost-optimal choices
- ✅ Considers team skill gaps and operational burden

### What This System Does NOT Do

- ❌ Generate Infrastructure-as-Code (Bicep/Terraform) - it only proposes architecture
- ❌ Perform security audits (add a 4th security agent if needed)
- ❌ Validate compliance requirements (HIPAA, PCI-DSS, etc.)
- ❌ Provide detailed cost estimates (integrate Azure Pricing API for that)
- ❌ Make the final decision for you (it's a recommendation system)

## 🔮 Future Enhancements

### Add More Agents

```python
# Security & Compliance Agent
security_agent = autogen.AssistantAgent(
    name="SecurityReviewer",
    system_message="Review for Azure Policy, Defender, RBAC, and compliance..."
)

# Cost Estimation Agent
cost_agent = autogen.AssistantAgent(
    name="CostEstimator",
    system_message="Provide detailed monthly cost estimates using Azure Pricing API..."
)
```

### Integration Ideas

1. **CI/CD Integration** - Run reviews on architecture PRs
2. **Slack/Teams Bot** - Get architecture feedback in chat
3. **Cost Tracking** - Compare estimated vs actual costs post-launch
4. **Architecture Repository** - Build a knowledge base of past decisions

## 📚 References

- [AutoGen Documentation](https://microsoft.github.io/autogen/)
- [Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/)
- [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
- [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/)

## 🤝 Contributing

To add new problem templates:

1. Edit `run_architecture_review.py`
2. Add entry to `PROBLEM_TEMPLATES` dict
3. Follow the structure: Requirements + Constraints + Current Stack

## 📄 License

MIT License - Use freely for your architecture reviews!

---

**Built for engineers who prefer brutal honesty over architectural fantasy.** 🔥
