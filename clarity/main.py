"""Entry point for running the Clarity server."""

import uvicorn
import logging
from clarity.api.app import create_app
from clarity.config import settings


def main():
    """Run the Clarity server."""
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.clarity_log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    app = create_app()
    
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║        Clarity — AI Output Verification Layer              ║
    ║                  Starting Server...                         ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    print(f"📡 Environment: {settings.clarity_env}")
    print(f"🔑 Model: claude-sonnet-4-6")
    print(f"🌐 Running on http://localhost:8000")
    print(f"📊 Dashboard at http://localhost:8000/")
    print(f"🔌 API at http://localhost:8000/api/v1/")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.clarity_log_level.lower(),
    )


if __name__ == "__main__":
    main()
