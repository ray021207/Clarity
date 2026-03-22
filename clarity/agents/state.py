"""LangGraph shared state for verification pipeline (Person B will implement)."""

from typing import TypedDict, Any, Optional
from clarity.models import AgentVerdict


class VerificationState(TypedDict, total=False):
    """Shared state flowing through LangGraph StateGraph."""

    # Input
    exchange_id: str
    context: dict[str, Any]  # Output of extract_verification_context()

    # Agent verdicts
    hallucination_verdict: Optional[AgentVerdict]
    reasoning_verdict: Optional[AgentVerdict]
    confidence_verdict: Optional[AgentVerdict]
    context_quality_verdict: Optional[AgentVerdict]

    # Aggregate output
    overall_score: Optional[float]
    warnings: list[str]
