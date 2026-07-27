"""OpenAI-compatible language model client factory.

Application code depends on the small ``ChatClient`` protocol rather than a
provider SDK.  Both Azure OpenAI and generic OpenAI-compatible endpoints use
the official OpenAI client, but all provider construction remains here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from openai import AsyncAzureOpenAI, AsyncOpenAI, AzureOpenAI, OpenAI


class LLMConfigurationError(ValueError):
    """Raised when an enabled language model provider is misconfigured."""


class ChatClient(Protocol):
    """Client surface consumed by the agent system.

    The OpenAI-compatible ``chat.completions.create`` shape is intentionally
    retained while provider construction and configuration are centralized.
    """

    chat: Any


@dataclass(frozen=True)
class LLMSettings:
    """Validated language model settings sourced from environment variables."""

    provider: str = "disabled"
    api_key: str = ""
    model: str = "gpt-4o"
    base_url: str = ""
    api_version: str = "2024-12-01-preview"
    timeout_seconds: float = 60.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "LLMSettings":
        provider = os.getenv("LLM_PROVIDER", "").strip().lower()

        # Preserve a smooth upgrade for existing Azure OpenAI deployments.
        if not provider and os.getenv("AZURE_OPENAI_ENDPOINT"):
            provider = "azure_openai"
        if not provider:
            provider = "disabled"

        if provider == "azure_openai":
            return cls(
                provider=provider,
                api_key=os.getenv("LLM_API_KEY") or os.getenv("AZURE_OPENAI_KEY", ""),
                model=os.getenv("LLM_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
                base_url=os.getenv("LLM_BASE_URL") or os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                api_version=os.getenv("LLM_API_VERSION") or os.getenv(
                    "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
                ),
                timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
                max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
            )

        return cls(
            provider=provider,
            api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o"),
            base_url=os.getenv("LLM_BASE_URL", ""),
            api_version=os.getenv("LLM_API_VERSION", "2024-12-01-preview"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        )

    def validate(self) -> None:
        """Validate only settings required by the selected provider."""
        if self.provider == "disabled":
            return
        if self.provider not in {"azure_openai", "openai_compatible"}:
            raise LLMConfigurationError(
                "LLM_PROVIDER must be disabled, azure_openai, or openai_compatible"
            )
        if not self.api_key:
            raise LLMConfigurationError("LLM_API_KEY is required when AI is enabled")
        if not self.model:
            raise LLMConfigurationError("LLM_MODEL is required when AI is enabled")
        if not self.base_url:
            raise LLMConfigurationError("LLM_BASE_URL is required when AI is enabled")


def create_chat_client(settings: LLMSettings | None = None) -> tuple[ChatClient | None, str]:
    """Create the configured async client and return it with its model name."""
    resolved = settings or LLMSettings.from_env()
    resolved.validate()

    if resolved.provider == "disabled":
        return None, resolved.model

    common = {
        "api_key": resolved.api_key,
        "timeout": resolved.timeout_seconds,
        "max_retries": resolved.max_retries,
    }
    if resolved.provider == "azure_openai":
        client = AsyncAzureOpenAI(
            **common,
            azure_endpoint=resolved.base_url,
            api_version=resolved.api_version,
        )
    else:
        client = AsyncOpenAI(**common, base_url=resolved.base_url)

    return client, resolved.model


def create_sync_chat_client(
    settings: LLMSettings | None = None,
) -> tuple[ChatClient | None, str]:
    """Create a synchronous client for non-async workers and CLI commands."""
    resolved = settings or LLMSettings.from_env()
    resolved.validate()

    if resolved.provider == "disabled":
        return None, resolved.model

    common = {
        "api_key": resolved.api_key,
        "timeout": resolved.timeout_seconds,
        "max_retries": resolved.max_retries,
    }
    if resolved.provider == "azure_openai":
        client = AzureOpenAI(
            **common,
            azure_endpoint=resolved.base_url,
            api_version=resolved.api_version,
        )
    else:
        client = OpenAI(**common, base_url=resolved.base_url)

    return client, resolved.model


def create_langchain_chat_model(
    settings: LLMSettings | None = None,
    *,
    model_override: str | None = None,
) -> Any:
    """Create the LangChain chat model used by the LangGraph runtime.

    Provider credentials remain sourced exclusively through ``LLMSettings``.
    The import is local so the deterministic runtime can still start when the
    optional agent feature is disabled during rollout.
    """
    from langchain_openai import AzureChatOpenAI, ChatOpenAI

    resolved = settings or LLMSettings.from_env()
    resolved.validate()
    if resolved.provider == "disabled":
        raise LLMConfigurationError("agent_runtime_unavailable: LLM provider is disabled")

    model = model_override or resolved.model
    common = {
        "api_key": resolved.api_key,
        "timeout": resolved.timeout_seconds,
        "max_retries": resolved.max_retries,
    }
    if resolved.provider == "azure_openai":
        return AzureChatOpenAI(
            **common,
            azure_deployment=model,
            azure_endpoint=resolved.base_url,
            api_version=resolved.api_version,
        )
    return ChatOpenAI(
        **common,
        model=model,
        base_url=resolved.base_url,
    )