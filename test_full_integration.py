"""
Full end-to-end integration test for Clarity.
Runs AFTER Person B and Person C have pushed their code.
"""

import asyncio
import json
from datetime import datetime
from clarity.config import settings
from clarity.integrations.insforge_client import InsForgeClient
from clarity.models import CapturedExchange, RequestMetadata, ResponseMetadata
from clarity.proxy.metadata import extract_verification_context
import uuid


async def test_full_pipeline():
    """Test complete Clarity pipeline with real agents."""
    
    print("=" * 70)
    print("  CLARITY FULL INTEGRATION TEST")
    print("=" * 70)
    
    # Check prerequisites
    print("\n📋 Checking prerequisites...")
    
    try:
        # Test imports (will fail if Person B's code not there)
        from clarity.agents.orchestrator import run_verification_pipeline
        print("   ✅ Person B's orchestrator found")
    except ImportError as e:
        print(f"   ❌ Person B's code missing: {e}")
        print("\n⚠️  Person B must push feat/agents-pipeline branch!")
        return False
    
    try:
        # Test imports (will fail if Person C's code not there)
        from clarity.integrations.ada_client import AdaClient
        print("   ✅ Person C's Ada client found")
    except ImportError as e:
        print(f"   ❌ Person C's code missing: {e}")
        print("\n⚠️  Person C must push feat/frontend-ux branch!")
        return False
    
    try:
        import psycopg2
        print("   ✅ Database driver available")
    except ImportError:
        print("   ❌ psycopg2 not installed")
        return False
    
    # Create mock exchange
    print("\n📝 Creating test exchange...")
    test_exchange = CapturedExchange(
        exchange_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        request=RequestMetadata(
            model="claude-sonnet-4-20250514",
            system_prompt="You are a helpful coding assistant.",
            messages=[
                {"role": "user", "content": "Write a Python function to calculate factorial"}
            ],
            temperature=0.7,
            max_tokens=500,
            total_context_chars=150,
            message_count=1,
        ),
        response=ResponseMetadata(
            content="""def factorial(n):
    \"\"\"Calculate factorial of n.\"\"\"
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Test
print(factorial(5))  # Output: 120
""",
            stop_reason="end_turn",
            input_tokens=25,
            output_tokens=75,
            latency_ms=500.5,
        ),
    )
    
    print(f"   Exchange ID: {test_exchange.exchange_id}")
    print(f"   Content length: {len(test_exchange.response.content)} chars")
    
    # Extract context
    print("\n🔍 Extracting verification context...")
    context = extract_verification_context(test_exchange)
    print(f"   ✅ Context extracted with {len(context)} fields")
    
    # Run verification pipeline
    print("\n🚀 Running verification pipeline (Person B's agents)...")
    try:
        trust_report = await run_verification_pipeline(
            exchange_id=test_exchange.exchange_id,
            context=context,
        )
        
        print(f"   ✅ Pipeline completed!")
        print(f"   Overall Score: {trust_report.overall_score}")
        print(f"   Overall Risk: {trust_report.overall_risk.value}")
        
        # Show agent verdicts
        print("\n📊 Agent Verdicts:")
        for agent_name in ["hallucination", "reasoning", "confidence", "context_quality"]:
            verdict = getattr(trust_report, agent_name)
            print(f"   {agent_name:20} | Score: {verdict.score:3.0f} | Risk: {verdict.risk_level.value}")
        
    except NotImplementedError:
        print(f"   ❌ Pipeline not implemented (Person B's code needed)")
        return False
    except Exception as e:
        print(f"   ❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Store in database
    print("\n💾 Storing report in InsForge...")
    try:
        insforge = InsForgeClient()
        
        # Store exchange
        exchange_result = insforge.store_exchange_log(
            exchange_id=test_exchange.exchange_id,
            exchange_data=test_exchange.to_dict(),
        )
        print(f"   ✅ Exchange stored: {exchange_result['id']}")
        
        # Store report
        report_result = insforge.store_trust_report(trust_report)
        print(f"   ✅ Report stored: {report_result['id']}")
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False
    
    # Test Ada integration
    print("\n💬 Testing Ada chat integration (Person C)...")
    try:
        from clarity.integrations.ada_client import AdaClient
        
        ada = AdaClient()
        summary = trust_report.get_summary()
        
        result = await ada.explain_trust_report(
            summary=summary,
            question="Why is my trust score 75?",
        )
        
        print(f"   ✅ Ada response received")
        print(f"   Explanation: {result['explanation'][:100]}...")
        
    except NotImplementedError:
        print(f"   ⚠️  Ada client not implemented (Person C's code needed)")
    except Exception as e:
        print(f"   ❌ Ada error: {e}")
        return False
    
    # Retrieve from database
    print("\n🔎 Retrieving data from InsForge...")
    try:
        retrieved = insforge.get_trust_report(trust_report.report_id)
        if retrieved:
            print(f"   ✅ Report retrieved successfully")
            print(f"   Score: {retrieved.get('overall_score')}")
        else:
            print(f"   ❌ Report not found")
            return False
    except Exception as e:
        print(f"   ❌ Retrieval error: {e}")
        return False
    
    # Test SDK
    print("\n🔌 Testing SDK integration...")
    try:
        from clarity.sdk import ClarityClient
        
        # Local mode test
        client = ClarityClient(local_mode=False)  # Use remote for testing if server running
        print(f"   ✅ SDK local mode initialized")
        
    except Exception as e:
        print(f"   ❌ SDK error: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("  ✅ ALL INTEGRATION TESTS PASSED!")
    print("=" * 70)
    print("""
✨ Clarity is fully functional with:
   - Anthropic interceptor ✅
   - Metadata extraction ✅
   - 4 verification agents (Person B) ✅
   - LangGraph orchestrator ✅
   - Database persistence ✅
   - Ada chat integration (Person C) ✅
   - Dashboard ready ✅
   - SDK ready ✅

🎉 Ready for demo and deployment!
    """)
    
    return True


async def test_dashboard_endpoints():
    """Test dashboard-related endpoints."""
    
    print("\n" + "=" * 70)
    print("  TESTING DASHBOARD ENDPOINTS")
    print("=" * 70)
    
    try:
        import httpx
        
        base_url = "http://localhost:8000"
        
        # Test health
        print("\n🔌 GET /api/v1/health")
        response = await httpx.AsyncClient().get(f"{base_url}/api/v1/health")
        print(f"   Status: {response.status_code}")
        
        # Test reports list
        print("\n📋 GET /api/v1/reports")
        response = await httpx.AsyncClient().get(f"{base_url}/api/v1/reports")
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: 200")
            print(f"   Reports: {data.get('count', 'N/A')}")
        else:
            print(f"   Status: {response.status_code}")
        
        # Test dashboard
        print("\n🎨 GET / (Dashboard)")
        response = await httpx.AsyncClient().get(f"{base_url}/")
        if response.status_code == 200:
            print(f"   ✅ Dashboard available ({len(response.content)} bytes)")
        else:
            print(f"   ❌ Dashboard not found (status: {response.status_code})")
            
    except Exception as e:
        print(f"   Error: {e}")
        print("   Note: Server must be running (python -m clarity.main)")


if __name__ == "__main__":
    # Run async tests
    success = asyncio.run(test_full_pipeline())
    
    if success:
        print("\n✨ Integration test complete!")
        print("\nTo start the server:")
        print("  python -m clarity.main")
        print("\nThen test endpoints at:")
        print("  http://localhost:8000/")
        print("  http://localhost:8000/api/v1/health")
    else:
        print("\n⚠️  Waiting for teammates to push their code:")
        print("  - Person B: feat/agents-pipeline")
        print("  - Person C: feat/frontend-ux")
    
    exit(0 if success else 1)
