"""Developer-facing SDK for Clarity (Person C will enhance)."""

from typing import Any, Optional
import httpx
from anthropic import Anthropic

from clarity.proxy.interceptor import ClarityInterceptor
from clarity.proxy.metadata import extract_verification_context
from clarity.agents.orchestrator import run_verification_pipeline
from clarity.models import TrustReport


class ClarityResult:
    """Result object returned to SDK users."""

    def __init__(self, content: str, trust_report: TrustReport):
        self.content = content
        self.trust_report = trust_report

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
    ):
        """
        Initialize ClarityClient.
        
        Args:
            clarity_api_url: URL of running Clarity server (for remote mode)
            local_mode: If True, runs verification locally without server
            anthropic_api_key: Anthropic API key (for local mode)
        """
        self.clarity_api_url = clarity_api_url
        self.local_mode = local_mode
        self.anthropic_api_key = anthropic_api_key

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
        Verify LLM output and get trust report.
        
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
        
        # Extract context and run verification
        context = extract_verification_context(exchange)
        
        # Run orchestrator (Person B will implement)
        # For now, create mock report
        from clarity.models import AgentVerdict, RiskLevel
        import uuid
        
        hallucination = AgentVerdict(
            agent_name="hallucination_detector",
            score=75,
            risk_level=RiskLevel.MEDIUM,
            summary="No obvious hallucinations.",
            findings=[],
            suggestions=[],
            details={},
        )
        
        reasoning = AgentVerdict(
            agent_name="reasoning_validator",
            score=80,
            risk_level=RiskLevel.LOW,
            summary="Reasoning is sound.",
            findings=[],
            suggestions=[],
            details={},
        )
        
        confidence = AgentVerdict(
            agent_name="confidence_calibrator",
            score=70,
            risk_level=RiskLevel.MEDIUM,
            summary="Moderate consistency.",
            findings=[],
            suggestions=[],
            details={},
        )
        
        context_quality = AgentVerdict(
            agent_name="context_analyzer",
            score=85,
            risk_level=RiskLevel.LOW,
            summary="Good prompt quality.",
            findings=[],
            suggestions=[],
            details={},
        )
        
        overall_score = (
            hallucination.score * 0.30 +
            reasoning.score * 0.25 +
            confidence.score * 0.25 +
            context_quality.score * 0.20
        )
        
        trust_report = TrustReport(
            report_id=str(uuid.uuid4()),
            exchange_id=exchange.exchange_id,
            overall_score=overall_score,
            overall_risk=RiskLevel.LOW if overall_score > 80 else RiskLevel.MEDIUM,
            hallucination=hallucination,
            reasoning=reasoning,
            confidence=confidence,
            context_quality=context_quality,
            warnings=[],
            model_used=model,
            temperature=temperature,
            tokens_used=exchange.response.input_tokens + exchange.response.output_tokens,
        )
        
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
        from clarity.models import TrustReport
        trust_report_dict = data["trust_report"]
        trust_report = TrustReport(**trust_report_dict)
        
        return ClarityResult(content=data["content"], trust_report=trust_report)
