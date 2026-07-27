"""LangGraph model factory backed by the shared LLM configuration."""

from dataclasses import dataclass
from typing import Any

from src.common.config import AgentRuntimeConfig
from src.integrations.llm.client import LLMSettings, create_langchain_chat_model


@dataclass(frozen=True)
class ConfiguredAgentModelFactory:
    settings: LLMSettings
    agent_config: AgentRuntimeConfig

    def create(self, *, workflow_kind: str) -> Any:
        override = (
            self.agent_config.agent_background_model
            if workflow_kind == "background_review"
            else self.agent_config.agent_chat_model
        )
        return create_langchain_chat_model(self.settings, model_override=override)