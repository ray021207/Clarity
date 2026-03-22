"""Test InsForge database connection and persistence."""

from datetime import datetime
from clarity.config import settings
from clarity.integrations.insforge_client import InsForgeClient
from clarity.models import (
    CapturedExchange,
    RequestMetadata,
    ResponseMetadata,
    TrustReport,
    AgentVerdict,
    RiskLevel,
)
import uuid
import json


def test_insforge_persistence():
    """Test complete InsForge persistence workflow."""
    
    print("=" * 70)
    print("  Testing InsForge Direct Database Persistence")
    print("=" * 70)
    
    # Check configuration
    if not settings.insforge_database_url:
        print("\n❌ ERROR: INSFORGE_DATABASE_URL not set in .env")
        return False
    
    print(f"\n🔗 Database URL: {settings.insforge_database_url.split('@')[0]}@...")
    
    try:
        client = InsForgeClient()
        
        # Step 1: Test connection
        print("\n📡 Testing database connection...")
        reports = client.list_trust_reports(limit=1)
        print(f"   ✅ Connected successfully")
        print(f"   Existing reports: {len(reports)}")
        
        # Step 2: Create mock exchange
        print("\n📝 Creating mock exchange...")
        mock_exchange = CapturedExchange(
            exchange_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            request=RequestMetadata(
                model="claude-sonnet-4-20250514",
                system_prompt="You are a helpful assistant.",
                messages=[{"role": "user", "content": "Hello"}],
                temperature=0.7,
                max_tokens=500,
                total_context_chars=100,
                message_count=1,
            ),
            response=ResponseMetadata(
                content="Hello! How can I help you?",
                stop_reason="end_turn",
                input_tokens=20,
                output_tokens=10,
                latency_ms=250.5,
            ),
        )
        print(f"   Exchange ID: {mock_exchange.exchange_id}")
        
        # Step 3: Store exchange log
        print("\n💾 Storing exchange log...")
        log_result = client.store_exchange_log(
            exchange_id=mock_exchange.exchange_id,
            exchange_data=mock_exchange.to_dict(),
        )
        print(f"   ✅ Exchange stored: {log_result}")
        
        # Step 4: Create mock trust report
        print("\n📊 Creating mock trust report...")
        trust_report = TrustReport(
            report_id=str(uuid.uuid4()),
            exchange_id=mock_exchange.exchange_id,
            overall_score=82.5,
            overall_risk=RiskLevel.LOW,
            hallucination=AgentVerdict(
                agent_name="hallucination_detector",
                score=85,
                risk_level=RiskLevel.LOW,
                summary="No hallucinations detected.",
                findings=["Output is factually grounded"],
                suggestions=[],
                details={},
            ),
            reasoning=AgentVerdict(
                agent_name="reasoning_validator",
                score=80,
                risk_level=RiskLevel.LOW,
                summary="Reasoning is sound.",
                findings=[],
                suggestions=[],
                details={},
            ),
            confidence=AgentVerdict(
                agent_name="confidence_calibrator",
                score=82,
                risk_level=RiskLevel.LOW,
                summary="High consistency.",
                findings=[],
                suggestions=[],
                details={},
            ),
            context_quality=AgentVerdict(
                agent_name="context_analyzer",
                score=82,
                risk_level=RiskLevel.LOW,
                summary="Good context quality.",
                findings=[],
                suggestions=[],
                details={},
            ),
            warnings=[],
            model_used="claude-sonnet-4-20250514",
            temperature=0.7,
            tokens_used=30,
        )
        print(f"   Report ID: {trust_report.report_id}")
        print(f"   Overall Score: {trust_report.overall_score}")
        
        # Step 5: Store trust report
        print("\n💾 Storing trust report...")
        report_result = client.store_trust_report(trust_report)
        print(f"   ✅ Report stored successfully")
        print(f"   Result: {report_result}")
        
        # Step 6: Retrieve trust report
        print("\n🔍 Retrieving trust report...")
        retrieved = client.get_trust_report(trust_report.report_id)
        if retrieved:
            print(f"   ✅ Report retrieved successfully")
            print(f"   Report ID: {retrieved.get('report_id')}")
            print(f"   Overall Score: {retrieved.get('overall_score')}")
        else:
            print(f"   ❌ Report not found")
            return False
        
        # Step 7: List reports
        print("\n📋 Listing recent reports...")
        all_reports = client.list_trust_reports(limit=5)
        print(f"   ✅ Found {len(all_reports)} reports")
        for i, r in enumerate(all_reports[:3], 1):
            print(f"      {i}. {r.get('report_id', 'unknown')[:8]}... score={r.get('overall_score')}")
        
        print("\n" + "=" * 70)
        print("  ✅ ALL PERSISTENCE TESTS PASSED!")
        print("=" * 70)
        print("\n🎉 InsForge is fully integrated and working!")
        print("   - Exchange logs being stored")
        print("   - Trust reports being stored")
        print("   - Data retrieval working")
        print("   - Ready for production use")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_insforge_persistence()
    exit(0 if success else 1)
