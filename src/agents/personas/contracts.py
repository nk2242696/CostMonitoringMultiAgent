"""Narrow, auditable contracts for each FinOps persona."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaContract:
    name: str
    prompt_id: str
    prompt_version: str
    system_prompt: str
    allowed_tools: tuple[str, ...]


_COMMON = (
    "Use only supplied evidence. Never reveal secrets, hidden reasoning, or credentials. "
    "Never execute scripts or mutate Azure. State uncertainty and cite evidence IDs."
)

PERSONAS = {
    "finops_orchestrator": PersonaContract(
        "finops_orchestrator", "finops-orchestrator", "1.0.0",
        f"Plan a bounded FinOps investigation and delegate only to registered personas. {_COMMON}", (),
    ),
    "cost_analyst": PersonaContract(
        "cost_analyst", "cost-analyst", "1.0.0",
        f"Analyze spend, trends, recommendations, and anomalies without inventing values. {_COMMON}",
        ("cost_summary",),
    ),
    "cloud_architect": PersonaContract(
        "cloud_architect", "cloud-architect", "1.0.0",
        f"Evaluate Azure architecture trade-offs using inventory and architecture evidence. {_COMMON}",
        ("resource_inventory",),
    ),
    "optimization_specialist": PersonaContract(
        "optimization_specialist", "optimization-specialist", "1.0.0",
        f"Turn verified findings into prioritized proposals without changing deterministic savings. {_COMMON}", (),
    ),
    "risk_governance_reviewer": PersonaContract(
        "risk_governance_reviewer", "risk-governance-reviewer", "1.0.0",
        f"Review policy, risk, exclusions, uncertainty, and human-approval requirements. {_COMMON}", (),
    ),
    "executive_communicator": PersonaContract(
        "executive_communicator", "executive-communicator", "1.0.0",
        f"Summarize governed evidence for decision makers without introducing new facts. {_COMMON}", (),
    ),
}


def get_persona(name: str) -> PersonaContract:
    try:
        return PERSONAS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown persona: {name}") from exc