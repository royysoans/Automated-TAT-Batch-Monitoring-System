"""
Automated TAT & Batch Monitoring System — FastAPI Application

Fully API-driven pipeline: no manual triggers or manual data entry required.
On startup, automatically initializes the DB, ingests EDOS data.
Background TAT breach checking is handled by GitHub Actions (external cron).
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from edos_parser import load_edos
from alert_service import check_all_samples_for_breaches
from routers import webhook, samples, alerts, tests, batches


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, load EDOS data on startup (local only)."""
    # Vercel functions must boot instantly. We skip heavy CSV parsing
    # because the Neon Postgres DB is already fully seeded.
    if not os.environ.get("VERCEL"):
        print("🔧 Initializing Postgres database...")
        init_db()
        print("📊 Loading EDOS data...")
        result = load_edos()
        print(f"✅ Loaded {result['loaded']} tests ({result['skipped']} skipped)")
    else:
        print("⚡ Vercel Serverless Boot (Skipping DB Init)")

    yield
    print("👋 Shutting down...")


app = FastAPI(
    title="TAT & Batch Monitoring System",
    description=(
        "Automated Turnaround Time and Batch Monitoring for Laboratory Diagnostics. "
        "Fully API-driven: webhook intake → EDOS lookup → batch assignment → "
        "ETA calculation → missed batch handling → alerts → live dashboard."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend (both local and production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Vercel deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routers
app.include_router(webhook.router)
app.include_router(samples.router)
app.include_router(alerts.router)
app.include_router(tests.router)
app.include_router(batches.router)


@app.get("/")
def root():
    """API index — lists all available endpoints for documentation."""
    return {
        "name": "TAT & Batch Monitoring System",
        "version": "1.0.0",
        "status": "running",
        "description": "Fully automated, API-driven pipeline for lab TAT monitoring",
        "endpoints": {
            "webhook_intake": "POST /api/webhook/sample — Entry point: fires on sample accession",
            "samples_list": "GET /api/samples — All samples with status, batch, ETA",
            "sample_detail": "GET /api/samples/{sample_id} — Single sample with full timeline",
            "sample_stats": "GET /api/samples/stats — Dashboard aggregate stats",
            "sample_status": "PUT /api/samples/{sample_id}/status — Update sample lifecycle status",
            "alerts_list": "GET /api/alerts — All alerts (missed batch, TAT breach, escalation)",
            "alert_acknowledge": "POST /api/alerts/{id}/acknowledge — Resolve an alert",
            "alert_breach_check": "POST /api/alerts/check-breaches — Manual breach scan trigger",
            "tests_list": "GET /api/tests — Browse EDOS test catalog with parsed schedules",
            "test_groups": "GET /api/tests/groups — Test groups with counts",
            "batches_active": "GET /api/batches — Active batch queues with sample counts",
            "batches_upcoming": "GET /api/batches/upcoming — Next batch window per test",
            "api_docs": "GET /docs — Interactive Swagger API documentation",
        }
    }


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}
