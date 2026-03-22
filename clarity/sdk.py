"""Developer-facing SDK for Clarity."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
import httpx
try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None

from clarity.proxy.interceptor import ClarityInterceptor
from clarity.proxy.metadata import extract_verification_context
from clarity.agents.orchestrator import run_verification_pipeline
from clarity.config import settings
from clarity.models import TrustReport


class ClarityResult:
    """
    Response object with familiar LLM fields plus Clarity verification details.

    The top-level fields mirror common SDK response patterns:
    - content
    - additional_kwargs
    - response_metadata
    - usage_metadata
    - tool_calls
    - id
    """

    def __init__(
        self,
        content: str,
        trust_report: TrustReport,
        *,
        message_id: str | None = None,
        additional_kwargs: dict[str, Any] | None = None,
        response_metadata: dict[str, Any] | None = None,
        usage_metadata: dict[str, Any] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ):
        self.content = content
        self.trust_report = trust_report
        self.id = message_id
        self.additional_kwargs = additional_kwargs or {}
        self.response_metadata = response_metadata or {}
        self.usage_metadata = usage_metadata
        self.tool_calls = tool_calls or []

    @property
    def score(self) -> float:
        return self.trust_report.overall_score

    @property
    def risk(self) -> str:
        return self.trust_report.overall_risk.value

    @property
    def warnings(self) -> list[str]:
        return self.trust_report.warnings

    @property
    def summary(self) -> dict[str, Any]:
        return self.trust_report.get_summary()

    @property
    def mistakes(self) -> list[dict[str, Any]]:
        return _extract_mistakes_from_report(self.trust_report)

    @property
    def clarity(self) -> dict[str, Any]:
        return {
            "mode": "deep",
            "overall_score": self.trust_report.overall_score,
            "overall_risk": self.trust_report.overall_risk.value,
            "warnings": self.trust_report.warnings,
            "agent_scores": {
                "hallucination": self.trust_report.hallucination.score,
                "reasoning": self.trust_report.reasoning.score,
                "confidence": self.trust_report.confidence.score,
                "context_quality": self.trust_report.context_quality.score,
                "trajectory": (
                    self.trust_report.trajectory.score
                    if self.trust_report.trajectory is not None
                    else None
                ),
            },
            "mistakes": self.mistakes,
            "report": self.trust_report.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "additional_kwargs": self.additional_kwargs,
            "response_metadata": self.response_metadata,
            "usage_metadata": self.usage_metadata,
            "tool_calls": self.tool_calls,
            "clarity": self.clarity,
        }


class ClarityClient:
    """
    Developer-facing API for Clarity verification.
    
    Usage (Remote mode — calls server):
        client = ClarityClient(clarity_api_url="http://localhost:8000")
        result = client.verify(
            messages=[{"role": "user", "content": "Explain React hooks"}],
            system="You are a helpful assistant.",
        )
        print(result.score)  # 0-100
        print(result.risk)   # low/medium/high/critical
    
    Usage (Local mode — in-process):
        client = ClarityClient(local_mode=True, anthropic_api_key="sk-ant-...")
        result = client.verify(messages=[...])
    """

    def __init__(
        self,
        clarity_api_url: str = "",
        local_mode: bool = False,
        anthropic_api_key: str = "",
        tinyfish_api_key: str = "",
    ):
        """
        Initialize ClarityClient.
        
        Args:
            clarity_api_url: URL of running Clarity server (for remote mode)
            local_mode: If True, runs verification locally without server
            anthropic_api_key: Anthropic API key (for local mode)
            tinyfish_api_key: TinyFish API key (for hallucination verification in local mode)
        """
        self.clarity_api_url = clarity_api_url
        self.local_mode = local_mode
        self.anthropic_api_key = anthropic_api_key
        self.tinyfish_api_key = tinyfish_api_key

    def verify(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: list[dict[str, Any]] = None,
    ) -> ClarityResult:
        """
        Verify LLM output and get a ClarityResult response object.
        
        Args:
            messages: List of message dicts with role/content
            system: System prompt
            model: Model name
            temperature: Temperature parameter
            max_tokens: Max tokens limit
            tools: List of tool definitions
            
        Returns:
            ClarityResult with content + trust_report
        """
        
        if self.local_mode:
            return self._verify_local(
                messages=messages,
                system=system,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )
        else:
            return self._verify_remote(
                messages=messages,
                system=system,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )

    def invoke(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: list[dict[str, Any]] = None,
    ) -> ClarityResult:
        """Alias for verify() for SDK familiarity."""
        return self.verify(
            messages=messages,
            system=system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )

    def _verify_local(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        tools: list[dict[str, Any]],
    ) -> ClarityResult:
        """Local verification — runs full pipeline in-process."""
        
        if Anthropic is None:
            raise RuntimeError(
                "anthropic package is not installed. Run `pip install -e .` to use local_mode."
            )
        anthropic_key = str(self.anthropic_api_key or settings.anthropic_api_key or "").strip()
        if not anthropic_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required. Set it in `.env` or pass `anthropic_api_key` to ClarityClient."
            )
        tinyfish_key = str(self.tinyfish_api_key or settings.tinyfish_api_key or "").strip()
        if not tinyfish_key:
            raise RuntimeError(
                "TINYFISH_API_KEY is required for strict deep-check mode. "
                "Set it in `.env` or pass `tinyfish_api_key` to ClarityClient."
            )

        # Call Claude via interceptor
        client = Anthropic(api_key=anthropic_key)
        interceptor = ClarityInterceptor()
        exchange = interceptor.capture_sync_call(
            client=client,
            model=model,
            messages=messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )
        
        # Extract context and run verification
        context = extract_verification_context(exchange)
        context["anthropic_api_key"] = anthropic_key
        context["tinyfish_api_key"] = tinyfish_key

        trust_report = _run_coro_sync(
            run_verification_pipeline(
                exchange_id=exchange.exchange_id,
                context=context,
            )
        )

        usage_metadata = {
            "input_tokens": exchange.response.input_tokens,
            "output_tokens": exchange.response.output_tokens,
            "total_tokens": exchange.response.input_tokens + exchange.response.output_tokens,
        }
        response_metadata = {
            "model_name": exchange.request.model,
            "stop_reason": exchange.response.stop_reason,
            "latency_ms": round(exchange.response.latency_ms, 2),
        }

        return ClarityResult(
            content=exchange.response.content,
            trust_report=trust_report,
            message_id=exchange.exchange_id,
            additional_kwargs={},
            response_metadata=response_metadata,
            usage_metadata=usage_metadata,
            tool_calls=exchange.response.tool_calls or [],
        )

    def _verify_remote(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        tools: list[dict[str, Any]],
    ) -> ClarityResult:
        """Remote verification — calls Clarity server."""
        
        payload = {
            "messages": messages,
            "system": system,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools or [],
        }
        
        url = f"{self.clarity_api_url}/api/v1/verify"
        
        response = httpx.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse trust report
        trust_report_dict = data["trust_report"]
        trust_report = TrustReport(**trust_report_dict)

        return ClarityResult(
            content=data["content"],
            trust_report=trust_report,
            message_id=trust_report.exchange_id,
            additional_kwargs={},
            response_metadata={},
            usage_metadata={"total_tokens": trust_report.tokens_used},
            tool_calls=[],
        )


def _run_coro_sync(coro):
    """
    Run async coroutines safely from sync SDK methods.

    In notebook/event-loop contexts, run the coroutine in a worker thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _extract_mistakes_from_report(report: TrustReport) -> list[dict[str, Any]]:
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    mistakes: list[dict[str, Any]] = []

    verdicts = [
        report.hallucination,
        report.reasoning,
        report.confidence,
        report.context_quality,
    ]
    if report.trajectory is not None:
        verdicts.append(report.trajectory)

    for verdict in verdicts:
        issues = verdict.details.get("issues", [])
        if isinstance(issues, list) and issues:
            for idx, issue in enumerate(issues, start=1):
                if not isinstance(issue, dict):
                    continue
                mistakes.append(
                    {
                        "issue_id": issue.get("issue_id") or f"{verdict.agent_name}_{idx}",
                        "agent": verdict.agent_name,
                        "category": issue.get("category", "general"),
                        "severity": issue.get("severity", verdict.risk_level.value),
                        "message": issue.get("message", ""),
                        "evidence": issue.get("evidence", {}),
                        "suggested_fixes": issue.get("suggested_fixes", verdict.suggestions),
                    }
                )
            continue

        # Fallback from findings when no structured issues are present.
        for idx, finding in enumerate(verdict.findings, start=1):
            mistakes.append(
                {
                    "issue_id": f"{verdict.agent_name}_finding_{idx}",
                    "agent": verdict.agent_name,
                    "category": "agent_finding",
                    "severity": verdict.risk_level.value,
                    "message": finding,
                    "evidence": {},
                    "suggested_fixes": verdict.suggestions,
                }
            )

    mistakes.sort(key=lambda m: severity_order.get(str(m.get("severity", "low")).lower(), 99))
    return mistakes
