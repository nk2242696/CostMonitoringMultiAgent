"""
Architecture Review Agent Service
Integrates the three-agent architecture review system with the cost monitoring platform
"""
import os
import logging
from typing import Dict, Optional
from datetime import datetime
from openai import AzureOpenAI
from pathlib import Path

logger = logging.getLogger(__name__)


class ArchitectureReviewService:
    """Service for running architecture reviews"""
    
    def __init__(self):
        # Use existing Azure OpenAI configuration
        self.azure_key = os.getenv("AZURE_OPENAI_KEY", "")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if not self.azure_key or not self.azure_endpoint:
            logger.warning("AZURE_OPENAI_KEY / AZURE_OPENAI_ENDPOINT not set — architecture reviews will fail")
        
        self.client = AzureOpenAI(
            api_key=self.azure_key,
            api_version="2025-01-01-preview",
            azure_endpoint=self.azure_endpoint,
            timeout=60.0
        )
        
        self.output_dir = Path("./architecture_review")
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"ArchitectureReviewService initialized with endpoint: {self.azure_endpoint}")
    
    def agent_1_architecture_proposal(self, problem: str) -> str:
        """Agent 1: Azure Architecture & Recommendations"""
        logger.info("Agent 1: Generating architecture proposal")
        
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
        
        return response.choices[0].message.content
    
    def agent_2_review(self, problem: str, proposal: str) -> str:
        """Agent 2: Reviewer (Effort, Complexity, Time)"""
        logger.info("Agent 2: Reviewing architecture proposal")
        
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
        
        return response.choices[0].message.content
    
    def agent_3_final_decision(self, problem: str, proposal: str, review: str) -> str:
        """Agent 3: Final Approver & Decision Agent"""
        logger.info("Agent 3: Making final decision")
        
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
        
        return response.choices[0].message.content
    
    def run_architecture_review(self, problem_statement: str, review_id: Optional[str] = None) -> Dict[str, str]:
        """Run full three-agent architecture review cycle"""
        if not review_id:
            review_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Starting architecture review: {review_id}")
        
        try:
            # Agent 1: Propose architecture
            proposal = self.agent_1_architecture_proposal(problem_statement)
            
            # Save proposal
            proposal_file = self.output_dir / f"{review_id}_01_PROPOSAL.md"
            with open(proposal_file, "w", encoding="utf-8") as f:
                f.write(f"# Architecture Proposal\n")
                f.write(f"**Review ID**: {review_id}\n")
                f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
                f.write(proposal)
            
            # Agent 2: Review and assess
            review = self.agent_2_review(problem_statement, proposal)
            
            # Save review
            review_file = self.output_dir / f"{review_id}_02_REVIEW.md"
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(f"# Review & Assessment\n")
                f.write(f"**Review ID**: {review_id}\n")
                f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
                f.write(review)
            
            # Agent 3: Final decision
            decision = self.agent_3_final_decision(problem_statement, proposal, review)
            
            # Save decision
            decision_file = self.output_dir / f"{review_id}_03_DECISION.md"
            with open(decision_file, "w", encoding="utf-8") as f:
                f.write(f"# Final Decision\n")
                f.write(f"**Review ID**: {review_id}\n")
                f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
                f.write(decision)
            
            # Create summary
            summary = self._create_summary(review_id, problem_statement, proposal, review, decision)
            summary_file = self.output_dir / f"{review_id}_00_SUMMARY.md"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary)
            
            logger.info(f"Architecture review completed: {review_id}")
            
            return {
                "review_id": review_id,
                "proposal": proposal,
                "review": review,
                "decision": decision,
                "summary": summary,
                "files": {
                    "summary": str(summary_file),
                    "proposal": str(proposal_file),
                    "review": str(review_file),
                    "decision": str(decision_file)
                }
            }
            
        except Exception as e:
            logger.error(f"Architecture review failed: {str(e)}", exc_info=True)
            raise
    
    def _create_summary(self, review_id: str, problem: str, proposal: str, review: str, decision: str) -> str:
        """Create executive summary"""
        return f"""# Architecture Review Summary
**Review ID**: {review_id}
**Generated**: {datetime.now().isoformat()}

---

## Problem Statement

{problem}

---

# 🏗️ Agent 1: Architecture Proposal

{proposal}

---

# 👨‍💻 Agent 2: Review & Assessment

{review}

---

# ✅ Agent 3: Final Decision

{decision}

---

## Files Generated
- Summary: {review_id}_00_SUMMARY.md
- Proposal: {review_id}_01_PROPOSAL.md
- Review: {review_id}_02_REVIEW.md
- Decision: {review_id}_03_DECISION.md
"""
