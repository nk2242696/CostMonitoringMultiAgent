"""
Simple Architecture Agent System using direct Azure OpenAI calls
No AutoGen dependency - works with your existing setup
"""
import os
import json
from openai import AzureOpenAI
from datetime import datetime


class SimpleArchitectureAgents:
    """Three-agent system without AutoGen framework"""
    
    def __init__(self):
        # Use correct Azure OpenAI endpoint
        self.azure_key = os.getenv("AZURE_OPENAI_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://kuamnuii.openai.azure.com/")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "o4-mini")
        
        # Try to initialize with Azure OpenAI
        try:
            if not self.azure_key:
                raise ValueError("AZURE_OPENAI_KEY environment variable is required")
            self.client = AzureOpenAI(
                api_key=self.azure_key,
                api_version="2025-01-01-preview",
                azure_endpoint=self.azure_endpoint,
                timeout=30.0
            )
            self.use_azure = True
            print(f"✅ Using Azure OpenAI: {self.azure_endpoint}")
            print(f"   Model: {self.deployment}")
        except Exception as e:
            print(f"⚠️  Azure OpenAI unavailable ({str(e)}), using OpenAI API instead")
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key:
                raise Exception("No valid API keys available. Set OPENAI_API_KEY environment variable.")
            from openai import OpenAI
            self.client = OpenAI(api_key=openai_key)
            self.deployment = "gpt-4o-mini"
            self.use_azure = False
        
        os.makedirs("./architecture_review", exist_ok=True)
    
    def agent_1_architecture_proposal(self, problem: str) -> str:
        """Agent 1: Azure Architecture & Recommendations"""
        print("\n" + "="*80)
        print("🏗️  AGENT 1: Azure Architecture & Recommendations Agent")
        print("="*80 + "\n")
        
        system_prompt = """You are a Senior Azure Cloud Architect with 15+ years of experience.

Your role is to propose end-to-end Azure architecture solutions with BRUTAL HONESTY about costs and complexity.

CRITICAL RULES:
1. **Cost Awareness First**: Explicitly call out expensive services
2. **No Hand-Waving**: Never say "highly scalable" without explaining HOW
3. **Challenge Azure Defaults**: Azure's "recommended" option is often expensive
4. **Real Numbers**: Estimate instance counts, storage sizes, request volumes
5. **Failure Modes**: What breaks first? What's the single point of failure?

OUTPUT STRUCTURE:
## Architecture Overview
[3-5 sentence summary]

## Recommended Azure Services
- **Compute**: [Service + tier + justification]
- **Storage**: [Service + tier + justification]
- **Database**: [Service + tier + justification]
- **Networking**: [Service + tier + justification]
- **Monitoring**: [Service + tier + justification]
- **Security**: [Service + tier + justification]

## Cost-Sensitive Components
1. [Component] - Estimated cost: $X/month - Why expensive: [reason]

## Design Decisions
1. [Decision]: [Rationale]

## Trade-offs
- **Performance vs Cost**: [explanation]
- **Scalability vs Complexity**: [explanation]
- **Managed vs DIY**: [explanation]

## Risks & Assumptions
1. [Risk/Assumption]

Be specific, honest, and numbers-driven."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": problem}
            ],
            max_completion_tokens=3000
        )
        
        proposal = response.choices[0].message.content
        
        # Save to file
        with open("./architecture_review/01_ARCHITECTURE_PROPOSAL.md", "w", encoding="utf-8") as f:
            f.write(f"# Architecture Proposal\n")
            f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
            f.write(proposal)
        
        print(proposal)
        return proposal
    
    def agent_2_review(self, problem: str, proposal: str) -> str:
        """Agent 2: Reviewer (Effort, Complexity, Time)"""
        print("\n" + "="*80)
        print("👨‍💻 AGENT 2: Reviewer Agent (Effort, Complexity, Time)")
        print("="*80 + "\n")
        
        system_prompt = """You are a Principal Engineer / Delivery Reviewer with brutal honesty.

Your job is to CRITICALLY evaluate architecture proposals for EXECUTION REALITY.

EVALUATION CRITERIA:
1. **Implementation Effort**: How much work is this really?
2. **Engineering Complexity**: What's hard? What requires expertise?
3. **Time to Deliver**: Realistic timeline with risks
4. **Over-Engineering**: What's unnecessarily complex?
5. **Hidden Costs**: Operational overhead, monitoring, maintenance
6. **Skill Gaps**: What skills does the team need?

BE BLUNT. Challenge assumptions. Prefer solutions teams can actually ship.

OUTPUT STRUCTURE:
## Review Summary
[3-5 sentence assessment]

## Effort Assessment: [Low / Medium / High]
[Justification]

## Complexity Hotspots
1. [Area]: [Why it's complex] - [Impact]

## Time-to-Implement Estimate
- **Setup & Infrastructure**: X weeks
- **Core Development**: X weeks
- **Integration & Testing**: X weeks
- **Total**: X weeks (with Y weeks buffer for unknowns)

## Suggested Changes
1. **[Area]**: [Current approach] → [Simpler alternative] - [Why better]

## Over-Engineering Flags
1. [What's over-engineered]

## Hidden Costs
1. [Operational cost not in architecture doc]

## Skill Gaps
1. [Required skill] - [Risk level]

Be realistic and challenge perfectionism."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"PROBLEM:\n{problem}\n\nPROPOSED ARCHITECTURE:\n{proposal}"}
            ],
            max_completion_tokens=3000
        )
        
        review = response.choices[0].message.content
        
        # Save to file
        with open("./architecture_review/02_REVIEW_ASSESSMENT.md", "w", encoding="utf-8") as f:
            f.write(f"# Review & Assessment\n")
            f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
            f.write(review)
        
        print(review)
        return review
    
    def agent_3_final_decision(self, problem: str, proposal: str, review: str) -> str:
        """Agent 3: Final Approver & Decision Agent"""
        print("\n" + "="*80)
        print("✅ AGENT 3: Final Approver & Decision Agent")
        print("="*80 + "\n")
        
        system_prompt = """You are a Staff+ Architect / Engineering Leader responsible for FINAL APPROVAL.

You must make the GO/NO-GO decision.

DECISION CRITERIA:
- Business value vs cost vs delivery speed
- Balance perfection with pragmatism
- Focus on execution clarity

DECISION OPTIONS:
1. **Approved as-is**: Ready to execute
2. **Approved with changes**: Good but needs modifications
3. **Rejected**: Needs fundamental rework

OUTPUT STRUCTURE:
## Final Decision: [Approved / Approved with Changes / Rejected]

## Key Feedback
[Critical observations from proposal and review]

## Mandatory Changes (if any)
1. **[Area]**: [Required change] - [Why critical]

## Deferred Items (can be done later)
1. [What can wait]

## Post-Implementation Watchlist
1. **[Metric/Area]**: [What to monitor] - [Action threshold]

## Execution Priority: [Critical / High / Medium / Low]

## Summary
[2-3 sentence final verdict]

Be decisive. Give clear, actionable feedback."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"PROBLEM:\n{problem}\n\nPROPOSED ARCHITECTURE:\n{proposal}\n\nREVIEW:\n{review}"}
            ],
            max_completion_tokens=3000
        )
        
        decision = response.choices[0].message.content
        
        # Save to file
        with open("./architecture_review/03_FINAL_DECISION.md", "w", encoding="utf-8") as f:
            f.write(f"# Final Decision\n")
            f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
            f.write(decision)
        
        print(decision)
        return decision
    
    def create_summary_report(self, problem: str, proposal: str, review: str, decision: str):
        """Create a comprehensive summary report"""
        report = f"""# Azure Architecture Review - Summary Report
**Generated**: {datetime.now().isoformat()}

---

## Problem Statement
{problem}

---

{proposal}

---

{review}

---

{decision}

---

## Next Steps
1. Review the final decision and mandatory changes
2. Address any skill gaps or hidden costs identified
3. Create detailed implementation plan with timelines
4. Set up post-implementation monitoring as recommended
"""
        
        with open("./architecture_review/00_SUMMARY_REPORT.md", "w", encoding="utf-8") as f:
            f.write(report)
    
    def run_full_cycle(self, problem: str):
        """Run all three agents in sequence"""
        print("\n🚀 Starting Three-Agent Architecture Review")
        print(f"Model: {self.deployment}\n")
        
        # Agent 1: Propose architecture
        proposal = self.agent_1_architecture_proposal(problem)
        
        # Agent 2: Review and assess
        review = self.agent_2_review(problem, proposal)
        
        # Agent 3: Final decision
        decision = self.agent_3_final_decision(problem, proposal, review)
        
        # Create summary
        self.create_summary_report(problem, proposal, review, decision)
        
        return {
            "proposal": proposal,
            "review": review,
            "decision": decision
        }


def main():
    """Run the system with your existing cost monitoring project"""
    
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
    
    system = SimpleArchitectureAgents()
    results = system.run_full_cycle(problem)
    
    print("\n" + "="*80)
    print("✅ ARCHITECTURE REVIEW COMPLETE")
    print("="*80)
    print("\n📄 Reports saved to:")
    print("   - ./architecture_review/00_SUMMARY_REPORT.md")
    print("   - ./architecture_review/01_ARCHITECTURE_PROPOSAL.md")
    print("   - ./architecture_review/02_REVIEW_ASSESSMENT.md")
    print("   - ./architecture_review/03_FINAL_DECISION.md")
    print("\n")


if __name__ == "__main__":
    main()
