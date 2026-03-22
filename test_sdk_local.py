#!/usr/bin/env python3
"""
Test script for Clarity SDK in local mode.

This tests the SDK without needing a running server.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from clarity.sdk import ClarityClient


def test_local_mode():
    """Test SDK in local mode."""
    
    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set. Please set it in .env or environment.")
        return False
    
    print("🚀 Testing Clarity SDK in LOCAL mode...\n")
    
    # Initialize client
    try:
        client = ClarityClient(local_mode=True, anthropic_api_key=api_key)
        print("✅ Client initialized in local mode")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False
    
    # Test 1: Simple factual question
    print("\n--- TEST 1: Factual Question ---")
    try:
        result = client.verify(
            messages=[{"role": "user", "content": "What year was Python released?"}],
            system="You are a helpful coding assistant.",
            temperature=0.2,
        )
        print(f"✅ Verification complete")
        print(f"   Score: {result.score:.1f}/100")
        print(f"   Risk: {result.risk}")
        print(f"   Content preview: {result.content[:100]}...")
        print(f"   Warnings: {len(result.warnings)}")
        if result.warnings:
            for w in result.warnings:
                print(f"      - {w}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Code generation
    print("\n--- TEST 2: Code Generation ---")
    try:
        result = client.verify(
            messages=[{"role": "user", "content": "Write a simple Python function to add two numbers."}],
            system="You are an expert Python developer.",
            temperature=0.5,
        )
        print(f"✅ Verification complete")
        print(f"   Score: {result.score:.1f}/100")
        print(f"   Risk: {result.risk}")
        print(f"   Content preview: {result.content[:100]}...")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    # Test 3: High temperature (creative)
    print("\n--- TEST 3: Creative Output (High Temp) ---")
    try:
        result = client.verify(
            messages=[{"role": "user", "content": "Write a short creative story about AI."}],
            temperature=0.9,
        )
        print(f"✅ Verification complete")
        print(f"   Score: {result.score:.1f}/100")
        print(f"   Risk: {result.risk}")
        print(f"   Content preview: {result.content[:100]}...")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    print("\n✅ All local mode tests passed!")
    return True


def test_result_properties():
    """Test ClarityResult properties."""
    print("\n--- TEST: ClarityResult Properties ---")
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⏭️  Skipping (no API key)")
        return True
    
    try:
        client = ClarityClient(local_mode=True, anthropic_api_key=api_key)
        result = client.verify(
            messages=[{"role": "user", "content": "Hello, how are you?"}],
        )
        
        # Test all properties
        print(f"✅ content: {len(result.content)} chars")
        print(f"✅ score: {result.score}")
        print(f"✅ risk: {result.risk}")
        print(f"✅ warnings: {len(result.warnings)} items")
        print(f"✅ summary keys: {list(result.summary.keys())}")
        print(f"✅ repr: {repr(result)}")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_local_mode() and test_result_properties()
    sys.exit(0 if success else 1)
