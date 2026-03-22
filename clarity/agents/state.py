"""LangGraph shared state for the verification pipeline."""

from typing import Any, Optional, TypedDict

from clarity.models import AgentVerdict


class VerificationState(TypedDict, total=False):
    """Shared state flowing through the LangGraph StateGraph."""

    # Input
    exchange_id: str
    context: dict[str, Any]

    # Parallel node outputs
    hallucination_verdict: Optional[AgentVerdict]
    reasoning_verdict: Optional[AgentVerdict]
    confidence_verdict: Optional[AgentVerdict]
    context_quality_verdict: Optional[AgentVerdict]
    trajectory_verdict: Optional[AgentVerdict]

    # Aggregate outputs
    overall_score: Optional[float]
    warnings: list[str]
