"""Mock test of ClarityInterceptor without requiring real API calls."""

from datetime import datetime
from clarity.models import (
    CapturedExchange,
    RequestMetadata,
    ResponseMetadata,
)
from clarity.proxy.metadata import extract_verification_context
import json


def test_interceptor_mock():
    """Test interceptor data structures with mock data."""
    
    print("=" * 70)
    print("  Testing ClarityInterceptor (Mock Data)")
    print("=" * 70)
    
    # Create a mock captured exchange
    mock_request = RequestMetadata(
        model="claude-sonnet-4-20250514",
        system_prompt="You are a helpful coding assistant.",
        messages=[
            {"role": "user", "content": "Write a factorial function in Python"}
        ],
        temperature=0.7,
        max_tokens=500,
        tools_provided=[],
        tool_definitions=None,
        total_context_chars=120,
        message_count=1,
    )
    
    mock_response = ResponseMetadata(
        content="""def factorial(n):
    \"\"\"Calculate factorial of n.\"\"\"
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Test
print(factorial(5))  # Output: 120
""",
        stop_reason="end_turn",
        input_tokens=45,
        output_tokens=87,
        tool_calls=None,
        latency_ms=1250.5,
    )
    
    mock_exchange = CapturedExchange(
        exchange_id="test-exchange-001",
        timestamp=datetime.utcnow(),
        request=mock_request,
        response=mock_response,
    )
    
    print("\n✅ Mock exchange created!")
    print(f"   Exchange ID: {mock_exchange.exchange_id}")
    print(f"   Model: {mock_exchange.request.model}")
    print(f"   Request Tokens: {mock_exchange.response.input_tokens}")
    print(f"   Response Tokens: {mock_exchange.response.output_tokens}")
    print(f"   Latency: {mock_exchange.response.latency_ms}ms")
    
    # Extract context
    print("\n🔍 Extracting verification context...")
    context = extract_verification_context(mock_exchange)
    
    print(f"\n✅ Context extracted successfully!")
    print(f"\n📊 Extracted Context Fields:")
    
    important_fields = [
        "exchange_id",
        "model",
        "temperature",
        "temp_risk",
        "has_system_prompt",
        "system_prompt_length",
        "message_count",
        "context_saturation_percent",
        "output_length",
        "output_words",
        "stop_reason",
        "is_truncated",
        "total_tokens",
        "tools_provided",
        "tools_available_but_unused",
        "middle_message_risk",
    ]
    
    for field in important_fields:
        value = context.get(field, "N/A")
        print(f"   {field}: {value}")
    
    # Verify structure
    print("\n🔎 Validating context structure...")
    required_keys = {
        "exchange_id", "model", "temperature", "messages",
        "response_content", "stop_reason", "input_tokens", "output_tokens",
        "context_saturation_percent", "total_tokens", "latency_ms",
    }
    
    missing_keys = required_keys - set(context.keys())
    if missing_keys:
        print(f"   ❌ Missing keys: {missing_keys}")
        return False
    
    print(f"   ✅ All {len(required_keys)} required keys present")
    
    # Verify serialization
    print("\n💾 Testing JSON serialization...")
    try:
        exchange_json = json.dumps(mock_exchange.to_dict())
        context_json = json.dumps(context)
        print(f"   ✅ Exchange serializable: {len(exchange_json)} bytes")
        print(f"   ✅ Context serializable: {len(context_json)} bytes")
    except Exception as e:
        print(f"   ❌ Serialization failed: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("  ✅ ALL MOCK TESTS PASSED!")
    print("=" * 70)
    print("\n✨ Code structure verified. Ready to:")
    print("  1. Add credits to Anthropic and test with real API")
    print("  2. Test database persistence (when InsForge ready)")
    print("  3. Test full API server")
    print("\n💡 Next: Run 'python -m clarity.main' to start the server")
    
    return True


if __name__ == "__main__":
    success = test_interceptor_mock()
    exit(0 if success else 1)
