"""Developer-facing SDK for Clarity verification."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
import httpx
import uuid
import os

from anthropic import Anthropic

from clarity.proxy.interceptor import ClarityInterceptor
from clarity.proxy.metadata import extract_verification_context
from clarity.agents.orchestrator import run_verification_pipeline
from clarity.models import TrustReport, AgentVerdict, RiskLevel
from clarity.config import settings


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
        """Compact summary dict for Ada explainer."""
        return self.trust_report.get_summary()
    
    def __repr__(self) -> str:
        return f"ClarityResult(score={self.score}, risk={self.risk}, warnings={len(self.warnings)})"


class ClarityClient:
    """
    Developer-facing SDK for Clarity verification.
    
    Two modes of operation:
    
    **Remote mode** (calls server):
        ```python
        client = ClarityClient(clarity_api_url="http://localhost:8000")
        result = client.verify(
            messages=[{"role": "user", "content": "Explain React hooks"}],
            system="You are a helpful assistant.",
        )
        print(result.score)  # 0-100
        print(result.risk)   # low/medium/high/critical
        ```
    
    **Local mode** (in-process, no server needed):
        ```python
        client = ClarityClient(local_mode=True, anthropic_api_key="sk-ant-...")
        result = client.verify(messages=[...])
        ```
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
                            e.g., "http://localhost:8000"
            local_mode: If True, runs verification locally without server
            anthropic_api_key: Anthropic API key (required for local mode)
                              Falls back to ANTHROPIC_API_KEY env var if not provided
            tinyfish_api_key: TinyFish API key for hallucination verification (optional)
                             Falls back to TINYFISH_API_KEY env var if not provided
        
        Raises:
            ValueError: If local_mode=True but no API key provided
        """
        self.clarity_api_url = clarity_api_url
        self.local_mode = local_mode
        self.anthropic_api_key = anthropic_api_key
        self.tinyfish_api_key = tinyfish_api_key
        
        if local_mode and not anthropic_api_key:
            # Try to get from environment
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.anthropic_api_key:
                raise ValueError(
                    "local_mode requires anthropic_api_key to be set "
                    "(either via parameter or ANTHROPIC_API_KEY env var)"
                )
        
        # Try to get TinyFish key from environment if not provided
        if not self.tinyfish_api_key:
            self.tinyfish_api_key = os.getenv("TINYFISH_API_KEY", "")

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
        Verify LLM output and get a trust report.
        
        Args:
            messages: List of message dicts with 'role' (user/assistant) and 'content'
            system: System prompt (optional)
            model: Claude model ID (default: claude-sonnet-4-20250514)
            temperature: Sampling temperature 0.0-1.0 (default: 0.7)
            max_tokens: Max output tokens (optional)
            tools: List of tool definitions (optional)
            
        Returns:
            ClarityResult with:
                - content: str — the LLM output
                - trust_report: TrustReport — detailed verification results
                - score: float — 0-100 trust score
                - risk: str — low/medium/high/critical
                - warnings: list[str] — issues found
                - summary: dict — compact summary for Ada chat
        
        Raises:
            ValueError: If remote mode but server unavailable
            Exception: If verification fails
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
            if not self.clarity_api_url:
                raise ValueError(
                    "Remote mode requires clarity_api_url. "
                    "Either set it or use local_mode=True"
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
        tools: list[dict[str, Any]],
    ) -> ClarityResult:
        """Local verification — runs full pipeline in-process."""
        
        print("[Clarity] Starting local verification...")
        
        # Call Claude via interceptor
        client = Anthropic(api_key=self.anthropic_api_key)
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
        
        print(f"[Clarity] Captured LLM exchange: {exchange.exchange_id}")
        
        # Extract context and run verification
        context = extract_verification_context(exchange)
        print(f"[Clarity] Extracted verification context ({len(context)} keys)")
        
        # Add API keys to context for agents
        context["anthropic_api_key"] = self.anthropic_api_key
        if self.tinyfish_api_key:
            context["tinyfish_api_key"] = self.tinyfish_api_key
        
        # Run verification pipeline via orchestrator
        print("[Clarity] Running verification pipeline (agents)...")
        trust_report = _run_coro_sync(
            run_verification_pipeline(
                exchange_id=exchange.exchange_id,
                context=context,
            )
        )
        
        print(f"[Clarity] Local verification complete. Score: {trust_report.overall_score:.1f}/100 ({trust_report.overall_risk.value})")
        
        return ClarityResult(content=exchange.response.content, trust_report=trust_report)

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
        except httpx.ConnectError:
            raise ValueError(
                f"Failed to connect to Clarity server at {self.clarity_api_url}. "
                "Is the server running? Try: python -m clarity.main"
            )
        except httpx.HTTPStatusError as e:
            raise Exception(f"Clarity server returned error: {e.response.status_code} - {e.response.text}")
        
        data = response.json()
        
        # Parse trust report
        trust_report_dict = data["trust_report"]
        
        # Handle datetime parsing
        if "timestamp" in trust_report_dict:
            trust_report_dict.pop("timestamp")
        
        trust_report = TrustReport(**trust_report_dict)
        
        print(f"[Clarity] Remote verification complete. Score: {trust_report.overall_score:.1f}/100")
        
        return ClarityResult(content=data["content"], trust_report=trust_report)


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
