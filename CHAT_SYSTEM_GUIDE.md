# Multi-Agent AI Chat System - Setup & User Guide

## 🤖 Overview

The Azure Cost Monitoring Platform now includes an **intelligent multi-agent chat system** that allows users to ask questions about their cloud costs in natural language and receive AI-powered insights.

### Architecture

The system uses **4 specialized AI agents** that collaborate to answer queries:

1. **📊 Data Analyst Agent** - Queries and analyzes cost data from the database
2. **💰 Budget Advisor Agent** - Tracks budgets and provides forecasts
3. **⚡ Optimizer Agent** - Generates cost optimization recommendations
4. **🔍 Anomaly Detector Agent** - Identifies and explains unusual spending patterns

An **🎯 Orchestrator Agent** coordinates these specialists, determining which agents to involve based on the user's question and synthesizing their responses into a coherent answer.

---

## 🚀 Quick Start

### 1. Install Dependencies

```powershell
pip install openai>=1.0.0 tiktoken>=0.5.0 websockets
```

### 2. Configure Azure OpenAI

Add to your `.env` file or environment variables:

```env
AZURE_OPENAI_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

### 3. Start the API Server

```powershell
# From project root
python -m uvicorn src.monitoring.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Access the Chat Widget

Open in browser:
```
http://localhost:8000/chat/widget
```

Or embed in Grafana dashboard using iframe.

---

## 💬 How to Use

### Example Conversations

**Cost Analysis:**
```
You: "What's my total cloud spend this month?"

AI: Based on data from our Data Analyst Agent, your total cloud spend 
for November 2025 is $124,543.37. This represents:
• 103.79% of your monthly budget ($120,000)
• -1.60% decrease compared to last month ($126,572.40)
• Spending across 20+ Azure services

Top 3 cost drivers:
1. Virtual Machines: $45,200 (36%)
2. Storage Accounts: $28,300 (23%)
3. Azure SQL Database: $18,900 (15%)
```

**Budget Tracking:**
```
You: "Are we over budget this month?"

AI: Yes, according to the Budget Advisor Agent:
• Current spend: $124,543.37
• Monthly budget: $120,000
• Over by: $4,543.37 (3.79%)

Status: ⚠️ WARNING - Slightly over budget

Forecast: At current spending rate, you're projected to end the month 
at $145,680 (21% over budget).

Recommendation: Implement quick wins from our Optimizer Agent to stay 
within budget (see optimization suggestions).
```

**Cost Optimization:**
```
You: "How can I reduce costs by 10%?"

AI: The Optimizer Agent has identified opportunities to achieve 10% 
cost reduction ($12,450/month):

1. **Right-size Oversized VMs** - Save $5,200/month
   - 8 VMs with <20% CPU utilization
   - Action: Scale down Standard_D8s_v3 → Standard_D4s_v3

2. **Storage Lifecycle Management** - Save $3,800/month
   - 2.5TB in hot tier >90 days old
   - Action: Auto-archive to cool tier

3. **Reserved Instances** - Save $2,900/month
   - 12 VMs running 24/7 for 6+ months
   - Action: Purchase 1-year RI commitment

Total: $11,900/month (95% of goal) ✅
```

**Anomaly Detection:**
```
You: "Why did costs spike on November 15th?"

AI: The Anomaly Detector Agent found:

📈 Cost spike: $8,500 increase (12% jump)

Root causes:
1. Azure SQL scaled from S3 to P2 tier (+$5,200)
2. 10 new VMs deployed in eastus (+$2,800)
3. Storage ingress increased 40% (+$500)

Context: This aligns with PROJ-1234 "Production Scale-Up" approved 
on Nov 10th. Costs are within projected range.

Verdict: ✅ Expected change, no action needed

Recommendation: Monitor for 7 days. If traffic doesn't scale as 
expected, consider downgrading to S12 tier (save $2,100/month).
```

---

## 🔌 API Endpoints

### 1. REST Chat Endpoint

**POST /chat**

```json
{
  "message": "What are my top 5 cost drivers?",
  "session_id": "optional-session-uuid"
}
```

Response:
```json
{
  "response": "Based on analysis...",
  "session_id": "uuid-v4",
  "timestamp": "2025-11-25T10:30:00Z",
  "agents_involved": ["data_analyst", "budget_advisor"]
}
```

### 2. WebSocket Chat Endpoint

**WS /ws/chat**

For real-time streaming responses with "thinking" status updates.

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
    ws.send(JSON.stringify({
        message: "Show me cost trends"
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data.status); // "thinking" | "complete"
    console.log(data.response);
};
```

### 3. Suggested Questions

**GET /chat/suggestions**

Returns categorized suggested questions to help users discover capabilities.

```json
[
  {
    "category": "Cost Analysis",
    "questions": [
      "What's my total cloud spend this month?",
      "Show me cost breakdown by service",
      ...
    ]
  },
  ...
]
```

---

## 🎨 Embedding in Grafana

### Method 1: iframe Panel

1. Add **Text panel** to Grafana dashboard
2. Set Content to **HTML**
3. Add iframe code:

```html
<iframe 
    src="http://localhost:8000/chat/widget" 
    width="100%" 
    height="700px" 
    frameborder="0"
    style="border-radius: 8px;">
</iframe>
```

### Method 2: Custom Panel Plugin

Create a Grafana panel plugin that integrates the chat widget natively.

### Method 3: Floating Widget

Add to dashboard HTML:

```html
<script>
  // Inject chat widget as floating button
  const iframe = document.createElement('iframe');
  iframe.src = 'http://localhost:8000/chat/widget';
  iframe.style.cssText = 'position:fixed;bottom:20px;right:20px;width:0;height:0;border:none;z-index:9999;';
  document.body.appendChild(iframe);
</script>
```

---

## 🏗️ Architecture Details

### Agent Communication Flow

```
User Query
    ↓
Orchestrator Agent (determines which agents to involve)
    ↓
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Data        │ Budget      │ Optimizer   │ Anomaly     │
│ Analyst     │ Advisor     │ Agent       │ Detector    │
└─────────────┴─────────────┴─────────────┴─────────────┘
    ↓
Orchestrator (synthesizes responses)
    ↓
Natural Language Response to User
```

### Agent Capabilities

| Agent | Responsibilities | Data Sources | Confidence |
|-------|-----------------|--------------|------------|
| **Data Analyst** | Query cost records, calculate metrics, identify trends | PostgreSQL cost_records table | 90% |
| **Budget Advisor** | Track budget utilization, forecast spending | PostgreSQL cost_budgets table | 95% |
| **Optimizer** | Generate cost reduction recommendations | PostgreSQL ai_recommendations table | 85% |
| **Anomaly Detector** | Detect and explain cost spikes | PostgreSQL anomaly table | 80% |
| **Orchestrator** | Route queries, coordinate agents, synthesize responses | All agents | 90% |

### LLM Prompts

Each agent uses specialized system prompts:

**Data Analyst:**
```
You are a cost data analyst. Analyze the provided cost data and answer 
the user's question. Provide clear, concise insights with specific numbers. 
Highlight trends, anomalies, and actionable items.
```

**Budget Advisor:**
```
You are a budget advisor. Analyze budget status and provide:
1. Current budget health
2. Risk assessment
3. Forecast for end of month
4. Recommendations to stay on budget
```

**Optimizer:**
```
You are a cost optimization expert. Based on existing recommendations 
and user query, provide specific, actionable advice. Prioritize by 
potential savings and ease of implementation.
```

---

## 🧪 Testing the Chat System

### Unit Tests

```powershell
# Test individual agents
pytest tests/test_multi_agent_system.py -v

# Test API endpoints
pytest tests/test_chat_api.py -v
```

### Manual Testing

```powershell
# Test REST endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are my costs this month?"}'

# Test WebSocket
python test_websocket_chat.py
```

### Example Test Queries

- ✅ "What's my total spend?"
- ✅ "Show me costs by service"
- ✅ "Are we over budget?"
- ✅ "Why did costs spike yesterday?"
- ✅ "How can I reduce costs by 15%?"
- ✅ "What are the top 3 optimization opportunities?"
- ✅ "Compare this month vs last month"
- ✅ "Forecast costs for next quarter"

---

## 📊 Performance & Scalability

### Response Times

| Query Complexity | Agents Involved | Avg Response Time |
|-----------------|-----------------|-------------------|
| Simple (total cost) | 1 agent | 1-2 seconds |
| Medium (budget status) | 2 agents | 2-4 seconds |
| Complex (optimization) | 3-4 agents | 4-6 seconds |
| Multi-part analysis | All agents | 6-8 seconds |

### Optimization Strategies

1. **Agent Parallelization** - Agents run concurrently using `asyncio.gather()`
2. **Database Query Caching** - Frequent queries cached with Redis (optional)
3. **LLM Response Caching** - Similar questions return cached responses
4. **Token Optimization** - Minimize prompt tokens while maintaining quality

### Cost Analysis

**Azure OpenAI Costs:**
- Average query: 2,000 tokens (input) + 500 tokens (output)
- GPT-4 pricing: ~$0.03 per 1K input tokens, ~$0.06 per 1K output tokens
- Per query cost: ~$0.09
- 1,000 queries/month: ~$90

**ROI:** Time saved by instant answers vs manual analysis = 100X+ value

---

## 🔒 Security Considerations

### Authentication

Add authentication to chat endpoints:

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.post("/chat")
async def chat(
    request: ChatRequest,
    token: str = Depends(security),
    session: Session = Depends(get_session)
):
    # Verify token
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    ...
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(...):
    ...
```

### Data Privacy

- Agent memory is session-scoped (not persistent across sessions)
- No user data logged to external services
- Azure OpenAI doesn't train on your data (opt-out agreement)
- Database queries respect row-level security

---

## 🐛 Troubleshooting

### Issue: "Azure OpenAI credentials not configured"

**Solution:**
```powershell
# Set environment variables
$env:AZURE_OPENAI_KEY="your-key"
$env:AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"

# Restart API
python -m uvicorn src.monitoring.api.main:app --reload
```

### Issue: Chat returns "Failed to process query"

**Solution:**
1. Check API logs for detailed error
2. Verify database connection
3. Ensure cost_records table has data
4. Test Azure OpenAI connection:

```python
from openai import AzureOpenAI
client = AzureOpenAI(...)
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "test"}]
)
print(response)
```

### Issue: Slow response times (>10 seconds)

**Solution:**
1. Check database query performance
2. Reduce number of agents involved
3. Implement response caching
4. Use GPT-3.5-turbo instead of GPT-4 for faster responses

---

## 🚀 Future Enhancements

### Phase 2 Features

- [ ] **Voice input** - Talk to the AI agent
- [ ] **Multi-modal responses** - Include charts and graphs in responses
- [ ] **Proactive notifications** - Agent sends alerts when it detects issues
- [ ] **Action execution** - "Shut down these 5 VMs" → Agent executes via Azure API
- [ ] **Multi-language support** - Chat in Spanish, French, German, etc.
- [ ] **Agent learning** - Agents improve based on user feedback
- [ ] **Custom agent creation** - Users define their own specialist agents

### Integration Roadmap

- Microsoft Teams bot integration
- Slack app integration
- Mobile app (iOS/Android)
- Chrome extension for quick access
- Email digest with chat summary

---

## 📚 Additional Resources

- **Azure OpenAI Documentation**: https://learn.microsoft.com/en-us/azure/ai-services/openai/
- **Multi-Agent Systems**: https://en.wikipedia.org/wiki/Multi-agent_system
- **FastAPI WebSockets**: https://fastapi.tiangolo.com/advanced/websockets/
- **Grafana Embedding**: https://grafana.com/docs/grafana/latest/panels-visualizations/

---

## 🤝 Support

For questions or issues with the chat system:

1. Check logs: `docker logs azure-cost-api`
2. Review API docs: http://localhost:8000/docs
3. Test agents individually using unit tests
4. Open GitHub issue with error details

**Happy chatting with your AI cost assistant! 🤖💬**
