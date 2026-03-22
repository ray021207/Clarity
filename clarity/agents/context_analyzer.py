"""LLM-based context quality analyzer."""

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


def _resolve_anthropic_key(context: dict[str, Any]) -> str:
    return str((context.get("anthropic_api_key") or settings.anthropic_api_key or "")).strip()


class StructuredIssue(BaseModel):
    """Strict schema for context-quality issues."""

    issue_id: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=80)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    message: str = Field(..., min_length=1, max_length=500)
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_fixes: list[str] = Field(default_factory=list)


class ContextAuditPayload(BaseModel):
    """Strict schema returned by context-quality auditor LLM."""

    score: float = Field(..., ge=0, le=100)
    summary: str = Field(..., min_length=1, max_length=400)
    findings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    issues: list[StructuredIssue] = Field(default_factory=list)


async def run_context_quality_check(context: dict[str, Any]) -> AgentVerdict:
    """Analyze prompt/context quality using an LLM auditor."""
    anthropic_key = _resolve_anthropic_key(context)
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for context quality analysis.")

    analyzer_model = context.get("model") or "claude-sonnet-4-20250514"
    context_payload = {
        "has_system_prompt": context.get("has_system_prompt"),
        "system_prompt_length": context.get("system_prompt_length"),
        "temperature": context.get("temperature"),
        "temp_risk": context.get("temp_risk"),
        "message_count": context.get("message_count"),
        "context_saturation_percent": context.get("context_saturation_percent"),
        "tools_available_but_unused": context.get("tools_available_but_unused"),
        "num_tools": context.get("num_tools"),
        "stop_reason": context.get("stop_reason"),
        "is_truncated": context.get("is_truncated"),
        "output_words": context.get("output_words"),
        "output_lines": context.get("output_lines"),
        "response_excerpt": str(context.get("response_content", ""))[:800],
    }

    system_prompt = (
        "You are a strict context-quality auditor for LLM interactions.\n"
        "Return STRICT JSON only with keys: score, summary, findings, suggestions, issues.\n"
        "No markdown, no prose outside JSON.\n"
        "Each issue must include: issue_id, category, severity(low|medium|high|critical), "
        "message, evidence, suggested_fixes."
    )
    user_prompt = (
        "Audit this conversation context and generation setup for reliability risks:\n"
        f"{json.dumps(context_payload, ensure_ascii=True)}"
    )

    structured_llm = build_structured_model(
        model=analyzer_model,
        anthropic_api_key=anthropic_key,
        schema=ContextAuditPayload,
        temperature=0.1,
        max_tokens=900,
    )
    parsed = await structured_llm.ainvoke(build_prompt_messages(system_prompt, user_prompt))
    payload = (
        parsed
        if isinstance(parsed, ContextAuditPayload)
        else ContextAuditPayload.model_validate(parsed)
    )

    score = float(payload.score)
    score = max(0.0, min(100.0, round(score, 2)))
    summary = payload.summary
    findings = [str(f) for f in payload.findings]
    suggestions = [str(s) for s in payload.suggestions]
    issues = [issue.model_dump(mode="json") for issue in payload.issues]

    if not summary:
        summary = (
            "Context setup appears reliable."
            if score >= 80
            else "Context setup has moderate reliability risks."
            if score >= 60
            else "Context setup has significant reliability issues."
        )
    if not findings:
        findings = [summary]

    return AgentVerdict(
        agent_name="context_analyzer",
        score=score,
        risk_level=_risk_from_score(score),
        summary=summary,
        findings=findings,
        suggestions=suggestions,
        details={
            "issues": issues,
            "analysis_mode": "llm",
            "metrics": context_payload,
        },
    )
