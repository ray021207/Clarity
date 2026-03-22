"""Developer-facing SDK for Clarity verification (Person C)."""

from typing import Any, Optional
import httpx
from anthropic import Anthropic
import uuid

from clarity.proxy.interceptor import ClarityInterceptor
from clarity.proxy.metadata import extract_verification_context
from clarity.models import TrustReport, AgentVerdict, RiskLevel


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
    ):
        """
        Initialize ClarityClient.
        
        Args:
            clarity_api_url: URL of running Clarity server (for remote mode)
                            e.g., "http://localhost:8000"
            local_mode: If True, runs verification locally without server
            anthropic_api_key: Anthropic API key (required for local mode)
                              Falls back to ANTHROPIC_API_KEY env var if not provided
        
        Raises:
            ValueError: If local_mode=True but no API key provided
        """
        self.clarity_api_url = clarity_api_url
        self.local_mode = local_mode
        self.anthropic_api_key = anthropic_api_key
        
        if local_mode and not anthropic_api_key:
            # Try to get from environment
            import os
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.anthropic_api_key:
                raise ValueError(
                    "local_mode requires anthropic_api_key to be set "
                    "(either via parameter or ANTHROPIC_API_KEY env var)"
                )

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
        
        # For now, create mock report (Person B will implement real orchestrator)
        # This allows local mode to work during development
        hallucination = AgentVerdict(
            agent_name="hallucination_detector",
            score=75,
            risk_level=RiskLevel.MEDIUM,
            summary="No obvious hallucinations detected.",
            findings=["Facts appear grounded"],
            suggestions=["Verify any domain-specific claims independently"],
            details={},
        )
        
        reasoning = AgentVerdict(
            agent_name="reasoning_validator",
            score=80,
            risk_level=RiskLevel.LOW,
            summary="Reasoning is logical and consistent.",
            findings=["Clear logical flow"],
            suggestions=["Could benefit from step-by-step explanations"],
            details={},
        )
        
        confidence = AgentVerdict(
            agent_name="confidence_calibrator",
            score=70,
            risk_level=RiskLevel.MEDIUM,
            summary="Moderate consistency across samples.",
            findings=[f"Temperature {temperature} may affect variance"],
            suggestions=["Lower temperature for more consistent results"],
            details={},
        )
        
        context_quality = AgentVerdict(
            agent_name="context_analyzer",
            score=85,
            risk_level=RiskLevel.LOW,
            summary="Prompt is well-formed and effective.",
            findings=["Good system prompt" if system else "No system prompt"],
            suggestions=["Add system prompt for more controlled outputs"],
            details={},
        )
        
        # Calculate weighted overall score
        overall_score = (
            hallucination.score * 0.30 +
            reasoning.score * 0.25 +
            confidence.score * 0.25 +
            context_quality.score * 0.20
        )
        
        # Determine risk level
        if overall_score >= 80:
            overall_risk = RiskLevel.LOW
        elif overall_score >= 60:
            overall_risk = RiskLevel.MEDIUM
        elif overall_score >= 40:
            overall_risk = RiskLevel.HIGH
        else:
            overall_risk = RiskLevel.CRITICAL
        
        # Build warnings
        warnings = []
        if temperature > 0.8:
            warnings.append("High temperature (>0.8) may reduce consistency")
        if not system:
            warnings.append("No system prompt provided")
        if context_quality.score < 70:
            warnings.append("Prompt quality could be improved")
        
        trust_report = TrustReport(
            report_id=str(uuid.uuid4()),
            exchange_id=exchange.exchange_id,
            overall_score=overall_score,
            overall_risk=overall_risk,
            hallucination=hallucination,
            reasoning=reasoning,
            confidence=confidence,
            context_quality=context_quality,
            warnings=warnings,
            model_used=model,
            temperature=temperature,
            tokens_used=exchange.response.input_tokens + exchange.response.output_tokens,
        )
        
        print(f"[Clarity] Local verification complete. Score: {overall_score:.1f}/100 ({overall_risk.value})")
        
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
