"""Tests for Azure cost collector authentication setup."""

import time

import pytest
from azure.core.credentials import AccessToken

from src.collection import cost_collector
from src.collection.cost_collector import CostCollector


def test_blank_credentials_use_non_environment_default_credential(monkeypatch):
    captured = {}

    def fake_default_credential(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(cost_collector, "DefaultAzureCredential", fake_default_credential)
    monkeypatch.setenv("AZURE_TENANT_ID", "")
    monkeypatch.setenv("AZURE_CLIENT_ID", "")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "")
    monkeypatch.delenv("AZURE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("AZURE_ACCESS_TOKEN_EXPIRES_ON", raising=False)

    CostCollector()

    assert captured == {"exclude_environment_credential": True}


def test_partial_service_principal_is_rejected(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "")
    monkeypatch.delenv("AZURE_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="must all be set"):
        CostCollector()


def test_ephemeral_access_token_takes_precedence(monkeypatch):
    expires_on = int(time.time()) + 3600
    monkeypatch.setenv("AZURE_ACCESS_TOKEN", "temporary-token")
    monkeypatch.setenv("AZURE_ACCESS_TOKEN_EXPIRES_ON", str(expires_on))

    collector = CostCollector()
    token = collector.credential.get_token("https://management.azure.com/.default")

    assert token == AccessToken("temporary-token", expires_on)


def test_ephemeral_access_token_requires_expiration(monkeypatch):
    monkeypatch.setenv("AZURE_ACCESS_TOKEN", "temporary-token")
    monkeypatch.delenv("AZURE_ACCESS_TOKEN_EXPIRES_ON", raising=False)

    with pytest.raises(ValueError, match="AZURE_ACCESS_TOKEN_EXPIRES_ON is required"):
        CostCollector()