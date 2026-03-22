"""Reasoning consistency agent."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from clarity.agents.langchain_runtime import build_prompt_messages, build_structured_model
from clarity.config import settings
from clarity.models import AgentVerdict, RiskLevel


def _risk_from_score(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.LOW
    if score >= 60:
        return RiskLevel.MEDIUM
    if score >= 40:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


class StructuredIssue(BaseModel):
    """Strict schema for agent issues."""

    issue_id: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=80)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    message: str = Field(..., min_length=1, max_length=500)
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_fixes: list[str] = Field(default_factory=list)


class ReasoningAuditPayload(BaseModel):
    """Strict schema returned by reasoning auditor LLM."""

    score: float = Field(..., ge=0, le=100)
    summary: str = Field(..., min_length=1, max_length=400)
    issues: list[StructuredIssue] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


def _resolve_anthropic_key(context: dict[str, Any]) -> str:
    return str((context.get("anthropic_api_key") or settings.anthropic_api_key or "")).strip()


async def run_reasoning_check(context: dict[str, Any]) -> AgentVerdict:
    """Analyze logical consistency and reasoning quality."""
    anthropic_key = _resolve_anthropic_key(context)
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for reasoning analysis.")

    analyzer_model = (
        context.get("verifier_model")
        or settings.clarity_verifier_model
        or "claude-sonnet-4-6"
    )
    prompt = {
        "conversation_messages": context.get("messages", []),
        "system_prompt": context.get("system_prompt"),
        "model_output": context.get("response_content", ""),
    }

    system_prompt = (
        "You are a strict reasoning auditor.\n"
        "Assess logical consistency and reasoning quality.\n"
        "Return STRICT JSON only with keys: score, summary, issues, findings, suggestions.\n"
        "No markdown, no prose outside JSON.\n"
        "Issue schema: issue_id, category, severity(low|medium|high|critical), message, evidence, suggested_fixes."
    )

    user_prompt = (
        "Audit this model output for reasoning quality.\n"
        f"{json.dumps(prompt, ensure_ascii=True)}"
    )

    structured_llm = build_structured_model(
        model=analyzer_model,
        anthropic_api_key=anthropic_key,
        schema=ReasoningAuditPayload,
        temperature=0.1,
        max_tokens=900,
    )
    parsed = await structured_llm.ainvoke(build_prompt_messages(system_prompt, user_prompt))
    payload = (
        parsed
        if isinstance(parsed, ReasoningAuditPayload)
        else ReasoningAuditPayload.model_validate(parsed)
    )

    score = float(payload.score)
    score = max(0.0, min(100.0, round(score, 2)))
    issues = [issue.model_dump(mode="json") for issue in payload.issues]
    findings = [str(f) for f in payload.findings]
    suggestions = [str(s) for s in payload.suggestions]
    summary = payload.summary

    if not summary:
        summary = (
            "Reasoning is logically consistent."
            if score >= 80
            else "Reasoning quality is mixed and needs caution."
            if score >= 60
            else "Reasoning has significant reliability issues."
        )
    if not findings:
        findings = [summary]

    return AgentVerdict(
        agent_name="reasoning_validator",
        score=score,
        risk_level=_risk_from_score(score),
        summary=summary,
        findings=findings,
        suggestions=suggestions,
        details={"issues": issues, "analysis_mode": "llm"},
    )
