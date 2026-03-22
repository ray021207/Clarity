"""
Vercel serverless function for Clarity API.
Exports FastAPI app for Vercel's ASGI runtime.
"""

import sys
import os

# Add parent directory to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clarity.api.app import create_app

# Create and export the FastAPI app
app = create_app()

# Vercel calls this 'handler'
handler = app
