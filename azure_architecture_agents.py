"""
Three-Agent Collaborative System for Azure Architecture Proposal, Review, and Approval
Uses AutoGen framework for multi-agent orchestration with cost-awareness and execution reality
"""

import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import autogen
from datetime import datetime


@dataclass
class ArchitectureProposal:
    """Structure for architecture proposal from Agent 1"""
    architecture_overview: str
    recommended_services: Dict[str, str]
    cost_sensitive_components: List[Dict[str, Any]]
    risks_and_assumptions: List[str]
    design_decisions: List[Dict[str, str]]
    trade_offs: Dict[str, str]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ReviewAssessment:
    """Structure for review from Agent 2"""
    review_summary: str
    effort_assessment: str  # Low / Medium / High
    complexity_hotspots: List[Dict[str, str]]
    time_to_implement_estimate: str
    suggested_changes: List[Dict[str, str]]
    over_engineering_flags: List[str]
    hidden_costs: List[str]
    skill_gaps: List[str]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class FinalDecision:
    """Structure for final decision from Agent 3"""
    decision_status: str  # Approved / Approved with Changes / Rejected
    key_feedback: str
    mandatory_changes: List[str]
    deferred_items: List[str]
    post_implementation_watchlist: List[Dict[str, str]]
    execution_priority: str  # Critical / High / Medium / Low
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class AzureArchitectureAgentSystem:
    """
    Three-agent system for Azure architecture decision-making
    Agent 1: Azure Architecture & Recommendations Agent
    Agent 2: Reviewer Agent (Effort, Complexity, Time)
    Agent 3: Final Approver & Decision Agent
    """
    
    def __init__(self, config_list: Optional[List[Dict]] = None, work_dir: str = "./agent_outputs"):
        """
        Initialize the three-agent system
        
        Args:
            config_list: AutoGen LLM configuration (Azure OpenAI, OpenAI, etc.)
            work_dir: Directory for agent outputs and collaboration artifacts
        """
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)
        
        # Default to environment-based config if not provided
        if config_list is None:
            config_list = self._get_default_config()
        
        self.config_list = config_list
        
        # Initialize agents
        self.architecture_agent = self._create_architecture_agent()
        self.reviewer_agent = self._create_reviewer_agent()
        self.approver_agent = self._create_approver_agent()
        self.user_proxy = self._create_user_proxy()
        
        # Store conversation history
        self.proposal: Optional[ArchitectureProposal] = None
        self.review: Optional[ReviewAssessment] = None
        self.decision: Optional[FinalDecision] = None
    
    def _get_default_config(self) -> List[Dict]:
        """Get default AutoGen config from environment variables"""
        # Try multiple environment variable names for compatibility
        api_key = (os.getenv("AZURE_OPENAI_API_KEY") or 
                   os.getenv("AZURE_OPENAI_KEY") or 
                   os.getenv("OPENAI_API_KEY"))
        api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        
        if api_base:  # Azure OpenAI
            return [{
                "model": model,
                "api_key": api_key,
                "base_url": api_base,
                "api_type": "azure",
                "api_version": api_version
            }]
        else:  # OpenAI
            return [{
                "model": "gpt-4-turbo-preview",
                "api_key": api_key
            }]
    
    def _create_architecture_agent(self) -> autogen.AssistantAgent:
        """Create Agent 1: Azure Architecture & Recommendations Agent"""
        system_message = """You are a Senior Azure Cloud Architect with 15+ years of experience.

Your role is to propose end-to-end Azure architecture solutions with BRUTAL HONESTY about costs and complexity.

CRITICAL RULES:
1. **Cost Awareness First**: Explicitly call out expensive services (Azure Kubernetes Service, Azure Databricks, Azure Synapse, Cosmos DB with high RU/s, etc.)
2. **No Hand-Waving**: Never say "highly scalable" without explaining HOW (scale sets, app service plans, partitioning strategy)
3. **Challenge Azure Defaults**: Azure's "recommended" option is often enterprise-grade and expensive. Question it.
4. **Managed vs DIY Trade-offs**: Justify every managed service with operational cost vs engineering time
5. **Real Numbers**: When possible, estimate instance counts, storage sizes, request volumes
6. **Failure Modes**: What breaks first? What's the single point of failure?

OUTPUT STRUCTURE (JSON):
{
    "architecture_overview": "3-5 sentence summary of the solution",
    "recommended_services": {
        "compute": "Service name and tier with justification",
        "storage": "...",
        "database": "...",
        "networking": "...",
        "monitoring": "...",
        "security": "..."
    },
    "cost_sensitive_components": [
        {
            "service": "Azure Kubernetes Service",
            "why_expensive": "24/7 control plane costs ~$70/month + nodes",
            "cheaper_alternative": "Azure Container Apps (consumption-based)",
            "recommendation": "Use AKS only if multi-cluster or complex networking required"
        }
    ],
    "design_decisions": [
        {"decision": "Use Azure SQL Database Serverless", "rationale": "Auto-pause for dev/test, pay-per-second"}
    ],
    "trade_offs": {
        "performance_vs_cost": "Serverless adds cold start latency but saves 70% in non-prod",
        "scalability_vs_complexity": "Container Apps simpler than AKS but less control over networking"
    },
    "risks_and_assumptions": [
        "Assumes < 10K requests/day; if higher, reassess compute tier",
        "No multi-region requirement; adding geo-replication increases cost 3-4x"
    ]
}

Be SPECIFIC. Be HONEST. Challenge assumptions.
"""
        
        return autogen.AssistantAgent(
            name="AzureArchitect",
            system_message=system_message,
            llm_config={
                "config_list": self.config_list,
                "temperature": 0.7,
                "timeout": 120
            }
        )
    
    def _create_reviewer_agent(self) -> autogen.AssistantAgent:
        """Create Agent 2: Reviewer Agent (Effort, Complexity, Time)"""
        system_message = """You are a Principal Engineer and Delivery Reviewer with battle scars from failed projects.

Your role is to BRUTALLY ASSESS the proposed architecture for REAL-WORLD EXECUTION.

CRITICAL RULES:
1. **Challenge Over-Engineering**: Is this NASA or a startup? Call out unnecessary complexity.
2. **Hidden Costs Surface**: "Serverless" isn't free. Data egress costs. VPN Gateway costs $140/month.
3. **Skill Gaps Kill Projects**: Does the team know Terraform? Kubernetes? Bicep? Call it out.
4. **Time Estimates Are Real**: Don't say "2 weeks" for setting up AKS + Istio + monitoring. Say "6-8 weeks".
5. **Operational Burden**: Who's on-call? Who patches? Who rotates secrets?
6. **Can This Actually Ship?**: Be honest. Some architectures look great on paper but die in prod.

OUTPUT STRUCTURE (JSON):
{
    "review_summary": "3-4 sentence critical assessment",
    "effort_assessment": "High",  // Low / Medium / High
    "complexity_hotspots": [
        {
            "area": "Kubernetes networking with Azure CNI",
            "complexity_level": "High",
            "why": "Requires deep understanding of pod networking, network policies, and Azure VNET integration",
            "mitigation": "Use Azure Container Apps instead unless hard requirement for K8s"
        }
    ],
    "time_to_implement_estimate": "8-10 weeks for MVP with 2 engineers",
    "suggested_changes": [
        {
            "change": "Replace Azure Kubernetes Service with Azure Container Apps",
            "rationale": "80% simpler, 60% cheaper, 90% faster to market",
            "impact": "Lose some Kubernetes ecosystem tooling but gain managed scaling and certs"
        }
    ],
    "over_engineering_flags": [
        "Multi-region active-active is overkill for < 100K users",
        "Azure Front Door premium tier not needed without WAF requirements"
    ],
    "hidden_costs": [
        "VPN Gateway: $140/month minimum",
        "Azure Firewall: $1.25/hour = $900/month",
        "Log Analytics ingestion: $2.76/GB after 5GB/day free tier"
    ],
    "skill_gaps": [
        "Team has no Terraform experience; steep learning curve",
        "No one knows Azure Networking (VNET peering, private endpoints)",
        "Monitoring/alerting strategy undefined"
    ]
}

Be BLUNT. Be REALISTIC. Kill architectural fantasy.
"""
        
        return autogen.AssistantAgent(
            name="EngineeringReviewer",
            system_message=system_message,
            llm_config={
                "config_list": self.config_list,
                "temperature": 0.6,
                "timeout": 120
            }
        )
    
    def _create_approver_agent(self) -> autogen.AssistantAgent:
        """Create Agent 3: Final Approver & Decision Agent"""
        system_message = """You are a Staff+ Architect and Engineering Leader responsible for FINAL APPROVAL.

Your role is to MAKE THE CALL: Ship it, fix it, or kill it.

CRITICAL RULES:
1. **Balance Business Value vs Engineering Perfectionism**: Perfect is the enemy of shipped.
2. **Explicit Trade-offs**: Make trade-offs visible. "We accept X risk to gain Y speed."
3. **Defer Non-Critical Items**: Not everything needs to be done in v1. Call out what can wait.
4. **Post-Launch Monitoring**: What metrics MUST be watched? Cost? Latency? Error rate?
5. **Decision Clarity**: No ambiguity. State "Approved", "Approved with Changes", or "Rejected".
6. **Mandatory Changes Are Mandatory**: If something MUST change before launch, say it clearly.

OUTPUT STRUCTURE (JSON):
{
    "decision_status": "Approved with Changes",  // Approved / Approved with Changes / Rejected
    "key_feedback": "Overall assessment in 3-4 sentences",
    "mandatory_changes": [
        "Must replace AKS with Container Apps to meet Q1 launch deadline",
        "Must add cost alerting (Azure Budget alerts) before deploying to production",
        "Must document runbook for scaling up/down during traffic spikes"
    ],
    "deferred_items": [
        "Multi-region can be deferred to Q2 after validating single-region performance",
        "Advanced monitoring (APM) can start with basic App Insights, upgrade later",
        "Disaster recovery (geo-redundant backups) defer until product-market fit"
    ],
    "post_implementation_watchlist": [
        {
            "metric": "Azure Cost per Day",
            "threshold": "$50/day",
            "action": "Investigate if exceeded; check for runaway resources"
        },
        {
            "metric": "Database DTU Usage",
            "threshold": "80% sustained for 1 hour",
            "action": "Scale up tier or optimize queries"
        },
        {
            "metric": "Container App Cold Start Latency",
            "threshold": "> 3 seconds",
            "action": "Consider switching to always-on instances"
        }
    ],
    "execution_priority": "High"  // Critical / High / Medium / Low
}

Be DECISIVE. Be CLEAR. Focus on shipping.
"""
        
        return autogen.AssistantAgent(
            name="FinalApprover",
            system_message=system_message,
            llm_config={
                "config_list": self.config_list,
                "temperature": 0.5,
                "timeout": 120
            }
        )
    
    def _create_user_proxy(self) -> autogen.UserProxyAgent:
        """Create user proxy for human-in-the-loop"""
        return autogen.UserProxyAgent(
            name="User",
            human_input_mode="NEVER",  # Set to "ALWAYS" for interactive mode
            max_consecutive_auto_reply=0,
            code_execution_config=False
        )
    
    def propose_architecture(self, problem_statement: str) -> ArchitectureProposal:
        """
        Agent 1: Propose architecture based on problem statement
        
        Args:
            problem_statement: Detailed description of the problem to solve
            
        Returns:
            ArchitectureProposal object
        """
        print("\n" + "="*80)
        print("AGENT 1: AZURE ARCHITECTURE & RECOMMENDATIONS")
        print("="*80 + "\n")
        
        prompt = f"""
PROBLEM STATEMENT:
{problem_statement}

Propose an end-to-end Azure architecture solution following the guidelines.
Output your response as a valid JSON object matching the specified structure.
Be explicit about costs, trade-offs, and assumptions.
"""
        
        # Initiate chat with architecture agent
        self.user_proxy.initiate_chat(
            self.architecture_agent,
            message=prompt,
            max_turns=1
        )
        
        # Extract proposal from last message
        last_message = self.architecture_agent.last_message()["content"]
        
        # Save raw output
        with open(f"{self.work_dir}/01_architecture_proposal.txt", "w") as f:
            f.write(last_message)
        
        # Parse JSON response (simplified - in production, add error handling)
        try:
            proposal_data = self._extract_json(last_message)
            self.proposal = ArchitectureProposal(**proposal_data)
            
            with open(f"{self.work_dir}/01_architecture_proposal.json", "w") as f:
                json.dump(asdict(self.proposal), f, indent=2)
        except Exception as e:
            print(f"Warning: Could not parse proposal as structured data: {e}")
            # Store as text-based proposal
            self.proposal = ArchitectureProposal(
                architecture_overview=last_message[:500],
                recommended_services={},
                cost_sensitive_components=[],
                risks_and_assumptions=[],
                design_decisions=[],
                trade_offs={}
            )
        
        return self.proposal
    
    def review_proposal(self) -> ReviewAssessment:
        """
        Agent 2: Review the architecture proposal critically
        
        Returns:
            ReviewAssessment object
        """
        if self.proposal is None:
            raise ValueError("No proposal to review. Call propose_architecture() first.")
        
        print("\n" + "="*80)
        print("AGENT 2: ENGINEERING REVIEW (EFFORT, COMPLEXITY, TIME)")
        print("="*80 + "\n")
        
        # Read the proposal output
        with open(f"{self.work_dir}/01_architecture_proposal.txt", "r") as f:
            proposal_text = f.read()
        
        prompt = f"""
ARCHITECTURE PROPOSAL TO REVIEW:
{proposal_text}

Critically assess this proposal for real-world execution.
Focus on: effort, complexity, time to implement, hidden costs, and skill gaps.
Output your response as a valid JSON object matching the specified structure.
Be BLUNT and REALISTIC.
"""
        
        # Initiate chat with reviewer agent
        self.user_proxy.initiate_chat(
            self.reviewer_agent,
            message=prompt,
            max_turns=1
        )
        
        # Extract review from last message
        last_message = self.reviewer_agent.last_message()["content"]
        
        # Save raw output
        with open(f"{self.work_dir}/02_engineering_review.txt", "w") as f:
            f.write(last_message)
        
        # Parse JSON response
        try:
            review_data = self._extract_json(last_message)
            self.review = ReviewAssessment(**review_data)
            
            with open(f"{self.work_dir}/02_engineering_review.json", "w") as f:
                json.dump(asdict(self.review), f, indent=2)
        except Exception as e:
            print(f"Warning: Could not parse review as structured data: {e}")
            self.review = ReviewAssessment(
                review_summary=last_message[:500],
                effort_assessment="Unknown",
                complexity_hotspots=[],
                time_to_implement_estimate="Unknown",
                suggested_changes=[],
                over_engineering_flags=[],
                hidden_costs=[],
                skill_gaps=[]
            )
        
        return self.review
    
    def approve_or_reject(self) -> FinalDecision:
        """
        Agent 3: Make final decision on the architecture
        
        Returns:
            FinalDecision object
        """
        if self.proposal is None or self.review is None:
            raise ValueError("Need both proposal and review before approval. Run previous steps first.")
        
        print("\n" + "="*80)
        print("AGENT 3: FINAL APPROVAL & DECISION")
        print("="*80 + "\n")
        
        # Read both previous outputs
        with open(f"{self.work_dir}/01_architecture_proposal.txt", "r") as f:
            proposal_text = f.read()
        
        with open(f"{self.work_dir}/02_engineering_review.txt", "r") as f:
            review_text = f.read()
        
        prompt = f"""
ARCHITECTURE PROPOSAL:
{proposal_text}

ENGINEERING REVIEW:
{review_text}

Make the final decision: Approved, Approved with Changes, or Rejected.
Provide clear, actionable feedback.
Specify mandatory changes, deferred items, and post-implementation monitoring.
Output your response as a valid JSON object matching the specified structure.
Be DECISIVE and CLEAR.
"""
        
        # Initiate chat with approver agent
        self.user_proxy.initiate_chat(
            self.approver_agent,
            message=prompt,
            max_turns=1
        )
        
        # Extract decision from last message
        last_message = self.approver_agent.last_message()["content"]
        
        # Save raw output
        with open(f"{self.work_dir}/03_final_decision.txt", "w") as f:
            f.write(last_message)
        
        # Parse JSON response
        try:
            decision_data = self._extract_json(last_message)
            self.decision = FinalDecision(**decision_data)
            
            with open(f"{self.work_dir}/03_final_decision.json", "w") as f:
                json.dump(asdict(self.decision), f, indent=2)
        except Exception as e:
            print(f"Warning: Could not parse decision as structured data: {e}")
            self.decision = FinalDecision(
                decision_status="Unknown",
                key_feedback=last_message[:500],
                mandatory_changes=[],
                deferred_items=[],
                post_implementation_watchlist=[],
                execution_priority="Unknown"
            )
        
        return self.decision
    
    def run_full_cycle(self, problem_statement: str) -> Dict[str, Any]:
        """
        Run the complete three-agent cycle: Propose → Review → Approve
        
        Args:
            problem_statement: Detailed problem description
            
        Returns:
            Dictionary with all three outputs
        """
        print("\n" + "🚀 "*20)
        print("STARTING THREE-AGENT ARCHITECTURE REVIEW CYCLE")
        print("🚀 "*20 + "\n")
        
        # Sequential execution
        proposal = self.propose_architecture(problem_statement)
        review = self.review_proposal()
        decision = self.approve_or_reject()
        
        # Generate final summary report
        self._generate_summary_report()
        
        print("\n" + "✅ "*20)
        print(f"CYCLE COMPLETE - Decision: {decision.decision_status}")
        print(f"Outputs saved to: {self.work_dir}")
        print("✅ "*20 + "\n")
        
        return {
            "proposal": asdict(proposal) if proposal else None,
            "review": asdict(review) if review else None,
            "decision": asdict(decision) if decision else None,
            "output_directory": self.work_dir
        }
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from agent response (handles markdown code blocks)"""
        # Try to find JSON in markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_text = text[start:end].strip()
        else:
            # Try to find raw JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                json_text = text[start:end]
            else:
                raise ValueError("No JSON found in response")
        
        return json.loads(json_text)
    
    def _generate_summary_report(self):
        """Generate a human-readable summary report"""
        report_path = f"{self.work_dir}/00_SUMMARY_REPORT.md"
        
        with open(report_path, "w") as f:
            f.write("# Azure Architecture Review - Summary Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            # Decision Status
            if self.decision:
                f.write(f"## 🎯 Final Decision: **{self.decision.decision_status}**\n\n")
                f.write(f"**Priority:** {self.decision.execution_priority}\n\n")
                f.write(f"### Key Feedback\n{self.decision.key_feedback}\n\n")
                
                if self.decision.mandatory_changes:
                    f.write("### ⚠️ Mandatory Changes\n")
                    for change in self.decision.mandatory_changes:
                        f.write(f"- {change}\n")
                    f.write("\n")
                
                if self.decision.deferred_items:
                    f.write("### 📋 Deferred to Later\n")
                    for item in self.decision.deferred_items:
                        f.write(f"- {item}\n")
                    f.write("\n")
            
            # Review Summary
            if self.review:
                f.write("---\n\n")
                f.write(f"## 🔍 Engineering Review\n\n")
                f.write(f"**Effort:** {self.review.effort_assessment}  \n")
                f.write(f"**Time Estimate:** {self.review.time_to_implement_estimate}\n\n")
                f.write(f"{self.review.review_summary}\n\n")
                
                if self.review.hidden_costs:
                    f.write("### 💰 Hidden Costs Identified\n")
                    for cost in self.review.hidden_costs:
                        f.write(f"- {cost}\n")
                    f.write("\n")
            
            # Architecture Overview
            if self.proposal:
                f.write("---\n\n")
                f.write("## 🏗️ Proposed Architecture\n\n")
                f.write(f"{self.proposal.architecture_overview}\n\n")
                
                if self.proposal.cost_sensitive_components:
                    f.write("### 💸 Cost-Sensitive Components\n")
                    for comp in self.proposal.cost_sensitive_components:
                        f.write(f"- **{comp.get('service', 'Unknown')}**: {comp.get('why_expensive', 'N/A')}\n")
                    f.write("\n")
            
            f.write("---\n\n")
            f.write("## 📁 Detailed Outputs\n\n")
            f.write("- `01_architecture_proposal.json` - Full architecture proposal\n")
            f.write("- `02_engineering_review.json` - Detailed review assessment\n")
            f.write("- `03_final_decision.json` - Final decision and action items\n\n")
        
        print(f"\n📊 Summary report generated: {report_path}")


def main():
    """Example usage of the three-agent system"""
    
    # Example problem statement
    problem_statement = """
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
    
    # Initialize the agent system
    system = AzureArchitectureAgentSystem(
        work_dir="./azure_architecture_review"
    )
    
    # Run the full cycle
    results = system.run_full_cycle(problem_statement)
    
    # Print final decision
    print("\n" + "="*80)
    print("FINAL DECISION SUMMARY")
    print("="*80)
    print(f"\nStatus: {results['decision']['decision_status']}")
    print(f"Priority: {results['decision']['execution_priority']}")
    print(f"\nKey Feedback:\n{results['decision']['key_feedback']}")
    
    if results['decision']['mandatory_changes']:
        print("\n⚠️  MANDATORY CHANGES:")
        for change in results['decision']['mandatory_changes']:
            print(f"  - {change}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
