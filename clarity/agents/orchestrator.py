"""LangGraph orchestrator for parallel agent execution."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from clarity.agents.confidence import run_confidence_check
from clarity.agents.context_analyzer import run_context_quality_check
from clarity.agents.hallucination import run_hallucination_check
from clarity.agents.reasoning import run_reasoning_check
from clarity.agents.state import VerificationState
from clarity.agents.trajectory_grader import run_trajectory_grader
from clarity.config import settings
from clarity.models import AgentVerdict, RiskLevel, TrustReport

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import RetryPolicy
except Exception:  # pragma: no cover
    END = "END"
    START = "START"
    StateGraph = None
    RetryPolicy = None


_GRAPH = None
_AGENT_TIMEOUT_SECONDS = 30
_PLACEHOLDER_KEYS = {
    "your-tinyfish-api-key-here",
    "your-api-key-here",
    "sk-ant-xxxxxxxxxxxxxxxxxxxxx",
    "gsk_xxxxxxxxxxxxxxxxxxxxx",
}
_WEIGHTS = {
    # Tuned to emphasize factual reliability while preserving trajectory/tool quality.
    "hallucination": 0.30,
    "reasoning": 0.22,
    "confidence": 0.18,
    "context_quality": 0.10,
    "trajectory": 0.20,
}


def _risk_from_score(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.LOW
    if score >= 60:
        return RiskLevel.MEDIUM
    if score >= 40:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def _resolve_required_api_key(context: dict[str, Any], key_name: str) -> str:
    value = str(context.get(key_name) or getattr(settings, key_name, "") or "").strip()
    lowered = value.lower()
    looks_placeholder = (
        lowered in _PLACEHOLDER_KEYS
        or lowered.startswith("your-")
        or lowered.startswith("sk-ant-xxxxxxxx")
        or lowered.startswith("gsk_x")
    )
    if (not value) or looks_placeholder:
        raise RuntimeError(
            f"{key_name.upper()} is required for deep-check verification. "
            f"Please set `{key_name.upper()}` in your environment or SDK config."
        )
    return value


async def _run_with_timeout(coro: Any) -> Any:
    return await asyncio.wait_for(coro, timeout=_AGENT_TIMEOUT_SECONDS)


def _build_fallback_verdict(
    *,
    agent_name: str,
    failure_type: str,
    message: str,
    started_at: float,
    elapsed_ms: float,
    timeout_seconds: int = _AGENT_TIMEOUT_SECONDS,
) -> AgentVerdict:
    score = 45.0 if failure_type == "timeout" else 35.0
    severity = "high" if failure_type == "timeout" else "critical"
    suggestions = [
        "Retry verification with a smaller response payload.",
        "Reduce model latency by lowering max tokens or simplifying prompt.",
        "Inspect provider/tool availability before rerunning deep-check.",
    ]
    if failure_type == "error":
        suggestions = [
            "Inspect the underlying exception in agent details.",
            "Check API keys, request schema, and provider availability.",
            "Retry verification after fixing the failing dependency.",
        ]

    issue = {
        "issue_id": f"{agent_name}_{failure_type}",
        "category": "agent_runtime",
        "severity": severity,
        "message": message,
        "evidence": {
            "agent_name": agent_name,
            "failure_type": failure_type,
            "timeout_seconds": timeout_seconds,
        },
        "suggested_fixes": suggestions,
    }
    details = {
        "issues": [issue],
        "execution": {
            "status": failure_type,
            "timed_out": failure_type == "timeout",
            "started_at_s": round(started_at, 6),
            "elapsed_ms": round(float(elapsed_ms), 2),
            "timeout_seconds": timeout_seconds,
        },
    }
    return AgentVerdict(
        agent_name=agent_name,
        score=score,
        risk_level=_risk_from_score(score),
        summary=(
            f"{agent_name} exceeded the {timeout_seconds}s timeout and fallback scoring was used."
            if failure_type == "timeout"
            else f"{agent_name} failed during execution and fallback scoring was used."
        ),
        findings=[message],
        suggestions=suggestions,
        details=details,
    )


def _attach_execution_metadata(
    verdict: AgentVerdict,
    *,
    started_at: float,
    elapsed_ms: float,
    timeout_seconds: int = _AGENT_TIMEOUT_SECONDS,
) -> AgentVerdict:
    details = dict(verdict.details or {})
    details["execution"] = {
        "status": "ok",
        "timed_out": False,
        "started_at_s": round(started_at, 6),
        "elapsed_ms": round(float(elapsed_ms), 2),
        "timeout_seconds": timeout_seconds,
    }
    verdict.details = details
    return verdict


async def _run_agent_resiliently(coro: Any, *, agent_name: str) -> AgentVerdict:
    started_at = time.perf_counter()
    try:
        verdict = await _run_with_timeout(coro)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        if not isinstance(verdict, AgentVerdict):
            raise RuntimeError(f"{agent_name} returned unexpected type: {type(verdict).__name__}")
        return _attach_execution_metadata(
            verdict,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            timeout_seconds=_AGENT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return _build_fallback_verdict(
            agent_name=agent_name,
            failure_type="timeout",
            message=f"{agent_name} timed out after {_AGENT_TIMEOUT_SECONDS}s.",
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            timeout_seconds=_AGENT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return _build_fallback_verdict(
            agent_name=agent_name,
            failure_type="error",
            message=f"{agent_name} failed with {type(exc).__name__}: {exc}",
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            timeout_seconds=_AGENT_TIMEOUT_SECONDS,
        )


async def _hallucination_node(state: VerificationState) -> dict[str, Any]:
    verdict = await _run_agent_resiliently(
        run_hallucination_check(state["context"]),
        agent_name="hallucination_detector",
    )
    return {"hallucination_verdict": verdict}


async def _reasoning_node(state: VerificationState) -> dict[str, Any]:
    verdict = await _run_agent_resiliently(
        run_reasoning_check(state["context"]),
        agent_name="reasoning_validator",
    )
    return {"reasoning_verdict": verdict}


async def _confidence_node(state: VerificationState) -> dict[str, Any]:
    verdict = await _run_agent_resiliently(
        run_confidence_check(state["context"]),
        agent_name="confidence_calibrator",
    )
    return {"confidence_verdict": verdict}


async def _context_quality_node(state: VerificationState) -> dict[str, Any]:
    verdict = await _run_agent_resiliently(
        run_context_quality_check(state["context"]),
        agent_name="context_analyzer",
    )
    return {"context_quality_verdict": verdict}


async def _trajectory_node(state: VerificationState) -> dict[str, Any]:
    hallucination = state.get("hallucination_verdict")
    reasoning = state.get("reasoning_verdict")
    confidence = state.get("confidence_verdict")
    context_quality = state.get("context_quality_verdict")
    if not all([hallucination, reasoning, confidence, context_quality]):
        raise RuntimeError("Trajectory grader requires all upstream agent verdicts.")

    verdict = await _run_agent_resiliently(
        run_trajectory_grader(
            state["context"],
            hallucination=hallucination,
            reasoning=reasoning,
            confidence=confidence,
            context_quality=context_quality,
        ),
        agent_name="trajectory_grader",
    )
    return {"trajectory_verdict": verdict}


async def _aggregate_node(state: VerificationState) -> dict[str, Any]:
    hallucination = state.get("hallucination_verdict")
    reasoning = state.get("reasoning_verdict")
    confidence = state.get("confidence_verdict")
    context_quality = state.get("context_quality_verdict")
    trajectory = state.get("trajectory_verdict")

    assert hallucination is not None
    assert reasoning is not None
    assert confidence is not None
    assert context_quality is not None
    assert trajectory is not None

    overall_score = (
        hallucination.score * _WEIGHTS["hallucination"]
        + reasoning.score * _WEIGHTS["reasoning"]
        + confidence.score * _WEIGHTS["confidence"]
        + context_quality.score * _WEIGHTS["context_quality"]
        + trajectory.score * _WEIGHTS["trajectory"]
    )
    overall_score = round(max(0.0, min(100.0, overall_score)), 2)

    warnings = []
    for verdict in [hallucination, reasoning, confidence, context_quality, trajectory]:
        if verdict.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            warnings.append(f"{verdict.agent_name} risk is {verdict.risk_level.value}.")
        execution = verdict.details.get("execution", {})
        if isinstance(execution, dict):
            status = str(execution.get("status", "")).lower()
            if status == "timeout":
                warnings.append(f"{verdict.agent_name} timed out; fallback verdict was used.")
            elif status == "error":
                warnings.append(f"{verdict.agent_name} failed; fallback verdict was used.")

    # Parallel fan-out observability: compute start-time spread across primary four agents.
    primary_starts: list[float] = []
    for verdict in [hallucination, reasoning, confidence, context_quality]:
        execution = verdict.details.get("execution", {})
        if isinstance(execution, dict):
            started_at_s = execution.get("started_at_s")
            if isinstance(started_at_s, (float, int)):
                primary_starts.append(float(started_at_s))
    if len(primary_starts) == 4:
        spread_ms = round((max(primary_starts) - min(primary_starts)) * 1000.0, 2)
        trajectory_details = dict(trajectory.details or {})
        trajectory_details["parallel_start_spread_ms"] = spread_ms
        trajectory.details = trajectory_details
        if spread_ms > 250.0:
            warnings.append(
                f"Parallel fan-out start spread was {spread_ms}ms; investigate execution contention."
            )

    # Context-level quick warnings.
    context = state.get("context", {})
    if context.get("is_truncated"):
        warnings.append("Model output may be truncated due to max tokens.")
    if context.get("tools_available_but_unused"):
        warnings.append("Tools were available but not used.")
    if context.get("temperature", 0.0) > 0.9:
        warnings.append("High temperature may increase output variance.")
    tool_format_issues = trajectory.details.get("tool_format_issues", [])
    if isinstance(tool_format_issues, list) and tool_format_issues:
        warnings.append(f"Tool format compliance issues detected: {len(tool_format_issues)}.")

    deduped_warnings = sorted(set(warnings))
    return {"overall_score": overall_score, "warnings": deduped_warnings}


def build_parallel_verification_graph():
    """Build and compile the LangGraph state graph."""
    if StateGraph is None:
        return None

    graph = StateGraph(VerificationState)
    retry_policy = RetryPolicy(max_attempts=2) if RetryPolicy is not None else None

    def _add_node(name: str, node_fn: Any) -> None:
        if retry_policy is None:
            graph.add_node(name, node_fn)
            return
        try:
            graph.add_node(name, node_fn, retry_policy=retry_policy)
        except TypeError:
            graph.add_node(name, node_fn)

    _add_node("hallucination", _hallucination_node)
    _add_node("reasoning", _reasoning_node)
    _add_node("confidence", _confidence_node)
    _add_node("context_quality", _context_quality_node)
    _add_node("trajectory", _trajectory_node)
    graph.add_node("aggregate", _aggregate_node)

    graph.add_edge(START, "hallucination")
    graph.add_edge(START, "reasoning")
    graph.add_edge(START, "confidence")
    graph.add_edge(START, "context_quality")

    graph.add_edge("hallucination", "trajectory")
    graph.add_edge("reasoning", "trajectory")
    graph.add_edge("confidence", "trajectory")
    graph.add_edge("context_quality", "trajectory")
    graph.add_edge("trajectory", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


async def _fallback_parallel_execution(context: dict[str, Any]) -> dict[str, Any]:
    """Fallback execution if LangGraph is unavailable."""
    results = await asyncio.gather(
        _run_agent_resiliently(
            run_hallucination_check(context),
            agent_name="hallucination_detector",
        ),
        _run_agent_resiliently(
            run_reasoning_check(context),
            agent_name="reasoning_validator",
        ),
        _run_agent_resiliently(
            run_confidence_check(context),
            agent_name="confidence_calibrator",
        ),
        _run_agent_resiliently(
            run_context_quality_check(context),
            agent_name="context_analyzer",
        ),
    )
    trajectory = await _run_agent_resiliently(
        run_trajectory_grader(
            context,
            hallucination=results[0],
            reasoning=results[1],
            confidence=results[2],
            context_quality=results[3],
        ),
        agent_name="trajectory_grader",
    )
    return {
        "hallucination_verdict": results[0],
        "reasoning_verdict": results[1],
        "confidence_verdict": results[2],
        "context_quality_verdict": results[3],
        "trajectory_verdict": trajectory,
    }


async def run_verification_pipeline(exchange_id: str, context: dict[str, Any]) -> TrustReport:
    """Run all 4 verification agents and return a complete TrustReport."""
    global _GRAPH
    # Strict mode: require all external keys used by deep-check pipeline.
    context["anthropic_api_key"] = _resolve_required_api_key(context, "anthropic_api_key")
    context["tinyfish_api_key"] = _resolve_required_api_key(context, "tinyfish_api_key")

    if _GRAPH is None:
        _GRAPH = build_parallel_verification_graph()

    if _GRAPH is None:
        state: dict[str, Any] = {"exchange_id": exchange_id, "context": context}
        state.update(await _fallback_parallel_execution(context))
        state.update(await _aggregate_node(state))
        final_state = state
    else:
        initial_state: VerificationState = {"exchange_id": exchange_id, "context": context}
        final_state = await _GRAPH.ainvoke(initial_state)

    hallucination = final_state.get("hallucination_verdict")
    reasoning = final_state.get("reasoning_verdict")
    confidence = final_state.get("confidence_verdict")
    context_quality = final_state.get("context_quality_verdict")
    trajectory = final_state.get("trajectory_verdict")
    if not all([hallucination, reasoning, confidence, context_quality, trajectory]):
        raise RuntimeError("Verification pipeline failed: one or more agent verdicts are missing.")

    overall_score = final_state.get("overall_score")
    if overall_score is None:
        overall_score = round(
            hallucination.score * _WEIGHTS["hallucination"]
            + reasoning.score * _WEIGHTS["reasoning"]
            + confidence.score * _WEIGHTS["confidence"]
            + context_quality.score * _WEIGHTS["context_quality"]
            + trajectory.score * _WEIGHTS["trajectory"],
            2,
        )

    warnings = final_state.get("warnings", [])
    model_used = context.get("model", "unknown")
    temperature = float(context.get("temperature", 0.0) or 0.0)
    tokens_used = int(context.get("total_tokens", 0) or 0)

    return TrustReport(
        report_id=str(uuid.uuid4()),
        exchange_id=exchange_id,
        overall_score=overall_score,
        overall_risk=_risk_from_score(overall_score),
        hallucination=hallucination,
        reasoning=reasoning,
        confidence=confidence,
        context_quality=context_quality,
        trajectory=trajectory,
        warnings=warnings,
        model_used=model_used,
        temperature=temperature,
        tokens_used=tokens_used,
    )
