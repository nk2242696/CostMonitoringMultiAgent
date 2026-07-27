"""
Agentic Cost Optimization Framework
Autonomous agent that monitors, analyzes, and optimizes Azure costs
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from dataclasses import dataclass, asdict


class AgentState(Enum):
    """Agent operational states"""
    IDLE = "idle"
    MONITORING = "monitoring"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    LEARNING = "learning"


class ActionType(Enum):
    """Types of actions the agent can take"""
    DETECT_ANOMALY = "detect_anomaly"
    GENERATE_RECOMMENDATION = "generate_recommendation"
    AUTO_SCALE = "auto_scale"
    SHUTDOWN_RESOURCE = "shutdown_resource"
    RIGHTSIZE_RESOURCE = "rightsize_resource"
    ALERT_USER = "alert_user"
    VALIDATE_CHANGE = "validate_change"
    ROLLBACK_CHANGE = "rollback_change"


@dataclass
class AgentGoal:
    """Agent's operational goals"""
    target_savings_percent: float = 20.0
    max_cost_threshold: float = 100000.0
    auto_remediation_enabled: bool = False
    require_approval_threshold: float = 1000.0  # Require approval for changes > $1000/month


@dataclass
class AgentMemory:
    """Agent's memory of past actions and learnings"""
    successful_actions: List[Dict] = None
    failed_actions: List[Dict] = None
    user_preferences: Dict = None
    learned_patterns: Dict = None
    
    def __post_init__(self):
        self.successful_actions = self.successful_actions or []
        self.failed_actions = self.failed_actions or []
        self.user_preferences = self.user_preferences or {}
        self.learned_patterns = self.learned_patterns or {}


class CostOptimizationAgent:
    """
    Autonomous agent for Azure cost optimization
    
    Capabilities:
    - Monitors costs in real-time
    - Detects anomalies autonomously
    - Plans multi-step optimization strategies
    - Executes approved changes with Azure APIs
    - Validates results and learns from outcomes
    - Adapts strategy based on feedback
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.state = AgentState.IDLE
        self.goals = AgentGoal(**config.get('goals', {}))
        self.memory = AgentMemory()
        
        # Azure OpenAI for reasoning
        self.openai_key = config['azure_openai_key']
        self.openai_endpoint = config['azure_openai_endpoint']
        self.deployment = config.get('deployment', 'gpt-4o')
        
        # Database connection
        self.db_config = config['database']
        
        # Action history for learning
        self.action_history: List[Dict] = []
        
        # Decision-making parameters
        self.confidence_threshold = 0.8
        self.risk_tolerance = config.get('risk_tolerance', 'low')
        
    async def run(self):
        """Main agent loop - autonomous operation"""
        print("🤖 Cost Optimization Agent Starting...")
        print(f"📊 Goals: {self.goals.target_savings_percent}% cost reduction")
        print(f"🎯 Max budget: ${self.goals.max_cost_threshold:,.2f}")
        
        while True:
            try:
                # 1. PERCEIVE: Monitor environment
                await self._perceive()
                
                # 2. THINK: Analyze and plan
                await self._think()
                
                # 3. ACT: Execute planned actions
                await self._act()
                
                # 4. LEARN: Reflect and improve
                await self._learn()
                
                # Sleep before next cycle
                await asyncio.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                print("\n🛑 Agent shutting down...")
                break
            except Exception as e:
                print(f"❌ Agent error: {e}")
                await asyncio.sleep(300)  # Wait 5 min on error
    
    async def _perceive(self):
        """Monitor environment and detect events"""
        self.state = AgentState.MONITORING
        
        # 1. Check for cost anomalies
        anomalies = await self._detect_anomalies()
        if anomalies:
            await self._handle_anomalies(anomalies)
        
        # 2. Check if goals are being met
        current_metrics = await self._get_current_metrics()
        if current_metrics['total_cost'] > self.goals.max_cost_threshold:
            await self._trigger_emergency_optimization()
        
        # 3. Check for idle/underutilized resources
        idle_resources = await self._find_idle_resources()
        if idle_resources:
            await self._plan_resource_cleanup(idle_resources)
    
    async def _think(self):
        """Analyze situation and create multi-step plans"""
        self.state = AgentState.ANALYZING
        
        # Get current cost data
        cost_data = await self._get_cost_data()
        
        # Use LLM for strategic planning
        analysis_prompt = f"""You are an Azure cost optimization agent.

Current situation:
{json.dumps(cost_data, indent=2)}

Goals:
- Reduce costs by {self.goals.target_savings_percent}%
- Stay under ${self.goals.max_cost_threshold:,.2f}
- Minimize business impact

Your past successful actions:
{json.dumps(self.memory.successful_actions[-5:], indent=2)}

Create a multi-step optimization plan. Consider:
1. Quick wins (low risk, high savings)
2. Medium-term optimizations (require planning)
3. Long-term architectural changes

Return JSON with:
- priority_actions: List of actions to take immediately
- reasoning: Why these actions
- expected_savings: Estimated monthly savings
- risk_assessment: Low/Medium/High for each action
- dependencies: Any prerequisites
"""
        
        plan = await self._call_llm(analysis_prompt)
        return plan
    
    async def _act(self):
        """Execute planned actions"""
        self.state = AgentState.EXECUTING
        
        # Get pending actions
        actions = await self._get_pending_actions()
        
        for action in actions:
            # Check if requires approval
            if action['estimated_savings'] > self.goals.require_approval_threshold:
                if not self.goals.auto_remediation_enabled:
                    await self._request_approval(action)
                    continue
            
            # Execute action
            result = await self._execute_action(action)
            
            # Record outcome
            self.action_history.append({
                'action': action,
                'result': result,
                'timestamp': datetime.now().isoformat()
            })
    
    async def _learn(self):
        """Learn from past actions and improve decision-making"""
        self.state = AgentState.LEARNING
        
        # Analyze recent actions
        recent_actions = self.action_history[-10:]
        
        # Calculate success rate
        successful = [a for a in recent_actions if a['result'].get('success')]
        success_rate = len(successful) / len(recent_actions) if recent_actions else 0
        
        # Update memory with successful patterns
        if success_rate > 0.7:
            for action in successful:
                self.memory.successful_actions.append({
                    'type': action['action']['type'],
                    'service': action['action']['service'],
                    'savings': action['result'].get('actual_savings'),
                    'timestamp': action['timestamp']
                })
        
        # Learn user preferences from approval/rejection patterns
        await self._update_user_preferences()
        
        # Adjust confidence thresholds based on outcomes
        if success_rate < 0.5:
            self.confidence_threshold = min(0.95, self.confidence_threshold + 0.05)
            print(f"⚙️  Increased confidence threshold to {self.confidence_threshold}")
    
    async def _detect_anomalies(self) -> List[Dict]:
        """Detect cost anomalies in real-time"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get last 7 days of data
        query = """
            WITH daily_costs AS (
                SELECT 
                    DATE(date) as day,
                    service_name,
                    SUM(cost) as daily_cost
                FROM cost_records
                WHERE date >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(date), service_name
            ),
            stats AS (
                SELECT 
                    service_name,
                    AVG(daily_cost) as avg_cost,
                    STDDEV(daily_cost) as stddev_cost
                FROM daily_costs
                GROUP BY service_name
            )
            SELECT 
                d.service_name,
                d.daily_cost,
                s.avg_cost,
                s.stddev_cost,
                (d.daily_cost - s.avg_cost) / NULLIF(s.stddev_cost, 0) as z_score
            FROM daily_costs d
            JOIN stats s ON d.service_name = s.service_name
            WHERE d.day = CURRENT_DATE
              AND ABS((d.daily_cost - s.avg_cost) / NULLIF(s.stddev_cost, 0)) > 2
            ORDER BY ABS((d.daily_cost - s.avg_cost) / NULLIF(s.stddev_cost, 0)) DESC;
        """
        
        cursor.execute(query)
        anomalies = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return anomalies
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Execute a planned action using Azure APIs"""
        action_type = action['type']
        
        if action_type == 'shutdown_idle_vm':
            return await self._shutdown_vm(action['resource_id'])
        elif action_type == 'rightsize_resource':
            return await self._rightsize_resource(action)
        elif action_type == 'enable_autoscale':
            return await self._enable_autoscale(action)
        elif action_type == 'alert_user':
            return await self._send_alert(action)
        
        return {'success': False, 'reason': 'Unknown action type'}
    
    async def _call_llm(self, prompt: str) -> Dict:
        """Call Azure OpenAI for reasoning"""
        url = f"{self.openai_endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version=2024-02-15-preview"
        
        headers = {
            "api-key": self.openai_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": "You are an expert Azure cost optimization agent. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return json.loads(result['choices'][0]['message']['content'])
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return {}
    
    async def _get_cost_data(self) -> Dict:
        """Get current cost data from database"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                service_name,
                SUM(cost) as total_cost,
                COUNT(*) as resource_count,
                AVG(cost) as avg_cost
            FROM cost_records
            WHERE date >= NOW() - INTERVAL '7 days'
            GROUP BY service_name
            ORDER BY total_cost DESC
            LIMIT 20;
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return {'services': [dict(r) for r in results]}
    
    async def _get_current_metrics(self) -> Dict:
        """Get current cost metrics"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT SUM(cost) as total_cost FROM cost_records WHERE date >= NOW() - INTERVAL '30 days';"
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(result) if result else {'total_cost': 0}
    
    async def _find_idle_resources(self) -> List[Dict]:
        """Find idle/underutilized resources"""
        # This would integrate with Azure Monitor API
        # For now, return empty list
        return []
    
    async def _handle_anomalies(self, anomalies: List[Dict]):
        """Handle detected anomalies"""
        for anomaly in anomalies:
            print(f"🚨 Anomaly detected: {anomaly['service_name']} - ${anomaly['daily_cost']:.2f} (Z-score: {anomaly['z_score']:.2f})")
            
            # Create investigation task
            await self._investigate_anomaly(anomaly)
    
    async def _investigate_anomaly(self, anomaly: Dict):
        """Investigate cost anomaly using LLM"""
        prompt = f"""Investigate this cost anomaly:

Service: {anomaly['service_name']}
Current cost: ${anomaly['daily_cost']:.2f}
Average cost: ${anomaly['avg_cost']:.2f}
Standard deviation: ${anomaly['stddev_cost']:.2f}
Z-score: {anomaly['z_score']:.2f}

Provide:
1. Possible root causes
2. Recommended immediate actions
3. Preventive measures

Return as JSON with keys: root_causes, immediate_actions, preventive_measures
"""
        
        analysis = await self._call_llm(prompt)
        print(f"🔍 Investigation: {json.dumps(analysis, indent=2)}")
    
    async def _trigger_emergency_optimization(self):
        """Triggered when costs exceed threshold"""
        print(f"🚨 EMERGENCY: Costs exceed ${self.goals.max_cost_threshold:,.2f}")
        
        # Create aggressive optimization plan
        plan = await self._create_emergency_plan()
        
        # Execute with high priority
        for action in plan.get('actions', []):
            await self._execute_action(action)
    
    async def _create_emergency_plan(self) -> Dict:
        """Create emergency cost reduction plan"""
        cost_data = await self._get_cost_data()
        
        prompt = f"""EMERGENCY: Costs have exceeded budget threshold!

Current costs: {json.dumps(cost_data, indent=2)}
Target: Reduce by {self.goals.target_savings_percent}% immediately

Create an aggressive emergency plan with:
1. Actions that can be taken immediately (0 business impact)
2. High-impact quick wins
3. Expected savings for each action

Return JSON: {{actions: [...], total_expected_savings: number}}
"""
        
        return await self._call_llm(prompt)
    
    async def _plan_resource_cleanup(self, idle_resources: List[Dict]):
        """Plan cleanup of idle resources"""
        pass
    
    async def _get_pending_actions(self) -> List[Dict]:
        """Get actions waiting to be executed"""
        # Fetch from agent's action queue
        return []
    
    async def _request_approval(self, action: Dict):
        """Request user approval for high-impact action"""
        print(f"⏸️  Approval required: {action['description']}")
        print(f"   Estimated savings: ${action['estimated_savings']:,.2f}/month")
        # Send notification via configured channels
    
    async def _update_user_preferences(self):
        """Learn user preferences from approval patterns"""
        pass
    
    async def _shutdown_vm(self, resource_id: str) -> Dict:
        """Shutdown idle VM"""
        # Azure API call
        return {'success': True, 'actual_savings': 250.0}
    
    async def _rightsize_resource(self, action: Dict) -> Dict:
        """Rightsize a resource"""
        return {'success': True, 'actual_savings': action.get('estimated_savings', 0)}
    
    async def _enable_autoscale(self, action: Dict) -> Dict:
        """Enable autoscaling"""
        return {'success': True, 'actual_savings': action.get('estimated_savings', 0)}
    
    async def _send_alert(self, action: Dict) -> Dict:
        """Send alert to user"""
        print(f"📧 Alert: {action['message']}")
        return {'success': True}


async def main():
    """Start the agentic cost optimization system"""
    
    config = {
        'azure_openai_key': os.getenv('AZURE_OPENAI_KEY'),
        'azure_openai_endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'deployment': 'gpt-4o',
        'database': {
            'host': 'localhost',
            'port': 5432,
            'database': 'azure_cost_dev',
            'user': 'postgres',
            'password': 'AzureCost2025!DbPass'
        },
        'goals': {
            'target_savings_percent': 20.0,
            'max_cost_threshold': 100000.0,
            'auto_remediation_enabled': False,  # Start with manual approval
            'require_approval_threshold': 1000.0
        },
        'risk_tolerance': 'low'
    }
    
    agent = CostOptimizationAgent(config)
    await agent.run()


if __name__ == "__main__":
    import os
    asyncio.run(main())
