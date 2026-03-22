"""Developer-facing SDK for Clarity verification."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import httpx
from anthropic import Anthropic

from clarity.agents.orchestrator import run_verification_pipeline
from clarity.config import settings
from clarity.models import TrustReport
from clarity.proxy.interceptor import ClarityInterceptor
from clarity.proxy.metadata import extract_verification_context

_PLACEHOLDER_KEYS = {
    "your-tinyfish-api-key-here",
    "your-api-key-here",
    "sk-ant-xxxxxxxxxxxxxxxxxxxxx",
}


class ClarityResult:
    """Result object returned to SDK users."""

    def __init__(self, content: str, trust_report: TrustReport):
        self.content = content
        self.trust_report = trust_report

    @property
    def score(self) -> float:
        """Overall trust score (0-100)."""
        return self.trust_report.overall_score

    @property
    def risk(self) -> str:
        """Risk level: low, medium, high, or critical."""
        return self.trust_report.overall_risk.value

    @property
    def warnings(self) -> list[str]:
        """List of warning messages."""
        return self.trust_report.warnings

    @property
    def summary(self) -> dict[str, Any]:
        """Compact summary dict for explainers."""
        return self.trust_report.get_summary()

    def __repr__(self) -> str:
        return f"ClarityResult(score={self.score}, risk={self.risk}, warnings={len(self.warnings)})"


class ClarityClient:
    """
    Developer-facing SDK for Clarity verification.

    Two modes:
    - Remote mode: calls running Clarity server via HTTP.
    - Local mode: calls Claude + verification pipeline in-process.
    """

    def __init__(
        self,
        clarity_api_url: str = "",
        local_mode: bool = False,
        anthropic_api_key: str = "",
        tinyfish_api_key: str = "",
    ):
        self.clarity_api_url = clarity_api_url
        self.local_mode = local_mode
        self.anthropic_api_key = anthropic_api_key
        self.tinyfish_api_key = tinyfish_api_key

        if not self.anthropic_api_key:
            self.anthropic_api_key = str(
                os.getenv("ANTHROPIC_API_KEY", "") or settings.anthropic_api_key or ""
            )
        if not self.tinyfish_api_key:
            self.tinyfish_api_key = str(
                os.getenv("TINYFISH_API_KEY", "") or settings.tinyfish_api_key or ""
            )

        if local_mode:
            self.anthropic_api_key = self._require_api_key(
                "ANTHROPIC_API_KEY", self.anthropic_api_key
            )
            self.tinyfish_api_key = self._require_api_key(
                "TINYFISH_API_KEY", self.tinyfish_api_key
            )

    def verify(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> ClarityResult:
        """Verify LLM output and return trust report with content."""
        if self.local_mode:
            return self._verify_local(
                messages=messages,
                system=system,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )

        if not self.clarity_api_url:
            raise ValueError(
                "Remote mode requires clarity_api_url. Either set it or use local_mode=True."
            )
        return self._verify_remote(
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
        tools: Optional[list[dict[str, Any]]],
    ) -> ClarityResult:
        """Run full Claude + Clarity pipeline locally."""
        print("[Clarity] Starting local verification...")

        client = Anthropic(api_key=self.anthropic_api_key)
        interceptor = ClarityInterceptor()
        exchange = interceptor.capture_sync_call(
            client=client,
            model=model,
            messages=messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools or [],
        )

        print(f"[Clarity] Captured LLM exchange: {exchange.exchange_id}")

        context = extract_verification_context(exchange)
        print(f"[Clarity] Extracted verification context ({len(context)} keys)")

        context["anthropic_api_key"] = self.anthropic_api_key
        context["tinyfish_api_key"] = self.tinyfish_api_key
        context["verifier_model"] = settings.clarity_verifier_model

        print("[Clarity] Running verification pipeline (agents)...")
        trust_report = _run_coro_sync(
            run_verification_pipeline(
                exchange_id=exchange.exchange_id,
                context=context,
            )
        )

        print(
            f"[Clarity] Local verification complete. Score: {trust_report.overall_score:.1f}/100 "
            f"({trust_report.overall_risk.value})"
        )
        return ClarityResult(content=exchange.response.content, trust_report=trust_report)

    def _verify_remote(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        tools: Optional[list[dict[str, Any]]],
    ) -> ClarityResult:
        """Call remote Clarity API server."""
        print(f"[Clarity] Calling remote server: {self.clarity_api_url}")
        payload = {
            "messages": messages,
            "system": system,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools or [],
        }
        url = f"{self.clarity_api_url}/api/v1/verify"

        try:
            response = httpx.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise ValueError(
                f"Failed to connect to Clarity server at {self.clarity_api_url}. "
                "Is the server running? Try: python -m clarity.main"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Clarity server returned error: {exc.response.status_code} - {exc.response.text}"
            ) from exc

        data = response.json()
        trust_report_dict = data["trust_report"]
        if "timestamp" in trust_report_dict:
            trust_report_dict.pop("timestamp")
        trust_report = TrustReport(**trust_report_dict)
        print(f"[Clarity] Remote verification complete. Score: {trust_report.overall_score:.1f}/100")
        return ClarityResult(content=data["content"], trust_report=trust_report)

    @staticmethod
    def _require_api_key(key_name: str, key_value: str) -> str:
        value = str(key_value or "").strip()
        normalized = value.lower()
        looks_placeholder = (
            not value
            or normalized in _PLACEHOLDER_KEYS
            or normalized.startswith("your-")
            or normalized.startswith("sk-ant-xxxxxxxx")
        )
        if looks_placeholder:
            raise ValueError(
                f"{key_name} is not available. Please set a valid `{key_name}` "
                "in your environment or SDK config."
            )
        return value


def _run_coro_sync(coro):
    """Run async coroutines safely from sync SDK methods."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()
