"""Extract verification context from captured exchanges."""

from typing import Any

from clarity.models import CapturedExchange


def extract_verification_context(exchange: CapturedExchange) -> dict[str, Any]:
    """
    Extract verification context dict from a captured exchange.
    
    This dict is consumed by all 4 agents via LangGraph state.
    All fields are derived from the captured request/response.
    """
    
    req = exchange.request
    resp = exchange.response
    
    # Calculate derived signals
    context_window = 200_000  # Claude context window (conservative estimate)
    context_saturation = (req.total_context_chars / context_window) * 100 if context_window > 0 else 0
    
    # Temperature risk assessment
    temp_risk = "medium"
    if req.temperature < 0.3:
        temp_risk = "low"
    elif req.temperature > 1.5:
        temp_risk = "high"
    
    # Check if tools were available but not used
    tools_available_but_unused = (
        len(req.tools_provided) > 0 and
        (resp.tool_calls is None or len(resp.tool_calls) == 0)
    )
    
    # Is output truncated?
    is_truncated = resp.stop_reason in ["max_tokens", "length"]
    
    # Output length metrics
    output_length = len(resp.content)
    output_words = len(resp.content.split())
    output_lines = len(resp.content.split("\n"))
    
    # Message patterns
    has_system_prompt = req.system_prompt is not None and len(req.system_prompt) > 0
    system_prompt_length = len(req.system_prompt) if req.system_prompt else 0
    
    # Lost-in-the-middle effect (>10 messages increases middle-token amnesia)
    middle_message_risk = "high" if req.message_count > 10 else "low"
    
    return {
        # Exchange ID and metadata
        "exchange_id": exchange.exchange_id,
        "timestamp": exchange.timestamp.isoformat(),
        "model": req.model,
        
        # Request parameters
        "system_prompt": req.system_prompt,
        "system_prompt_length": system_prompt_length,
        "has_system_prompt": has_system_prompt,
        "temperature": req.temperature,
        "temp_risk": temp_risk,
        "max_tokens": req.max_tokens,
        "messages": req.messages,
        "message_count": req.message_count,
        "total_context_chars": req.total_context_chars,
        "context_saturation_percent": context_saturation,
        
        # Tool information
        "tools_provided": req.tools_provided,
        "tool_definitions": req.tool_definitions,
        "tools_available_but_unused": tools_available_but_unused,
        "num_tools": len(req.tools_provided),
        
        # Response information
        "response_content": resp.content,
        "stop_reason": resp.stop_reason,
        "is_truncated": is_truncated,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "total_tokens": resp.input_tokens + resp.output_tokens,
        "latency_ms": resp.latency_ms,
        "tool_calls": resp.tool_calls,
        
        # Output metrics
        "output_length": output_length,
        "output_words": output_words,
        "output_lines": output_lines,
        
        # Risk assessments
        "middle_message_risk": middle_message_risk,
        
        # Flags for agents
        "has_error_indicators": _check_error_indicators(resp.content),
        "has_reasoning": _check_reasoning_present(resp.content),
    }


def _check_error_indicators(content: str) -> bool:
    """Check if output has error-like indicators."""
    error_words = ["error", "exception", "traceback", "failed", "invalid"]
    content_lower = content.lower()
    return any(word in content_lower for word in error_words)


def _check_reasoning_present(content: str) -> bool:
    """Check if output contains reasoning/explanation."""
    reasoning_markers = ["because", "therefore", "thus", "so ", "reasoning:", "step"]
    content_lower = content.lower()
    return any(marker in content_lower for marker in reasoning_markers)
