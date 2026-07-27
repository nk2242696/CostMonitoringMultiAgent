# Quick Start: Azure Architecture Agent System

## ⚡ 5-Minute Setup

### Step 1: Install Dependencies

```bash
pip install pyautogen openai python-dotenv
```

Or if using the full project:

```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment

Create `.env` file (or add to existing):

```bash
# Azure OpenAI (Recommended)
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# OR OpenAI
OPENAI_API_KEY=sk-your-openai-key
```

### Step 3: Run Your First Review

```bash
# Option A: Use built-in template
python run_architecture_review.py --template cost_monitoring

# Option B: Custom problem statement
python run_architecture_review.py --problem "Build a serverless API with 100K requests/day, budget $200/month"

# Option C: From file
python run_architecture_review.py --file my_architecture_problem.txt
```

### Step 4: Check Results

```bash
# Read the executive summary
cat azure_architecture_review/00_SUMMARY_REPORT.md

# Or open in VS Code
code azure_architecture_review/00_SUMMARY_REPORT.md
```

---

## 📋 Example: Review Your Current Project

Create `my_problem.txt`:

```text
We need to deploy a cost monitoring dashboard to Azure.

REQUIREMENTS:
- Python FastAPI backend
- PostgreSQL database
- Grafana for visualization
- 10-20 users
- Budget: $500-1000/month

CONSTRAINTS:
- Small team (2 engineers)
- 6-8 weeks to launch
- No Kubernetes experience
```

Run review:

```bash
python run_architecture_review.py --file my_problem.txt --output ./my_review
```

Get decision:

```bash
# Check the decision
cat my_review/03_final_decision.json | jq .decision_status
```

---

## 🎯 Common Use Cases

### 1. Pre-Project Architecture Review

**When:** Before starting a new Azure project  
**Goal:** Get cost estimates and complexity assessment

```bash
python run_architecture_review.py --template microservices_migration
```

### 2. Cost Optimization Analysis

**When:** Azure costs are higher than expected  
**Goal:** Find savings opportunities

```bash
python run_architecture_review.py --problem "Review current setup: AKS with 5 nodes, Azure SQL Business Critical, Application Gateway. Monthly cost: $4,200. Find 50% cost savings."
```

### 3. Technology Selection

**When:** Choosing between Azure services  
**Goal:** Get unbiased recommendations

```bash
python run_architecture_review.py --problem "Choose between Azure Functions, Container Apps, and AKS for microservices with 10K requests/day"
```

---

## 🔧 Troubleshooting

### Error: "No module named 'autogen'"

```bash
pip install pyautogen
```

### Error: "Invalid API key"

Check your `.env` file:

```bash
cat .env | grep OPENAI
```

Verify key is valid:

```bash
# Azure OpenAI
curl https://your-resource.openai.azure.com/openai/deployments?api-version=2024-02-15-preview \
  -H "api-key: your-key"

# OpenAI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer your-key"
```

### Error: "Rate limit exceeded"

Wait 60 seconds or upgrade your API tier.

### Agent Response is Too Generic

Add more details to your problem statement:

- Specific numbers (users, requests/day, data size)
- Budget constraints
- Team skill levels
- Timeline requirements
- Current stack/infrastructure

---

## 📚 What's Next?

### Customize Agent Prompts

Edit `azure_architecture_agents.py`:

```python
def _create_architecture_agent(self):
    system_message = """
    You are a Senior Azure Cloud Architect...
    
    CUSTOM RULE: Always recommend Azure Container Apps over AKS for < 50K requests/day
    """
```

### Add a 4th Agent (e.g., Security Reviewer)

```python
def _create_security_agent(self):
    return autogen.AssistantAgent(
        name="SecurityReviewer",
        system_message="Review for Azure Policy, Defender, RBAC..."
    )
```

### Integrate with CI/CD

```yaml
# GitHub Actions example
- name: Run Architecture Review
  run: |
    python run_architecture_review.py --file architecture.txt --output ./review
    
- name: Check Decision
  run: |
    DECISION=$(cat review/03_final_decision.json | jq -r .decision_status)
    if [ "$DECISION" != "Approved" ]; then
      echo "Architecture not approved: $DECISION"
      exit 1
    fi
```

### Build a Slack Bot

```python
# slack_bot.py
from slack_bolt import App
from azure_architecture_agents import AzureArchitectureAgentSystem

@app.command("/review-architecture")
def review_architecture(ack, command):
    ack()
    problem = command['text']
    system = AzureArchitectureAgentSystem()
    results = system.run_full_cycle(problem)
    
    app.client.chat_postMessage(
        channel=command['channel_id'],
        text=f"Decision: {results['decision']['decision_status']}"
    )
```

---

## 💡 Pro Tips

1. **Be Specific in Problem Statements**
   - ✅ "Support 100K requests/day with p95 latency < 500ms"
   - ❌ "Build a scalable API"

2. **Include Budget Constraints**
   - Agents will optimize for cost when you specify a budget

3. **Mention Team Skills**
   - Reviewer agent will flag skill gaps and suggest training

4. **Use Templates as Starting Points**
   - Copy and modify existing templates for similar scenarios

5. **Review All 3 Outputs**
   - Proposal (Agent 1): Technical details
   - Review (Agent 2): Reality check
   - Decision (Agent 3): Action items

---

## 🆘 Getting Help

**Documentation:** See `AGENT_SYSTEM_README.md` for full details

**Examples:** Run `python examples_architecture_agents.py`

**Templates:** List with `python run_architecture_review.py --list-templates`

**Issues:** Check agent output files in `azure_architecture_review/` directory

---

**Ready to get brutally honest architecture feedback? Run your first review now! 🚀**
