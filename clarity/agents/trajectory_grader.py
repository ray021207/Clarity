"""Trajectory grading layer for agent and tool execution quality."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from clarity.agents.langchain_runtime import build_prompt_messages, build_structured_model
from clarity.config import settings
from clarity.models import AgentVerdict, RiskLevel

_TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class StructuredIssue(BaseModel):
    """Strict schema for trajectory and tool issues."""

    issue_id: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=80)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    message: str = Field(..., min_length=1, max_length=500)
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_fixes: list[str] = Field(default_factory=list)


class TrajectoryAuditPayload(BaseModel):
    """Strict schema returned by trajectory grader LLM."""

    overall_score: float = Field(..., ge=0, le=100)
    tool_compliance_score: float = Field(..., ge=0, le=100)
    summary: str = Field(..., min_length=1, max_length=500)
    findings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    per_agent_scores: dict[str, float] = Field(default_factory=dict)
    per_tool_scores: dict[str, float] = Field(default_factory=dict)
    issues: list[StructuredIssue] = Field(default_factory=list)
    tool_format_issues: list[StructuredIssue] = Field(default_factory=list)


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


def _build_issue(
    issue_id: str,
    category: str,
    severity: str,
    message: str,
    evidence: dict[str, Any],
    suggested_fixes: list[str],
) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "category": category,
        "severity": severity,
        "message": message,
        "evidence": evidence,
        "suggested_fixes": suggested_fixes,
    }


def _collect_tool_format_issues(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic tool-format validator inspired by IFEval-FC style constraints."""
    issues: list[dict[str, Any]] = []
    tool_calls = context.get("tool_calls") or []
    tools_provided = set(context.get("tools_provided") or [])
    tool_definitions = context.get("tool_definitions") or []
    schema_by_tool: dict[str, dict[str, Any]] = {}
    for tool in tool_definitions:
        if isinstance(tool, dict):
            name = str(tool.get("name") or "")
            if name:
                schema_by_tool[name] = tool

    if tools_provided and not tool_calls:
        issues.append(
            _build_issue(
                issue_id="tool_unused_available",
                category="tool_selection",
                severity="medium",
                message="Tools were available but no tool call was emitted.",
                evidence={"tools_provided": sorted(tools_provided)},
                suggested_fixes=[
                    "Clarify tool-usage expectations in system prompt.",
                    "Provide examples that require tool invocation before final answer.",
                ],
            )
        )

    for idx, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            issues.append(
                _build_issue(
                    issue_id=f"tool_call_shape_{idx+1}",
                    category="tool_format",
                    severity="high",
                    message="Tool call entry is not an object.",
                    evidence={"call": call},
                    suggested_fixes=[
                        "Ensure tool calls are emitted as JSON objects with name/id/input.",
                    ],
                )
            )
            continue

        name = str(call.get("name") or "").strip()
        tool_input = call.get("input")
        tool_id = str(call.get("id") or "").strip()

        if not name:
            issues.append(
                _build_issue(
                    issue_id=f"tool_name_missing_{idx+1}",
                    category="tool_format",
                    severity="high",
                    message="Tool call is missing `name`.",
                    evidence={"call": call},
                    suggested_fixes=["Ensure every tool call contains a non-empty tool name."],
                )
            )
        elif not _TOOL_NAME_PATTERN.match(name):
            issues.append(
                _build_issue(
                    issue_id=f"tool_name_invalid_{idx+1}",
                    category="tool_format",
                    severity="high",
                    message="Tool name format is invalid.",
                    evidence={"name": name},
                    suggested_fixes=[
                        "Use tool names matching ^[a-zA-Z0-9_-]{1,64}$.",
                    ],
                )
            )

        if not tool_id:
            issues.append(
                _build_issue(
                    issue_id=f"tool_id_missing_{idx+1}",
                    category="tool_format",
                    severity="medium",
                    message="Tool call is missing `id`.",
                    evidence={"name": name},
                    suggested_fixes=[
                        "Emit stable call IDs for tool/result correlation.",
                    ],
                )
            )

        if name and tools_provided and name not in tools_provided:
            issues.append(
                _build_issue(
                    issue_id=f"tool_unknown_{idx+1}",
                    category="tool_selection",
                    severity="high",
                    message="Tool call references a tool not declared in request.",
                    evidence={"name": name, "tools_provided": sorted(tools_provided)},
                    suggested_fixes=[
                        "Constrain tool calls to declared tools only.",
                    ],
                )
            )

        if not isinstance(tool_input, dict):
            issues.append(
                _build_issue(
                    issue_id=f"tool_input_shape_{idx+1}",
                    category="tool_format",
                    severity="high",
                    message="Tool call `input` must be a JSON object.",
                    evidence={"name": name, "input_type": type(tool_input).__name__},
                    suggested_fixes=[
                        "Return function arguments as a structured JSON object.",
                    ],
                )
            )
            continue

        tool_schema = schema_by_tool.get(name, {})
        input_schema = tool_schema.get("input_schema", {}) if isinstance(tool_schema, dict) else {}
        required = input_schema.get("required", []) if isinstance(input_schema, dict) else []
        if isinstance(required, list):
            missing = [field for field in required if field not in tool_input]
            if missing:
                issues.append(
                    _build_issue(
                        issue_id=f"tool_required_args_{idx+1}",
                        category="tool_format",
                        severity="medium",
                        message="Tool call is missing required input fields.",
                        evidence={"name": name, "missing_fields": missing},
                        suggested_fixes=[
                            "Populate all required fields from tool input schema.",
                            "Use few-shot tool-call examples with required args.",
                        ],
                    )
                )

    return issues


def _build_audit_payload(
    context: dict[str, Any],
    agent_verdicts: dict[str, AgentVerdict],
    format_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    tool_calls = context.get("tool_calls") or []
    agent_payload = {}
    for name, verdict in agent_verdicts.items():
        issues = verdict.details.get("issues", [])
        agent_payload[name] = {
            "score": verdict.score,
            "risk_level": verdict.risk_level.value,
            "summary": verdict.summary[:300],
            "issues": issues if isinstance(issues, list) else [],
            "findings": [str(f)[:200] for f in verdict.findings[:8]],
        }

    return {
        "trajectory_context": {
            "model": context.get("model"),
            "stop_reason": context.get("stop_reason"),
            "is_truncated": context.get("is_truncated"),
            "message_count": context.get("message_count"),
            "tools_provided": context.get("tools_provided"),
            "tool_calls": tool_calls,
            "response_excerpt": str(context.get("response_content", ""))[:1200],
        },
        "agent_verdicts": agent_payload,
        "deterministic_tool_format_issues": format_issues,
    }


async def run_trajectory_grader(
    context: dict[str, Any],
    *,
    hallucination: AgentVerdict,
    reasoning: AgentVerdict,
    confidence: AgentVerdict,
    context_quality: AgentVerdict,
) -> AgentVerdict:
    """Grade execution trajectory across agents and tool calls."""
    anthropic_key = _resolve_anthropic_key(context)
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for trajectory grading.")

    model = context.get("model") or "claude-sonnet-4-20250514"
    format_issues = _collect_tool_format_issues(context)
    payload = _build_audit_payload(
        context=context,
        agent_verdicts={
            "hallucination_detector": hallucination,
            "reasoning_validator": reasoning,
            "confidence_calibrator": confidence,
            "context_analyzer": context_quality,
        },
        format_issues=format_issues,
    )

    system_prompt = (
        "You are a strict trajectory auditor for a multi-agent verification pipeline.\n"
        "Evaluate process quality, tool-call quality, and consistency across agent verdicts.\n"
        "Return STRICT JSON only with keys:\n"
        "overall_score, tool_compliance_score, summary, findings, suggestions,\n"
        "per_agent_scores, per_tool_scores, issues, tool_format_issues.\n"
        "Issue schema: issue_id, category, severity(low|medium|high|critical), message, evidence, suggested_fixes."
    )
    user_prompt = json.dumps(payload, ensure_ascii=True)

    structured_llm = build_structured_model(
        model=model,
        anthropic_api_key=anthropic_key,
        schema=TrajectoryAuditPayload,
        temperature=0.0,
        max_tokens=1200,
    )
    parsed = await structured_llm.ainvoke(build_prompt_messages(system_prompt, user_prompt))
    payload = (
        parsed
        if isinstance(parsed, TrajectoryAuditPayload)
        else TrajectoryAuditPayload.model_validate(parsed)
    )

    llm_tool_issues = [issue.model_dump(mode="json") for issue in payload.tool_format_issues]
    merged_tool_issues = format_issues + llm_tool_issues
    parsed_issues = [issue.model_dump(mode="json") for issue in payload.issues]

    return AgentVerdict(
        agent_name="trajectory_grader",
        score=round(float(payload.overall_score), 2),
        risk_level=_risk_from_score(float(payload.overall_score)),
        summary=payload.summary,
        findings=[str(f) for f in payload.findings],
        suggestions=[str(s) for s in payload.suggestions],
        details={
            "issues": parsed_issues + merged_tool_issues,
            "tool_format_issues": merged_tool_issues,
            "tool_compliance_score": round(float(payload.tool_compliance_score), 2),
            "per_agent_scores": {
                key: round(float(value), 2) for key, value in payload.per_agent_scores.items()
            },
            "per_tool_scores": {
                key: round(float(value), 2) for key, value in payload.per_tool_scores.items()
            },
            "analysis_mode": "llm_plus_deterministic_tool_validator",
        },
    )
