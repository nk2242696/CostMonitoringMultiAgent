"""Tests for provider-neutral language model configuration."""

import pytest

from src.common.config import Config, DatabaseConfig
from src.integrations.llm.client import (
    LLMConfigurationError,
    LLMSettings,
    create_chat_client,
    create_sync_chat_client,
)


def test_disabled_provider_needs_no_credentials():
    client, model = create_chat_client(LLMSettings(provider="disabled", model="local-rules"))

    assert client is None
    assert model == "local-rules"


def test_disabled_sync_provider_needs_no_credentials():
    client, model = create_sync_chat_client(
        LLMSettings(provider="disabled", model="local-rules")
    )

    assert client is None
    assert model == "local-rules"


def test_default_api_version_supports_current_reasoning_models(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("LLM_API_KEY", "not-a-real-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.openai.azure.com")
    monkeypatch.delenv("LLM_API_VERSION", raising=False)

    assert LLMSettings.from_env().api_version == "2024-12-01-preview"


@pytest.mark.parametrize("provider", ["azure_openai", "openai_compatible"])
def test_enabled_provider_requires_credentials(provider):
    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        create_chat_client(LLMSettings(provider=provider, base_url="https://example.invalid/v1"))


def test_rejects_unknown_provider():
    with pytest.raises(LLMConfigurationError, match="LLM_PROVIDER"):
        create_chat_client(LLMSettings(provider="unknown", api_key="not-a-real-key"))


def test_azure_legacy_environment_is_mapped(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "cost-model")

    settings = LLMSettings.from_env()

    assert settings.provider == "azure_openai"
    assert settings.base_url == "https://example.openai.azure.com"
    assert settings.model == "cost-model"


def test_workspace_context_is_loaded(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace.yaml"
    workspace.write_text(
        '{"organization":{"name":"Contoso","currency":"EUR"},'
        '"environments":[{"name":"production","risk_tolerance":"low"}],'
        '"minimum_monthly_savings":25}',
        encoding="utf-8",
    )
    monkeypatch.setenv("WORKSPACE_CONFIG_PATH", str(workspace))

    config = Config("docker")

    assert config.workspace.organization.name == "Contoso"
    assert config.workspace.organization.currency == "EUR"
    assert config.workspace.environments[0].risk_tolerance == "low"
    assert config.workspace.minimum_monthly_savings == 25


def test_database_url_encodes_reserved_credentials():
    config = DatabaseConfig(
        host="postgres",
        database="azure_cost",
        username="cost_monitor",
        password="secret@word:/",
    )

    assert config.url == (
        "postgresql://cost_monitor:secret%40word%3A%2F@postgres:5432/azure_cost"
    )