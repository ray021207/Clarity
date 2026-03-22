"""Test InsForge connection and database setup."""

import json
from clarity.config import settings
from clarity.integrations.insforge_client import InsForgeClient


def test_insforge_connection():
    """Test that we can connect to InsForge."""
    
    print("=" * 70)
    print("  Testing InsForge Connection")
    print("=" * 70)
    
    print(f"\n🔗 InsForge URL: {settings.insforge_url}")
    print(f"🔑 API Key: {settings.insforge_api_key[:20]}..." if settings.insforge_api_key else "❌ No API key")
    
    if not settings.insforge_api_key:
        print("\n❌ ERROR: INSFORGE_API_KEY not set in .env")
        return False
    
    if not settings.insforge_url:
        print("\n❌ ERROR: INSFORGE_URL not set in .env")
        return False
    
    try:
        client = InsForgeClient()
        
        # Try to list reports (even if empty, it should connect)
        print("\n📡 Testing API connection...")
        reports = client.list_trust_reports(limit=1)
        
        print(f"✅ Connection successful!")
        print(f"   Response type: {type(reports)}")
        print(f"   Reports found: {len(reports)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n⚠️  Troubleshooting:")
        print("   - Check INSFORGE_URL is correct (should end with .insforge.dev)")
        print("   - Check INSFORGE_API_KEY is valid")
        print("   - Make sure InsForge project exists")
        print("   - Check tables exist in your project")
        return False


def setup_database():
    """Print SQL to create tables."""
    
    print("\n" + "=" * 70)
    print("  Database Schema Setup Instructions")
    print("=" * 70)
    
    sql_trust_reports = """
CREATE TABLE IF NOT EXISTS trust_reports (
    id BIGSERIAL PRIMARY KEY,
    report_id TEXT UNIQUE NOT NULL,
    exchange_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    overall_score FLOAT NOT NULL,
    overall_risk TEXT NOT NULL,
    verified_report JSONB NOT NULL,
    model_used TEXT,
    temperature FLOAT,
    tokens_used INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trust_reports_report_id ON trust_reports(report_id);
CREATE INDEX IF NOT EXISTS idx_trust_reports_exchange_id ON trust_reports(exchange_id);
    """

    sql_exchange_logs = """
CREATE TABLE IF NOT EXISTS exchange_logs (
    id BIGSERIAL PRIMARY KEY,
    exchange_id TEXT UNIQUE NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    exchange_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exchange_logs_exchange_id ON exchange_logs(exchange_id);
    """
    
    print("\n📋 SQL for trust_reports table:")
    print(sql_trust_reports)
    
    print("\n📋 SQL for exchange_logs table:")
    print(sql_exchange_logs)
    
    print("\n" + "=" * 70)
    print("  HOW TO CREATE TABLES IN INSFORGE")
    print("=" * 70)
    print("""
1. Go to your InsForge project dashboard
2. Click on "SQL Editor" or "Console"
3. Copy and paste the SQL above into the editor
4. Execute the queries
5. Verify tables were created

Alternatively, you can use the PostgREST API:
    curl -X POST \\
      -H "apikey: YOUR_API_KEY" \\
      -H "Authorization: Bearer YOUR_API_KEY" \\
      -H "Content-Type: application/json" \\
      https://your-project.insforge.dev/rest/v1/trust_reports \\
      -d '{"report_id":"test","exchange_id":"test","overall_score":75,"overall_risk":"low","verified_report":{},"model_used":"test"}'
    """)


if __name__ == "__main__":
    # Test connection
    connected = test_insforge_connection()
    
    # Show schema setup
    setup_database()
    
    if connected:
        print("\n✅ InsForge connection working!")
        print("   Next: Create the tables using the SQL above in your InsForge dashboard")
    else:
        print("\n❌ Cannot connect to InsForge. Check your credentials in .env")
    
    exit(0 if connected else 1)
