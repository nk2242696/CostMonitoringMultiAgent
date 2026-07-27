"""
Claude (Anthropic) adapter that exposes the same async interface as
``AsyncAzureOpenAI`` so the multi-agent system can use Claude without
changing any agent code.

Usage:
    client = ClaudeAdapter(api_key="sk-ant-...")
    resp = await client.chat.completions.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
        temperature=0.3,
    )
    text = resp.choices[0].message.content
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)


# ── Thin response wrappers that look like OpenAI's objects ──


@dataclass
class _Message:
    content: str
    role: str = "assistant"


@dataclass
class _Choice:
    message: _Message
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class _ChatCompletion:
    choices: List[_Choice] = field(default_factory=list)
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)


# ── Completions namespace ──


class _Completions:
    """Mimics ``client.chat.completions``."""

    def __init__(self, anthropic_client: anthropic.AsyncAnthropic, default_model: str):
        self._client = anthropic_client
        self._default_model = default_model

    async def create(
        self,
        *,
        model: Optional[str] = None,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 4096,
        **kwargs,
    ) -> _ChatCompletion:
        """
        Translate an OpenAI-style ``chat.completions.create`` call into
        an Anthropic ``messages.create`` call and wrap the result.
        """
        model = model or self._default_model

        # Split the OpenAI messages list into a system prompt + user/assistant turns
        system_prompt = ""
        claude_messages: List[Dict[str, str]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            else:
                # Claude only accepts "user" and "assistant" roles
                claude_role = "user" if role != "assistant" else "assistant"
                claude_messages.append({"role": claude_role, "content": content})

        # Claude requires alternating user/assistant turns and must start with user
        if not claude_messages:
            claude_messages = [{"role": "user", "content": "Hello"}]

        # Merge consecutive same-role messages (Claude doesn't allow them)
        merged: List[Dict[str, str]] = []
        for m in claude_messages:
            if merged and merged[-1]["role"] == m["role"]:
                merged[-1]["content"] += "\n\n" + m["content"]
            else:
                merged.append(dict(m))
        claude_messages = merged

        # Ensure it starts with "user"
        if claude_messages[0]["role"] != "user":
            claude_messages.insert(0, {"role": "user", "content": "Please respond to the following."})

        try:
            resp = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=claude_messages,
                temperature=temperature,
            )

            # Extract text from Claude's response
            text = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    text += block.text

            return _ChatCompletion(
                choices=[_Choice(message=_Message(content=text))],
                model=resp.model,
                usage={
                    "prompt_tokens": resp.usage.input_tokens,
                    "completion_tokens": resp.usage.output_tokens,
                    "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
                },
            )
        except Exception as e:
            logger.error("Claude API error: %s", e)
            raise


# ── Chat namespace ──


class _Chat:
    """Mimics ``client.chat``."""

    def __init__(self, completions: _Completions):
        self.completions = completions


# ── Main adapter ──


class ClaudeAdapter:
    """
    Drop-in async replacement for ``AsyncAzureOpenAI``.

    Exposes ``client.chat.completions.create(...)`` using the
    Anthropic Messages API under the hood.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
    ):
        self._anthropic = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.chat = _Chat(_Completions(self._anthropic, default_model=model))
        logger.info("ClaudeAdapter initialised (model=%s)", model)
