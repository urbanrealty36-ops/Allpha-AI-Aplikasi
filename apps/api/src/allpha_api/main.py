"""Minimal API thin slice for platform foundation.

Health endpoints report this process only. They do not claim that external
systems (database, storage, AI providers) are configured or reachable.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

APP_NAME = "allpha-api"
APP_VERSION = os.getenv("ALLPHA_API_VERSION", "0.1.0")
STARTED_AT = time.time()

app = FastAPI(
    title="Allpha Platform API",
    version=APP_VERSION,
    description="Foundation endpoints for the Allpha AI Social Universe.",
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Do not return exception details to clients.
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.get("/healthz", tags=["system"])
async def healthz() -> dict[str, str]:
    """Liveness probe: process is able to serve requests."""
    return {"status": "ok", "service": APP_NAME}


@app.get("/readyz", tags=["system"])
async def readyz() -> dict[str, Any]:
    """Readiness for the API process only; external dependencies are not wired yet."""
    return {
        "status": "ready",
        "service": APP_NAME,
        "version": APP_VERSION,
        "dependencies": {
            "database": "not_configured",
            "object_storage": "not_configured",
            "ai_gateway": "not_configured",
        },
    }


@app.get("/v1/system/status", tags=["system"])
async def system_status(request: Request) -> dict[str, Any]:
    """Internal foundation diagnostics; reports configuration, never secrets."""
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "uptime_seconds": max(0, int(time.time() - STARTED_AT)),
        "request_id": getattr(request.state, "request_id", "unknown"),
        "environment": os.getenv("ALLPHA_ENVIRONMENT", "development"),
        "capabilities": {
            "health_checks": True,
            "structured_error_contract": True,
            "database": False,
            "authentication": False,
        },
    }
