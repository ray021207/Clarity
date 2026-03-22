"""Interceptor for Anthropic SDK calls — captures request/response metadata."""

import time
import uuid
from typing import Any, Optional
from datetime import datetime

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message

from clarity.models import (
    CapturedExchange,
    RequestMetadata,
    ResponseMetadata,
)


class ClarityInterceptor:
    """
    Wraps Anthropic SDK to capture metadata without changing user code.
    
    Usage:
        interceptor = ClarityInterceptor()
        exchange = interceptor.capture_sync_call(
            client=client,
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hi"}],
            system="You are helpful",
            temperature=0.7,
        )
        print(exchange.response.content)
    """

    @staticmethod
    def capture_sync_call(
        client: Anthropic,
        model: str,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> CapturedExchange:
        """Capture a synchronous Claude API call and return CapturedExchange."""
        
        exchange_id = str(uuid.uuid4())
        
        # Build request metadata
        request_meta = RequestMetadata(
            model=model,
            system_prompt=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools_provided=[t.get("name", "") for t in (tools or [])],
            tool_definitions=tools,
            total_context_chars=_count_context_chars(system, messages),
            message_count=len(messages),
        )
        
        # Make the API call with timing
        start_time = time.time()
        
        # Call Claude
        response: Message = client.messages.create(
            model=model,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or 4096,
            tools=tools,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Extract response metadata
        content = ""
        if response.content and len(response.content) > 0:
            # Get text content (first block that's text)
            for block in response.content:
                if hasattr(block, "text"):
                    content = block.text
                    break
        
        tool_calls = None
        if response.content:
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "name": getattr(block, "name", ""),
                        "id": getattr(block, "id", ""),
                        "input": getattr(block, "input", {}),
                    })
        
        response_meta = ResponseMetadata(
            content=content,
            stop_reason=response.stop_reason or "unknown",
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
        )
        
        # Create and return the exchange
        exchange = CapturedExchange(
            exchange_id=exchange_id,
            timestamp=datetime.utcnow(),
            request=request_meta,
            response=response_meta,
        )
        
        return exchange

    @staticmethod
    async def capture_async_call(
        client: AsyncAnthropic,
        model: str,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> CapturedExchange:
        """Capture an asynchronous Claude API call and return CapturedExchange."""
        
        exchange_id = str(uuid.uuid4())
        
        # Build request metadata
        request_meta = RequestMetadata(
            model=model,
            system_prompt=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools_provided=[t.get("name", "") for t in (tools or [])],
            tool_definitions=tools,
            total_context_chars=_count_context_chars(system, messages),
            message_count=len(messages),
        )
        
        # Make the API call with timing
        start_time = time.time()
        
        response: Message = await client.messages.create(
            model=model,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or 4096,
            tools=tools,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Extract response metadata
        content = ""
        if response.content and len(response.content) > 0:
            for block in response.content:
                if hasattr(block, "text"):
                    content = block.text
                    break
        
        tool_calls = None
        if response.content:
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "name": getattr(block, "name", ""),
                        "id": getattr(block, "id", ""),
                        "input": getattr(block, "input", {}),
                    })
        
        response_meta = ResponseMetadata(
            content=content,
            stop_reason=response.stop_reason or "unknown",
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
        )
        
        exchange = CapturedExchange(
            exchange_id=exchange_id,
            timestamp=datetime.utcnow(),
            request=request_meta,
            response=response_meta,
        )
        
        return exchange


def _count_context_chars(system: Optional[str], messages: list[dict[str, Any]]) -> int:
    """Count total characters in context (system + messages)."""
    total = 0
    if system:
        total += len(system)
    for msg in messages:
        if "content" in msg:
            content = msg["content"]
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        total += len(item["text"])
    return total
