"""FastAPI application setup and configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="Clarity — AI Output Verification Layer",
        description="Multi-agent trust verification for LLM outputs",
        version="0.1.0",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For development; restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount dashboard as static files
    dashboard_path = Path(__file__).parent.parent.parent / "dashboard"
    if dashboard_path.exists():
        app.mount("/", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")
    
    # Import and include routes
    from .routes import router
    app.include_router(router, prefix="/api/v1")
    
    return app
