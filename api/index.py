# api/index.py — Vercel Python Serverless entry point
# This file re-exports the FastAPI app from the backend so Vercel can
# discover it in the required api/ directory structure.

import sys
import os

# Add the backend directory to path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app
