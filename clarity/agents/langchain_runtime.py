"""LangChain runtime helpers for agent nodes."""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage


def build_prompt_messages(system_prompt: str, user_prompt: str) -> list[Any]:
    """Build a standard system+user message list for LangChain chat models."""
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]


def build_structured_model(
    *,
    model: str,
    anthropic_api_key: str,
    schema: type,
    temperature: float = 0.0,
    max_tokens: int = 900,
):
    """Create a ChatAnthropic model with provider-structured output enabled."""
    llm = ChatAnthropic(
        model=model,
        anthropic_api_key=anthropic_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return llm.with_structured_output(schema, method="json_schema")


def build_text_model(
    *,
    model: str,
    anthropic_api_key: str,
    temperature: float,
    max_tokens: int,
) -> ChatAnthropic:
    """Create a plain-text ChatAnthropic model."""
    return ChatAnthropic(
        model=model,
        anthropic_api_key=anthropic_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def extract_message_text(content: Any) -> str:
    """Normalize LangChain message content into plain text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content or "").strip()
