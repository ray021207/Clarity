"""Data models for trust reports and agent verdicts."""

from datetime import datetime
from typing import Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk level categories."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentVerdict(BaseModel):
    """An individual agent's verification verdict."""

    agent_name: str = Field(..., description="Name of the agent (e.g., 'hallucination_detector')")
    score: float = Field(..., ge=0, le=100, description="Score 0-100")
    risk_level: RiskLevel = Field(..., description="Risk level based on score")
    summary: str = Field(..., description="One-sentence summary of findings")
    findings: list[str] = Field(default_factory=list, description="Detailed list of findings/issues")
    suggestions: list[str] = Field(default_factory=list, description="Actionable suggestions")
    details: dict[str, Any] = Field(default_factory=dict, description="Agent-specific detailed data")


class TrustReport(BaseModel):
    """Complete trust report with aggregated verdicts."""

    report_id: str = Field(..., description="Unique report ID")
    exchange_id: str = Field(..., description="Reference to the captured exchange")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When report was generated")

    # Overall score and risk
    overall_score: float = Field(..., ge=0, le=100, description="Weighted aggregate score 0-100")
    overall_risk: RiskLevel = Field(..., description="Overall risk level")

    # Individual agent verdicts
    hallucination: AgentVerdict = Field(..., description="Hallucination detector verdict")
    reasoning: AgentVerdict = Field(..., description="Reasoning validator verdict")
    confidence: AgentVerdict = Field(..., description="Confidence calibrator verdict")
    context_quality: AgentVerdict = Field(..., description="Context analyzer verdict")
    trajectory: Optional[AgentVerdict] = Field(
        default=None,
        description="Trajectory/tool execution grader verdict",
    )

    # Metadata
    warnings: list[str] = Field(default_factory=list, description="Top-level warnings")
    model_used: str = Field(..., description="Model that generated the output")
    temperature: float = Field(..., description="Temperature used")
    tokens_used: int = Field(default=0, description="Total tokens used (input + output)")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return self.model_dump(mode="json", by_alias=True)

    def get_summary(self) -> dict[str, Any]:
        """Get compact summary for Ada explainer."""
        return {
            "overall_score": self.overall_score,
            "overall_risk": self.overall_risk.value,
            "hallucination_score": self.hallucination.score,
            "reasoning_score": self.reasoning.score,
            "confidence_score": self.confidence.score,
            "context_quality_score": self.context_quality.score,
            "trajectory_score": self.trajectory.score if self.trajectory else None,
            "warnings": self.warnings,
            "model_used": self.model_used,
        }
