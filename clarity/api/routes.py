"""API endpoints for Clarity verification service."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from clarity.integrations.insforge_client import InsForgeClient
from clarity.integrations.ada_client import AdaClient
from clarity.models import TrustReport
from clarity.sdk import ClarityClient
from clarity.config import settings

router = APIRouter()

# Global services
insforge_client = InsForgeClient()
ada_client = AdaClient()


class VerifyRequest(BaseModel):
    """Request body for /verify endpoint."""
    messages: list[dict[str, Any]]
    system: Optional[str] = None
    model: str = "claude-sonnet-4-6"
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
    1. Call Claude model via local SDK mode
    2. Extract verification context
    3. Run verification pipeline (LangGraph orchestrator)
    4. Persist trust report to InsForge (async)
    5. Return content + report to user
    """
    try:
        client = ClarityClient(
            local_mode=True,
            anthropic_api_key=settings.anthropic_api_key,
            tinyfish_api_key=settings.tinyfish_api_key,
        )
        result = client.verify(
            messages=request.messages,
            system=request.system,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=request.tools,
        )

        # Persist to InsForge in background (best-effort).
        background_tasks.add_task(
            _persist_trust_report,
            trust_report=result.trust_report,
        )

        return VerifyResponse(
            content=result.content,
            trust_report=result.trust_report.to_dict(),
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


async def _persist_trust_report(trust_report: TrustReport):
    """Background task to persist trust report to InsForge."""
    try:
        insforge_client.store_trust_report(trust_report)
    except Exception as e:
        print(f"Failed to persist to InsForge: {e}")
