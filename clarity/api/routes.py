"""API endpoints for Clarity verification service."""

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from clarity.proxy.interceptor import ClarityInterceptor
from clarity.proxy.metadata import extract_verification_context
from clarity.integrations.insforge_client import InsForgeClient
from clarity.integrations.ada_client import AdaClient
from clarity.models import TrustReport, CapturedExchange
from clarity.config import settings

router = APIRouter()

# Global services
insforge_client = InsForgeClient()
ada_client = AdaClient()


class VerifyRequest(BaseModel):
    """Request body for /verify endpoint."""
    messages: list[dict[str, Any]]
    system: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools: list[dict[str, Any]] = []


class VerifyResponse(BaseModel):
    """Response body for /verify endpoint."""
    content: str
    trust_report: dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@router.post("/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest, background_tasks: BackgroundTasks):
    """
    Main verification endpoint.
    
    Send messages → get LLM output + trust report.
    
    Flow:
    1. Call Claude via interceptor (captures CapturedExchange)
    2. Extract verification context
    3. Run verification pipeline (Person B's orchestrator)
    4. Generate trust report
    5. Persist to InsForge (async)
    6. Return content + report to user
    """
    try:
        # Step 1: Call Claude and capture exchange
        from anthropic import Anthropic
        anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
        
        interceptor = ClarityInterceptor()
        exchange = interceptor.capture_sync_call(
            client=anthropic_client,
            model=request.model,
            messages=request.messages,
            system=request.system,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=request.tools if request.tools else None,
        )
        
        # Step 2: Extract verification context
        context = extract_verification_context(exchange)
        
        # Step 3: Run verification pipeline (currently a stub, Person B implements)
        # For now, return mock report to let API route tests work
        trust_report = _create_mock_trust_report(exchange, context)
        
        # Step 4: Persist to InsForge (async in background)
        background_tasks.add_task(
            _persist_exchange_and_report,
            exchange=exchange,
            trust_report=trust_report,
        )
        
        # Step 5: Return to user
        return VerifyResponse(
            content=exchange.response.content,
            trust_report=trust_report.to_dict(),
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/reports")
async def list_reports(limit: int = 10, offset: int = 0):
    """List recent trust reports from InsForge."""
    try:
        reports = insforge_client.list_trust_reports(limit=limit, offset=offset)
        return {"reports": reports, "count": len(reports)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Fetch a single trust report by ID."""
    try:
        report = insforge_client.get_trust_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve report: {str(e)}")


class ExplainRequest(BaseModel):
    """Request body for /explain endpoint."""
    report_summary: dict[str, Any]
    question: str


class ExplainResponse(BaseModel):
    """Response for /explain endpoint."""
    explanation: str
    suggested_questions: list[str] = []


@router.post("/explain", response_model=ExplainResponse)
async def explain_report(request: ExplainRequest):
    """
    Explain a trust report in plain language using Ada (Person C).
    
    Falls back to local explanation if Ada is unavailable.
    """
    try:
        result = await ada_client.explain_trust_report(
            summary=request.report_summary,
            question=request.question,
        )
        return ExplainResponse(
            explanation=result.get("explanation", ""),
            suggested_questions=result.get("suggested_questions", []),
        )
    except (NotImplementedError, Exception):
        # Fall back to local explanation
        return ExplainResponse(
            explanation="Ada explainer not configured yet. Please configure ADA_API_URL and ADA_API_KEY in .env",
            suggested_questions=[
                "Why is my score 75?",
                "What do the warnings mean?",
                "Should I trust this output?",
            ],
        )


async def _persist_exchange_and_report(exchange: CapturedExchange, trust_report: TrustReport):
    """Background task to persist exchange and report to InsForge."""
    try:
        insforge_client.store_exchange_log(
            exchange_id=exchange.exchange_id,
            exchange_data=exchange.to_dict(),
        )
        insforge_client.store_trust_report(trust_report)
    except Exception as e:
        print(f"Failed to persist to InsForge: {e}")


def _create_mock_trust_report(exchange: CapturedExchange, context: dict[str, Any]) -> TrustReport:
    """
    Create a mock trust report for testing (Person B will replace with real orchestrator).
    """
    from clarity.models import AgentVerdict, RiskLevel
    import uuid
    
    # Create mock verdicts
    hallucination = AgentVerdict(
        agent_name="hallucination_detector",
        score=75,
        risk_level=RiskLevel.MEDIUM,
        summary="No obvious hallucinations detected.",
        findings=["Output appears factually grounded"],
        suggestions=["Consider verifying critical claims"],
        details={},
    )
    
    reasoning = AgentVerdict(
        agent_name="reasoning_validator",
        score=80,
        risk_level=RiskLevel.LOW,
        summary="Reasoning is logically sound.",
        findings=["Logic flow is clear"],
        suggestions=[],
        details={},
    )
    
    confidence = AgentVerdict(
        agent_name="confidence_calibrator",
        score=70,
        risk_level=RiskLevel.MEDIUM,
        summary="Output shows moderate consistency.",
        findings=["Temperature 0.7 produces some variance"],
        suggestions=["Lower temperature for deterministic outputs"],
        details={},
    )
    
    context_quality = AgentVerdict(
        agent_name="context_analyzer",
        score=85,
        risk_level=RiskLevel.LOW,
        summary="Good prompt quality and context usage.",
        findings=["System prompt present", "Appropriate temperature"],
        suggestions=[],
        details={},
    )
    
    # Calculate weighted average
    overall_score = (
        hallucination.score * 0.30 +
        reasoning.score * 0.25 +
        confidence.score * 0.25 +
        context_quality.score * 0.20
    )
    
    overall_risk = RiskLevel.LOW if overall_score > 80 else RiskLevel.MEDIUM
    
    return TrustReport(
        report_id=str(uuid.uuid4()),
        exchange_id=exchange.exchange_id,
        overall_score=overall_score,
        overall_risk=overall_risk,
        hallucination=hallucination,
        reasoning=reasoning,
        confidence=confidence,
        context_quality=context_quality,
        warnings=["Mock report—use real orchestrator"],
        model_used=exchange.request.model,
        temperature=exchange.request.temperature,
        tokens_used=exchange.response.input_tokens + exchange.response.output_tokens,
    )
