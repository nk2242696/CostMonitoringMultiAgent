"""Tests for reference architecture and LLM-enhanced recommendations."""

import json
from types import SimpleNamespace

from src.models import AIRecommendation
from src.recommendations.architecture_reviewer import (
    ArchitectureRecommender,
    resolve_architecture_key,
)


def test_resolves_cost_management_service_names():
    assert resolve_architecture_key("Virtual Machines") == "Microsoft.Compute"
    assert resolve_architecture_key("Storage") == "Microsoft.Storage"
    assert resolve_architecture_key("SQL Database") == "Microsoft.Sql"
    assert resolve_architecture_key("Azure Databricks") == "Microsoft.Databricks"
    assert resolve_architecture_key("Azure App Service") == "Microsoft.Web"


def test_preserves_provider_namespace_and_rejects_unknown_service():
    assert resolve_architecture_key("Microsoft.Network") == "Microsoft.Network"
    assert resolve_architecture_key("Unknown Service") is None


def test_llm_enrichment_updates_recommendation_without_changing_savings():
    content = json.dumps(
        {
            "recommendations": [
                {
                    "index": 0,
                    "title": "Validate VM commitment options",
                    "recommendation_text": "Review eligible VM usage before purchasing commitments.",
                    "action_items": ["Open Azure Advisor", "Validate 30-day utilization"],
                    "implementation_effort": "1-2 hours",
                }
            ]
        }
    )
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: completion)
        )
    )
    rec = AIRecommendation(
        recommendation_id="test-rec",
        tier=1,
        source="reference_architecture",
        category="compute",
        title="Original",
        recommendation_text="Original guidance",
        current_cost=100,
        potential_savings=25,
        priority="medium",
        rec_metadata={"reference_check": "reserved_instances"},
    )
    recommender = ArchitectureRecommender.__new__(ArchitectureRecommender)
    recommender.openai_client = client
    recommender.deployment = "test-model"

    recommender._enrich_with_llm([rec])

    assert rec.source == "llm_enhanced_reference"
    assert rec.title == "Validate VM commitment options"
    assert rec.potential_savings == 25
    assert rec.rec_metadata["llm_model"] == "test-model"