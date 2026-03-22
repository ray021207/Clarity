"""Confidence calibration agent via response consistency sampling."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field

from clarity.agents.langchain_runtime import (
    build_prompt_messages,
    build_structured_model,
    build_text_model,
    extract_message_text,
)
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
    """Strict schema for confidence issues."""

    issue_id: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=80)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    message: str = Field(..., min_length=1, max_length=500)
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_fixes: list[str] = Field(default_factory=list)


class ConfidenceAuditPayload(BaseModel):
    """Strict schema returned by semantic consistency judge."""

    consistency_score: float = Field(..., ge=0, le=100)
    summary: str = Field(..., min_length=1, max_length=400)
    findings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    stable_points: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    issues: list[StructuredIssue] = Field(default_factory=list)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _get_temp_variations(base_temp: float, samples: int) -> list[float]:
    if samples <= 1:
        return [_clamp(base_temp, 0.0, 1.5)]
    deltas = [0.0, -0.2, 0.2, -0.35, 0.35, -0.5, 0.5]
    values: list[float] = []
    for delta in deltas:
        if len(values) >= samples:
            break
        values.append(_clamp(base_temp + delta, 0.0, 1.5))
    while len(values) < samples:
        values.append(_clamp(base_temp, 0.0, 1.5))
    return values


def _resolve_anthropic_key(context: dict[str, Any]) -> str:
    return str((context.get("anthropic_api_key") or settings.anthropic_api_key or "")).strip()


async def _sample_once(
    model_name: str,
    anthropic_key: str,
    messages: list[dict[str, Any]],
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    llm = build_text_model(
        model=model_name,
        anthropic_api_key=anthropic_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    payload = list(messages)
    if system_prompt:
        payload = [{"role": "system", "content": system_prompt}] + payload
    response = await llm.ainvoke(payload)
    return extract_message_text(response.content)


def _build_semantic_consistency_prompt(outputs: list[str], context: dict[str, Any]) -> str:
    capped_outputs = [
        {"index": idx, "text": text[:2500]}
        for idx, text in enumerate(outputs)
    ]
    payload = {
        "task": "semantic_consistency_audit",
        "system_prompt": context.get("system_prompt"),
        "temperature_used": context.get("temperature"),
        "samples": capped_outputs,
    }
    return (
        "Assess semantic consistency across response samples for the same prompt.\n"
        "Return STRICT JSON only (no markdown) with keys:\n"
        "consistency_score (0-100), summary, findings, suggestions, stable_points, contradictions, issues.\n"
        "Issue schema: issue_id, category, severity(low|medium|high|critical), message, evidence, suggested_fixes.\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


async def run_confidence_check(context: dict[str, Any]) -> AgentVerdict:
    """Estimate confidence by checking response stability across repeated generations."""
    base_output = (context.get("response_content") or "").strip()
    base_temp = float(context.get("temperature", 0.7) or 0.7)
    model = context.get("model") or "claude-sonnet-4-20250514"
    messages = context.get("messages") or []
    system_prompt = context.get("system_prompt")
    max_tokens = int(context.get("max_tokens") or 1024)
    sample_count = max(1, int(settings.clarity_confidence_samples or 3))
    temp_variations = _get_temp_variations(base_temp, sample_count)

    outputs: list[str] = [base_output] if base_output else []
    sample_meta: list[dict[str, Any]] = []

    anthropic_key = _resolve_anthropic_key(context)
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for confidence sampling.")
    if not messages:
        raise RuntimeError("Confidence agent requires original messages in verification context.")

    tasks = [
        _sample_once(
            model_name=model,
            anthropic_key=anthropic_key,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temp,
            max_tokens=max_tokens,
        )
        for temp in temp_variations
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    for idx, result in enumerate(results):
        sample_text = result.strip()
        outputs.append(sample_text)
        sample_meta.append(
            {
                "index": idx,
                "temperature": temp_variations[idx],
                "status": "ok",
                "output_length": len(sample_text),
            }
        )

    if not outputs:
        outputs = [""]

    successful_samples = sum(1 for s in sample_meta if s.get("status") == "ok")
    if successful_samples == 0:
        raise RuntimeError("Confidence agent could not produce any resampled outputs.")

    structured_llm = build_structured_model(
        model=model,
        anthropic_api_key=anthropic_key,
        schema=ConfidenceAuditPayload,
        temperature=0.0,
        max_tokens=1000,
    )
    parsed = await structured_llm.ainvoke(
        build_prompt_messages(
            (
                "You are a strict confidence calibration auditor. "
                "Evaluate semantic agreement and contradiction across sampled outputs."
            ),
            _build_semantic_consistency_prompt(outputs, context),
        )
    )
    payload = (
        parsed
        if isinstance(parsed, ConfidenceAuditPayload)
        else ConfidenceAuditPayload.model_validate(parsed)
    )
    consistency_score = round(float(payload.consistency_score), 2)
    issues = [issue.model_dump(mode="json") for issue in payload.issues]
    findings = [str(f) for f in payload.findings]
    suggestions = [str(s) for s in payload.suggestions]

    if not findings:
        findings = [payload.summary]
    if not suggestions:
        suggestions = ["Use stricter prompts and deterministic decoding for high-stakes tasks."]

    return AgentVerdict(
        agent_name="confidence_calibrator",
        score=round(consistency_score, 2),
        risk_level=_risk_from_score(consistency_score),
        summary=payload.summary,
        findings=findings,
        suggestions=suggestions,
        details={
            "issues": issues,
            "samples": outputs,
            "sample_meta": sample_meta,
            "stable_points": [str(s) for s in payload.stable_points],
            "contradictions": [str(c) for c in payload.contradictions],
            "temperatures": temp_variations,
            "base_temperature": base_temp,
            "sample_count": sample_count,
        },
    )
