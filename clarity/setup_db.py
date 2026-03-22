"""Database schema setup for InsForge.

Run this once to initialize trust_reports and exchange_logs tables.
"""

from clarity.integrations.insforge_client import InsForgeClient


def setup_db():
    """Initialize InsForge database tables."""
    
    print("Setting up Clarity database schema on InsForge...")
    
    client = InsForgeClient()
    
    # Create tables (will output SQL to console)
    client.create_tables()
    
    print("\n✅ Database setup instructions printed above.")
    print("   Execute the SQL in your InsForge dashboard or use direct SQL access.")


if __name__ == "__main__":
    setup_db()
