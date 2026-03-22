"""Hallucination and factual grounding agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from clarity.agents.langchain_runtime import build_prompt_messages, build_structured_model
from clarity.config import settings
from clarity.integrations.tinyfish_client import TinyFishClient
from clarity.models import AgentVerdict, RiskLevel


def _risk_from_score(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.LOW
    if score >= 60:
        return RiskLevel.MEDIUM
    if score >= 40:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


class ClaimCandidate(BaseModel):
    """Strict schema for extracted factual claims."""

    claim_id: str = Field(..., min_length=1, max_length=64)
    claim: str = Field(..., min_length=1, max_length=500)
    source_hint: str | None = Field(default=None, max_length=200)


class ClaimExtractionPayload(BaseModel):
    """Structured extraction payload for factual claims."""

    claims: list[ClaimCandidate] = Field(default_factory=list)


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


def _resolve_anthropic_key(context: dict[str, Any]) -> str:
    return str((context.get("anthropic_api_key") or settings.anthropic_api_key or "")).strip()


async def _extract_claims_llm(context: dict[str, Any]) -> list[ClaimCandidate]:
    anthropic_key = _resolve_anthropic_key(context)
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for hallucination claim extraction.")

    model = (
        context.get("verifier_model")
        or settings.clarity_verifier_model
        or "claude-sonnet-4-6"
    )
    output = context.get("response_content", "")
    if not output.strip():
        return []

    system_prompt = (
        "Extract verifiable factual claims from assistant output.\n"
        "Return a structured object with key `claims` where value is an array.\n"
        "Each claim must have: claim_id (string), claim (string), source_hint (string|null).\n"
        "Exclude opinions and procedural text."
    )
    user_prompt = f"Assistant output:\n{output}"

    structured_llm = build_structured_model(
        model=model,
        anthropic_api_key=anthropic_key,
        schema=ClaimExtractionPayload,
        temperature=0.0,
        max_tokens=900,
    )
    parsed = await structured_llm.ainvoke(build_prompt_messages(system_prompt, user_prompt))
    payload = (
        parsed
        if isinstance(parsed, ClaimExtractionPayload)
        else ClaimExtractionPayload.model_validate(parsed)
    )
    return payload.claims[:12]


async def run_hallucination_check(context: dict[str, Any]) -> AgentVerdict:
    """Detect factual hallucinations using claim extraction + TinyFish verification."""
    claims = await _extract_claims_llm(context)

    findings: list[str] = []
    suggestions: list[str] = []
    issues: list[dict[str, Any]] = []

    if not claims:
        score = 95.0
        findings.append("No strongly verifiable factual claims detected.")
        return AgentVerdict(
            agent_name="hallucination_detector",
            score=score,
            risk_level=_risk_from_score(score),
            summary="Low factual-risk answer with minimal factual claims.",
            findings=findings,
            suggestions=["For critical decisions, ask model to provide explicit citations."],
            details={"claims": [], "verification_results": [], "issues": []},
        )

    tinyfish = TinyFishClient(api_key=str(context.get("tinyfish_api_key", "") or ""))
    try:
        verification_results = await tinyfish.verify_claims_batch([c.claim for c in claims])
    except Exception as exc:
        # Degrade gracefully to inconclusive claim checks if TinyFish is slow/unavailable.
        verification_results = [
            {
                "claim": c.claim,
                "status": "inconclusive",
                "verified": None,
                "confidence": None,
                "evidence": [],
                "error": f"tinyfish_unavailable: {type(exc).__name__}: {exc}",
            }
            for c in claims
        ]

    false_count = 0
    inconclusive_count = 0
    verified_count = 0

    for idx, result in enumerate(verification_results):
        claim = claims[idx].claim
        status = (result.get("status") or "inconclusive").lower()
        evidence = result.get("evidence") or []
        error = result.get("error")

        if status == "verified":
            verified_count += 1
            findings.append(f"Verified claim: {claim}")
            continue

        if status == "false":
            false_count += 1
            findings.append(f"False or conflicting claim: {claim}")
            issues.append(
                _build_issue(
                    issue_id=f"hallucination_false_{idx+1}",
                    category="factual_error",
                    severity="high",
                    message=f"Claim appears false or contradicted by sources: {claim}",
                    evidence={"claim": claim, "evidence": evidence},
                    suggested_fixes=[
                        "Require citations for factual statements.",
                        "Use web/tool lookup before finalizing facts.",
                    ],
                )
            )
            continue

        inconclusive_count += 1
        findings.append(f"Inconclusive claim verification: {claim}")
        issues.append(
            _build_issue(
                issue_id=f"hallucination_inconclusive_{idx+1}",
                category="unverified_claim",
                severity="medium",
                message=f"Could not verify claim reliably: {claim}",
                evidence={"claim": claim, "error": error, "evidence": evidence},
                suggested_fixes=[
                    "Add tool grounding or provide source URLs in prompt.",
                    "Reduce unsupported factual claims.",
                ],
            )
        )

    score = 100.0 - (false_count * 30.0) - (inconclusive_count * 5.0)
    score = max(0.0, min(100.0, round(score, 2)))

    if false_count > 0:
        suggestions.append("For factual tasks, require source-backed answers and verification steps.")
    if inconclusive_count > 0:
        suggestions.append("Use authoritative sources/tools for uncertain claims.")
    if not suggestions:
        suggestions.append("Maintain factual grounding for future prompts with citation requirements.")

    summary = (
        "Factual grounding is strong."
        if score >= 80
        else "Some factual uncertainty was detected."
        if score >= 60
        else "Significant hallucination risk detected in factual claims."
    )

    return AgentVerdict(
        agent_name="hallucination_detector",
        score=score,
        risk_level=_risk_from_score(score),
        summary=summary,
        findings=findings,
        suggestions=suggestions,
        details={
            "claims": [claim.model_dump(mode="json") for claim in claims],
            "verification_results": verification_results,
            "counts": {
                "verified": verified_count,
                "false": false_count,
                "inconclusive": inconclusive_count,
            },
            "issues": issues,
        },
    )
