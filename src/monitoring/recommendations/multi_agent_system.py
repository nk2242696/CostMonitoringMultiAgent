"""
Multi-Agent System for Cost Analysis
Agentic architecture where specialized agents collaborate to answer user queries
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field

from openai import AsyncAzureOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.monitoring.storage.models import CostRecord, AIRecommendation, CostBudget, Anomaly

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Agent roles in the multi-agent system"""
    ORCHESTRATOR = "orchestrator"  # Coordinates other agents
    DATA_ANALYST = "data_analyst"  # Queries and analyzes cost data
    BUDGET_ADVISOR = "budget_advisor"  # Budget tracking and forecasting
    ANOMALY_DETECTOR = "anomaly_detector"  # Identifies unusual patterns
    OPTIMIZER = "optimizer"  # Generates cost optimization recommendations
    COMMUNICATOR = "communicator"  # Formats responses for users


class AgentMessage(BaseModel):
    """Message passed between agents"""
    from_agent: AgentRole
    to_agent: AgentRole
    content: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    """Response from an agent"""
    agent: AgentRole
    success: bool
    content: str
    data: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    needs_followup: bool = False


class BaseAgent:
    """Base class for all agents"""
    
    def __init__(self, role: AgentRole, azure_client: AsyncAzureOpenAI, db_session: Session, deployment: str = "gpt-4o"):
        self.role = role
        self.client = azure_client
        self.db = db_session
        self.deployment = deployment
        self.memory: List[AgentMessage] = []
        
    async def process(self, message: AgentMessage) -> AgentResponse:
        """Process a message and return response"""
        raise NotImplementedError
    
    def add_to_memory(self, message: AgentMessage):
        """Add message to agent's memory"""
        self.memory.append(message)
        # Keep only last 10 messages
        if len(self.memory) > 10:
            self.memory = self.memory[-10:]


class DataAnalystAgent(BaseAgent):
    """Agent responsible for querying and analyzing cost data"""
    
    def __init__(self, azure_client: AsyncAzureOpenAI, db_session: Session, deployment: str = "gpt-4o"):
        super().__init__(AgentRole.DATA_ANALYST, azure_client, db_session, deployment)
    
    async def process(self, message: AgentMessage) -> AgentResponse:
        """Analyze cost data based on user query"""
        self.add_to_memory(message)
        
        try:
            # Extract intent using LLM
            intent = await self._extract_intent(message.content)
            
            # Query relevant data
            data = await self._query_data(intent)
            
            # Analyze with LLM
            analysis = await self._analyze_data(data, message.content)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                content=analysis,
                data=data,
                confidence=0.9
            )
            
        except Exception as e:
            logger.error(f"DataAnalystAgent error: {str(e)}")
            return AgentResponse(
                agent=self.role,
                success=False,
                content=f"Failed to analyze data: {str(e)}",
                confidence=0.0
            )
    
    async def _extract_intent(self, query: str) -> Dict[str, Any]:
        """Use LLM to extract intent from user query"""
        system_prompt = """You are a data analyst intent extractor. Analyze the user query and extract:
        - time_range: (today, this_week, this_month, last_month, last_3_months, last_year, custom)
        - metric: (total_cost, service_breakdown, mom_change, top_services, forecast, anomalies)
        - filters: {subscription_id, service_name, region}
        - aggregation: (daily, weekly, monthly)
        
        Return JSON only."""
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.1
        )
        
        import json
        return json.loads(response.choices[0].message.content)
    
    async def _query_data(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Query database based on intent"""
        time_range = intent.get("time_range", "this_month")
        metric = intent.get("metric", "total_cost")
        
        # Calculate date range
        end_date = datetime.utcnow()
        if time_range == "this_month":
            start_date = end_date.replace(day=1)
        elif time_range == "last_month":
            start_date = (end_date.replace(day=1) - timedelta(days=1)).replace(day=1)
            end_date = end_date.replace(day=1) - timedelta(days=1)
        elif time_range == "last_3_months":
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=30)
        
        result = {}
        
        # Total cost
        if metric in ["total_cost", "mom_change"]:
            total = self.db.query(func.sum(CostRecord.cost)).filter(
                CostRecord.date >= start_date,
                CostRecord.date <= end_date
            ).scalar() or 0
            result["total_cost"] = float(total)
            result["period"] = f"{start_date.date()} to {end_date.date()}"
        
        # Service breakdown
        if metric in ["service_breakdown", "top_services"]:
            services = self.db.query(
                CostRecord.service_name,
                func.sum(CostRecord.cost).label("total")
            ).filter(
                CostRecord.date >= start_date,
                CostRecord.date <= end_date
            ).group_by(CostRecord.service_name).order_by(desc("total")).limit(10).all()
            
            result["services"] = [
                {"service": s.service_name, "cost": float(s.total)}
                for s in services
            ]
        
        # MoM change
        if metric == "mom_change":
            prev_start = start_date - timedelta(days=30)
            prev_end = start_date - timedelta(days=1)
            
            prev_total = self.db.query(func.sum(CostRecord.cost)).filter(
                CostRecord.date >= prev_start,
                CostRecord.date <= prev_end
            ).scalar() or 0
            
            if prev_total > 0:
                result["mom_change_percent"] = ((result["total_cost"] - float(prev_total)) / float(prev_total)) * 100
                result["previous_period_cost"] = float(prev_total)
        
        return result
    
    async def _analyze_data(self, data: Dict[str, Any], query: str) -> str:
        """Use LLM to analyze data and generate insights"""
        system_prompt = """You are a cost data analyst. Analyze the provided cost data and answer the user's question.
        Provide clear, concise insights with specific numbers. Highlight trends, anomalies, and actionable items."""
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nData: {data}\n\nProvide analysis:"}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content


class BudgetAdvisorAgent(BaseAgent):
    """Agent responsible for budget tracking and forecasting"""
    
    def __init__(self, azure_client: AsyncAzureOpenAI, db_session: Session, deployment: str = "gpt-4o"):
        super().__init__(AgentRole.BUDGET_ADVISOR, azure_client, db_session, deployment)
    
    async def process(self, message: AgentMessage) -> AgentResponse:
        """Analyze budget status and provide forecasts"""
        self.add_to_memory(message)
        
        try:
            # Get active budgets
            budgets = self.db.query(CostBudget).filter(CostBudget.status == "active").all()
            
            if not budgets:
                return AgentResponse(
                    agent=self.role,
                    success=True,
                    content="No active budgets configured. Consider setting monthly budgets for your subscriptions to track spending.",
                    confidence=1.0
                )
            
            # Get current month costs
            start_date = datetime.utcnow().replace(day=1)
            current_cost = self.db.query(func.sum(CostRecord.cost)).filter(
                CostRecord.date >= start_date
            ).scalar() or 0
            
            # Analyze budget status
            budget_data = []
            for budget in budgets:
                utilization = (float(current_cost) / float(budget.amount)) * 100 if budget.amount else 0
                remaining = float(budget.amount or 0) - float(current_cost)
                
                budget_data.append({
                    "name": budget.name,
                    "amount": float(budget.amount),
                    "spent": float(current_cost),
                    "utilization": utilization,
                    "remaining": remaining,
                    "status": "over" if utilization > 100 else "warning" if utilization > 90 else "ok"
                })
            
            # Generate insights with LLM
            analysis = await self._generate_budget_insights(budget_data, message.content)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                content=analysis,
                data={"budgets": budget_data},
                confidence=0.95
            )
            
        except Exception as e:
            logger.error(f"BudgetAdvisorAgent error: {str(e)}")
            return AgentResponse(
                agent=self.role,
                success=False,
                content=f"Failed to analyze budget: {str(e)}",
                confidence=0.0
            )
    
    async def _generate_budget_insights(self, budget_data: List[Dict], query: str) -> str:
        """Generate budget insights using LLM"""
        system_prompt = """You are a budget advisor. Analyze budget status and provide:
        1. Current budget health
        2. Risk assessment
        3. Forecast for end of month
        4. Recommendations to stay on budget"""
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nBudget Data: {budget_data}\n\nProvide analysis:"}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content


class OptimizerAgent(BaseAgent):
    """Agent responsible for cost optimization recommendations"""
    
    def __init__(self, azure_client: AsyncAzureOpenAI, db_session: Session, deployment: str = "gpt-4o"):
        super().__init__(AgentRole.OPTIMIZER, azure_client, db_session, deployment)
    
    async def process(self, message: AgentMessage) -> AgentResponse:
        """Generate optimization recommendations"""
        self.add_to_memory(message)
        
        try:
            # Get existing AI recommendations (pending ones)
            recommendations = self.db.query(AIRecommendation).filter(
                AIRecommendation.status == "pending"
            ).order_by(desc(AIRecommendation.potential_savings)).limit(5).all()
            
            rec_data = [
                {
                    "title": rec.title,
                    "recommendation": rec.recommendation_text or "",
                    "description": (rec.description or "")[:2000],
                    "priority": rec.priority,
                    "savings": float(rec.potential_savings) if rec.potential_savings else 0,
                    "current_cost": float(rec.current_cost) if rec.current_cost else 0,
                    "category": rec.category,
                    "service": rec.service_name,
                    "effort": rec.implementation_effort,
                }
                for rec in recommendations
            ]
            
            # Generate contextual advice with LLM
            advice = await self._generate_optimization_advice(rec_data, message.content)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                content=advice,
                data={"recommendations": rec_data},
                confidence=0.85
            )
            
        except Exception as e:
            logger.error(f"OptimizerAgent error: {str(e)}")
            return AgentResponse(
                agent=self.role,
                success=False,
                content=f"Failed to generate recommendations: {str(e)}",
                confidence=0.0
            )
    
    async def _generate_optimization_advice(self, recommendations: List[Dict], query: str) -> str:
        """Generate personalized optimization advice"""
        system_prompt = """You are a cost optimization expert. Based on existing recommendations and user query,
        provide specific, actionable advice. Prioritize by potential savings and ease of implementation."""
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nRecommendations: {recommendations}\n\nProvide advice:"}
            ],
            temperature=0.4
        )
        
        return response.choices[0].message.content


class AnomalyDetectorAgent(BaseAgent):
    """Agent responsible for detecting cost anomalies"""
    
    def __init__(self, azure_client: AsyncAzureOpenAI, db_session: Session, deployment: str = "gpt-4o"):
        super().__init__(AgentRole.ANOMALY_DETECTOR, azure_client, db_session, deployment)
    
    async def process(self, message: AgentMessage) -> AgentResponse:
        """Detect and explain cost anomalies"""
        self.add_to_memory(message)
        
        try:
            # Get recent anomalies
            anomalies = self.db.query(Anomaly).filter(
                Anomaly.detected_at >= datetime.utcnow() - timedelta(days=7)
            ).order_by(desc(Anomaly.severity)).limit(5).all()
            
            anomaly_data = [
                {
                    "service": a.service_name,
                    "expected": float(a.expected_cost),
                    "actual": float(a.actual_cost),
                    "deviation": float(a.deviation_percentage),
                    "severity": a.severity,
                    "date": a.detected_at.isoformat()
                }
                for a in anomalies
            ]
            
            # Analyze with LLM
            analysis = await self._analyze_anomalies(anomaly_data, message.content)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                content=analysis,
                data={"anomalies": anomaly_data},
                confidence=0.8
            )
            
        except Exception as e:
            logger.error(f"AnomalyDetectorAgent error: {str(e)}")
            return AgentResponse(
                agent=self.role,
                success=False,
                content=f"Failed to detect anomalies: {str(e)}",
                confidence=0.0
            )
    
    async def _analyze_anomalies(self, anomalies: List[Dict], query: str) -> str:
        """Analyze anomalies with LLM"""
        system_prompt = """You are an anomaly detection expert. Analyze cost anomalies and explain:
        1. What caused the anomaly
        2. Whether it's expected or concerning
        3. Recommended actions"""
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nAnomalies: {anomalies}\n\nProvide analysis:"}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content


class OrchestratorAgent(BaseAgent):
    """Orchestrator that coordinates other agents"""
    
    def __init__(self, azure_client: AsyncAzureOpenAI, db_session: Session, deployment: str = "gpt-4o"):
        super().__init__(AgentRole.ORCHESTRATOR, azure_client, db_session, deployment)
        self.agents: Dict[AgentRole, BaseAgent] = {}
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the orchestrator"""
        self.agents[agent.role] = agent
    
    async def process(self, message: AgentMessage) -> AgentResponse:
        """Coordinate agents to answer user query"""
        self.add_to_memory(message)
        
        try:
            # Determine which agents to involve
            agents_to_query = await self._determine_agents(message.content)
            
            # Query agents in parallel
            tasks = [
                self.agents[agent_role].process(AgentMessage(
                    from_agent=self.role,
                    to_agent=agent_role,
                    content=message.content
                ))
                for agent_role in agents_to_query
                if agent_role in self.agents
            ]
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine responses
            combined_response = await self._synthesize_responses(message.content, responses)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                content=combined_response,
                confidence=0.9
            )
            
        except Exception as e:
            logger.error(f"OrchestratorAgent error: {str(e)}")
            return AgentResponse(
                agent=self.role,
                success=False,
                content=f"Failed to process query: {str(e)}",
                confidence=0.0
            )
    
    async def _determine_agents(self, query: str) -> List[AgentRole]:
        """Determine which agents should handle the query"""
        system_prompt = """You are an orchestrator. Given a user query about cloud costs, determine which agents should be involved:
        - data_analyst: For queries about costs, trends, breakdowns
        - budget_advisor: For queries about budgets, forecasts, spending limits
        - optimizer: For queries about cost reduction, optimization recommendations
        - anomaly_detector: For queries about unusual spending, spikes, or anomalies
        
        Return JSON array of agent roles needed. Example: ["data_analyst", "budget_advisor"]"""
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nWhich agents are needed?"}
            ],
            temperature=0.1
        )
        
        import json
        agent_names = json.loads(response.choices[0].message.content)
        return [AgentRole(name) for name in agent_names]
    
    async def _synthesize_responses(self, query: str, responses: List[AgentResponse]) -> str:
        """Synthesize multiple agent responses into coherent answer"""
        # Filter successful responses
        successful = [r for r in responses if isinstance(r, AgentResponse) and r.success]
        
        if not successful:
            return "I wasn't able to gather enough information to answer your question. Please try rephrasing."
        
        # Combine insights
        combined_content = "\n\n".join([
            f"**From {r.agent.value}:**\n{r.content}"
            for r in successful
        ])
        
        # Synthesize with LLM
        system_prompt = """You are a communicator agent. Synthesize insights from multiple specialist agents into a coherent,
        conversational response. Be concise but comprehensive. Use bullet points for clarity. Include specific numbers."""
        
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Query: {query}\n\nAgent Insights:\n{combined_content}\n\nSynthesize response:"}
            ],
            temperature=0.4
        )
        
        return response.choices[0].message.content


class MultiAgentSystem:
    """Multi-agent system for cost analysis — supports Azure OpenAI and Claude"""
    
    def __init__(self, azure_openai_key: str = None, azure_openai_endpoint: str = None, db_session: Session = None):
        import os
        self.db = db_session
        self.fallback_only = False
        
        # ------------------------------------------------------------------
        # Priority: 1) Anthropic Claude  2) Azure OpenAI  3) Fallback
        # ------------------------------------------------------------------
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        claude_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        
        if anthropic_key:
            # ── Use Claude ──
            from src.monitoring.recommendations.claude_adapter import ClaudeAdapter
            self.client = ClaudeAdapter(api_key=anthropic_key, model=claude_model)
            self.deployment = claude_model
            self.orchestrator = OrchestratorAgent(self.client, db_session, self.deployment)
            self.orchestrator.register_agent(DataAnalystAgent(self.client, db_session, self.deployment))
            self.orchestrator.register_agent(BudgetAdvisorAgent(self.client, db_session, self.deployment))
            self.orchestrator.register_agent(OptimizerAgent(self.client, db_session, self.deployment))
            self.orchestrator.register_agent(AnomalyDetectorAgent(self.client, db_session, self.deployment))
            logger.info("MultiAgentSystem using Claude (%s)", claude_model)
            return
        
        # ── Check for Azure OpenAI ──
        key = azure_openai_key or os.getenv('AZURE_OPENAI_KEY', '')
        endpoint = azure_openai_endpoint or os.getenv('AZURE_OPENAI_ENDPOINT', '')
        
        if key and endpoint:
            self.deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
            self.client = AsyncAzureOpenAI(
                api_key=key,
                api_version="2024-02-15-preview",
                azure_endpoint=endpoint
            )
            self.orchestrator = OrchestratorAgent(self.client, db_session, self.deployment)
            self.orchestrator.register_agent(DataAnalystAgent(self.client, db_session, self.deployment))
            self.orchestrator.register_agent(BudgetAdvisorAgent(self.client, db_session, self.deployment))
            self.orchestrator.register_agent(OptimizerAgent(self.client, db_session, self.deployment))
            self.orchestrator.register_agent(AnomalyDetectorAgent(self.client, db_session, self.deployment))
            logger.info("MultiAgentSystem using Azure OpenAI (%s)", self.deployment)
            return
        
        # ── Fallback: no LLM available ──
        self.fallback_only = True
        self.client = None
        self.orchestrator = None
        logger.info("MultiAgentSystem in fallback-only mode (no LLM keys configured)")
    
    async def query(self, user_message: str) -> str:
        """Process user query through multi-agent system"""
        # If in fallback-only mode, skip AI processing entirely
        if self.fallback_only:
            return self._fallback_response(user_message)
        
        try:
            message = AgentMessage(
                from_agent=AgentRole.COMMUNICATOR,
                to_agent=AgentRole.ORCHESTRATOR,
                content=user_message
            )
            
            response = await self.orchestrator.process(message)
            return response.content
        except Exception as e:
            # Fallback to rule-based responses if Azure OpenAI is unreachable
            logger.warning(f"Azure OpenAI unavailable, using fallback: {str(e)}")
            return self._fallback_response(user_message)
    
    def _fallback_response(self, query: str) -> str:
        """Provide rule-based response when Azure OpenAI is unavailable"""
        query_lower = query.lower()
        
        # Get basic cost data from database
        if self.db:
            total_cost = self.db.query(func.sum(CostRecord.cost)).scalar() or 0
            resource_count = self.db.query(func.count(func.distinct(CostRecord.resource_id))).scalar() or 0
            top_resources = self.db.query(
                CostRecord.service_name,
                func.sum(CostRecord.cost).label('total')
            ).group_by(CostRecord.service_name).order_by(desc('total')).limit(5).all()
        else:
            total_cost, resource_count, top_resources = 0, 0, []
        
        # Cost trends query
        if any(word in query_lower for word in ['trend', 'spending', 'cost over time', 'monthly']):
            return f"""📊 **Cost Analysis**

**Total Spending**: ${total_cost:,.2f}
**Resources Monitored**: {resource_count}

**Top Services by Cost**:
{chr(10).join([f'• {r.service_name}: ${r.total:,.2f}' for r in top_resources]) if top_resources else '• No cost data available'}

💡 **Quick Recommendations**:
• Review underutilized resources for potential savings
• Consider Reserved Instances for predictable workloads
• Enable auto-shutdown for development resources
• Implement tagging for better cost allocation"""

        # Top cost drivers
        elif any(word in query_lower for word in ['top', 'expensive', 'highest', 'cost driver']):
            top_list = chr(10).join([f'{i+1}. **{r.service_name}**: ${r.total:,.2f}' for i, r in enumerate(top_resources)]) if top_resources else 'No cost data available'
            return f"""💰 **Top Cost Drivers**

{top_list}

**Total Tracked**: ${total_cost:,.2f} across {resource_count} resources

💡 **Optimization Tips**:
• Analyze usage patterns for top services
• Consider right-sizing VMs
• Use spot instances for non-critical workloads
• Review storage tiers"""

        # Budget queries
        elif any(word in query_lower for word in ['budget', 'limit', 'threshold', 'alert']):
            budget = self.db.query(CostBudget).filter(CostBudget.status == "active").first() if self.db else None
            if budget:
                budget_amt = float(budget.amount or 0)
                pct = (float(total_cost) / budget_amt * 100) if budget_amt > 0 else 0
                return f"""💰 **Budget Status**

**Monthly Limit**: ${budget_amt:,.2f}
**Current Spending**: ${total_cost:,.2f}
**Budget Used**: {pct:.1f}%

{'🚨 **ALERT**: Over budget!' if pct > 100 else '⚠️ **WARNING**: Approaching limit' if pct > 80 else '✅ Within budget'}

💡 Configure alerts in Azure Portal for proactive monitoring."""
            else:
                return """💰 **Budget Management** (Rule-based)

No budget configured. Set a monthly budget to track spending and receive alerts.

**Recommended Actions**:
1. Set monthly budget limits
2. Configure alert thresholds (50%, 80%, 100%)
3. Review spending weekly
4. Implement cost controls"""

        # Optimization queries
        elif any(word in query_lower for word in ['optimize', 'save', 'reduce', 'lower']):
            return f"""🎯 **Cost Optimization Recommendations** (Rule-based)

**Current Spending**: ${total_cost:,.2f}

**Quick Wins**:
1. **Right-size resources** - Match VM sizes to actual workload
2. **Reserved Instances** - Save up to 72% on predictable workloads
3. **Auto-shutdown** - Stop dev/test resources during off-hours
4. **Storage optimization** - Move cold data to cool/archive tiers
5. **Delete unused resources** - Remove orphaned disks, IPs, etc.

**Monitoring**:
• Enable Azure Advisor recommendations
• Set up cost alerts
• Review Azure Cost Management reports

⚠️ AI-powered analysis unavailable - Azure OpenAI endpoint unreachable."""

        # Default response
        else:
            return f"""🤖 **Azure Cost Assistant**

**Current Status**:
• Total Spending: ${total_cost:,.2f}
• Resources Monitored: {resource_count}

**Try asking**:
• "What are my top cost drivers?"
• "Show me spending trends"
• "How is my budget?"
• "Recommend cost optimizations"
• "How can I reduce Synapse costs?"
• "What Spark jobs are most expensive?"
"""
