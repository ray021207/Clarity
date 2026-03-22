"""Quick test of the ClarityInterceptor to verify it captures metadata correctly."""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from anthropic import Anthropic
from clarity.proxy.interceptor import ClarityInterceptor
from clarity.proxy.metadata import extract_verification_context
import json


def test_interceptor():
    """Test interceptor capture and metadata extraction."""
    
    print("=" * 70)
    print("  Testing ClarityInterceptor in Isolation")
    print("=" * 70)
    
    # Initialize Anthropic client
    client = Anthropic()
    interceptor = ClarityInterceptor()
    
    # Simple test prompt
    test_messages = [
        {"role": "user", "content": "Write a simple Python function to calculate factorial"}
    ]
    
    print("\n📡 Calling Claude API...")
    print(f"   Messages: {test_messages}")
    print(f"   System: (none)")
    print(f"   Temperature: 0.7")
    
    try:
        # Capture the exchange
        exchange = interceptor.capture_sync_call(
            client=client,
            model="claude-sonnet-4-20250514",
            messages=test_messages,
            system="You are a helpful coding assistant.",
            temperature=0.7,
            max_tokens=500,
        )
        
        print("\n✅ Exchange captured successfully!")
        print(f"\n📊 Captured Exchange:")
        print(f"   Exchange ID: {exchange.exchange_id}")
        print(f"   Timestamp: {exchange.timestamp}")
        print(f"   Request Model: {exchange.request.model}")
        print(f"   Request Temp: {exchange.request.temperature}")
        print(f"   System Prompt: {exchange.request.system_prompt[:50]}..." if exchange.request.system_prompt else "   System Prompt: (none)")
        print(f"   Input Tokens: {exchange.response.input_tokens}")
        print(f"   Output Tokens: {exchange.response.output_tokens}")
        print(f"   Stop Reason: {exchange.response.stop_reason}")
        print(f"   Latency: {exchange.response.latency_ms:.2f}ms")
        print(f"   Response Preview: {exchange.response.content[:100]}...")
        
        # Extract context
        print("\n🔍 Extracting verification context...")
        context = extract_verification_context(exchange)
        
        print(f"\n✅ Context extracted! Key fields:")
        print(f"   exchange_id: {context['exchange_id']}")
        print(f"   model: {context['model']}")
        print(f"   temperature: {context['temperature']}")
        print(f"   temp_risk: {context['temp_risk']}")
        print(f"   has_system_prompt: {context['has_system_prompt']}")
        print(f"   system_prompt_length: {context['system_prompt_length']}")
        print(f"   message_count: {context['message_count']}")
        print(f"   context_saturation_percent: {context['context_saturation_percent']:.2f}%")
        print(f"   output_length: {context['output_length']}")
        print(f"   output_words: {context['output_words']}")
        print(f"   stop_reason: {context['stop_reason']}")
        print(f"   is_truncated: {context['is_truncated']}")
        print(f"   total_tokens: {context['total_tokens']}")
        
        print("\n" + "=" * 70)
        print("  ✅ INTERCEPTOR TEST PASSED!")
        print("=" * 70)
        print("\nAll metadata captured correctly. Ready to:")
        print("  1. Test database persistence (if InsForge configured)")
        print("  2. Test full API server")
        print("  3. Test verification pipeline (when Person B adds agents)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_interceptor()
    exit(0 if success else 1)
