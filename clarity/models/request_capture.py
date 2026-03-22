"""Data models for capturing LLM requests and responses."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class RequestMetadata(BaseModel):
    """Metadata about the incoming LLM request."""

    model: str = Field(..., description="Model name (e.g., 'claude-sonnet-4-20250514')")
    system_prompt: Optional[str] = Field(default=None, description="System prompt if provided")
    messages: list[dict[str, Any]] = Field(..., description="User messages")
    temperature: float = Field(default=1.0, description="Temperature parameter")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens limit")
    tools_provided: list[str] = Field(default_factory=list, description="Tool names available to the model")
    tool_definitions: Optional[list[dict[str, Any]]] = Field(default=None, description="Full tool schemas")
    total_context_chars: int = Field(default=0, description="Total character count of context")
    message_count: int = Field(default=0, description="Number of messages in conversation")


class ResponseMetadata(BaseModel):
    """Metadata about the LLM response."""

    content: str = Field(..., description="LLM text response")
    stop_reason: str = Field(..., description="Why generation stopped (e.g., 'end_turn', 'max_tokens')")
    input_tokens: int = Field(default=0, description="Tokens in the request")
    output_tokens: int = Field(default=0, description="Tokens in the response")
    tool_calls: Optional[list[dict[str, Any]]] = Field(default=None, description="If model called tools")
    latency_ms: float = Field(default=0.0, description="Request latency in milliseconds")


class CapturedExchange(BaseModel):
    """A complete captured LLM request/response pair."""

    exchange_id: str = Field(..., description="Unique identifier for this exchange")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the exchange occurred")
    request: RequestMetadata = Field(..., description="The request metadata")
    response: ResponseMetadata = Field(..., description="The response metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return self.model_dump(mode="json")
