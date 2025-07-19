"""
Main application entrypoint for the OpenFactory Routing Layer API.

This module creates and configures the FastAPI application for the routing layer,
which dynamically manages routing logic based on asset grouping and deployment strategy.

It instantiates the routing controller using:
    - A UNS-level grouping strategy (e.g., by workcenter)
    - A Docker Swarm-based deployment platform for deploying service groups

Application lifecycle (startup/shutdown) is managed using FastAPI's lifespan events.
During startup, the routing controller initializes and begins monitoring group membership;
during shutdown, it gracefully stops dispatching and releases resources.

The Uvicorn ASGI server is launched when the module is run directly,
using configuration from the `settings` singleton.

Usage:
    Run locally for development:

        python -m routing_layer.app.main

    Or launch via Docker in a production Swarm deployment.

Environment variables defined in `routing_layer.app.config.Settings` control:
    - Kafka & ksqlDB connections
    - Docker network and image configuration
    - Logging verbosity

Exposed Endpoints:
    - GET /health:
        Lightweight liveness probe used by load balancers or orchestration tools
        to check if the API container is running and reachable.

    - GET /ready:
        Readiness probe used to verify whether the routing layer is ready to serve traffic.
        It checks whether internal dependencies (e.g., ksqlDB, Docker Swarm) are available
        and correctly configured. Returns 503 if not ready.

    - GET /asset_stream?asset_uuid=...:
        Main endpoint for clients to subscribe to asset events. Requests are
        dynamically routed to the appropriate group service.
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import AsyncGenerator
from routing_layer.app.config import settings
from routing_layer.app.dependencies import routing_controller
from routing_layer.app.api.router_asset import router as assets_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application startup and shutdown context manager.

    Initializes the routing controller on startup and ensures it is properly
    shut down on application exit.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control is yielded to allow the app to run.
    """
    routing_controller.initialize()
    try:
        yield
    finally:
        # Wait for dispatcher to stop cleanly
        routing_controller.stop()


app = FastAPI(
    title="OpenFactory API Routing Layer",
    description="Routing layer for the OpenFactory serving layer",
    lifespan=lifespan
)


@app.get("/health", include_in_schema=False)
async def health_check():
    """
    Liveness probe endpoint.

    Returns:
        JSON object with status "ok". This confirms that the API process is
        running and responsive, but does not guarantee service dependencies are healthy.
    """
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
async def readiness_check():
    """
    Readiness probe endpoint.

    This endpoint checks the internal readiness of the routing layer, including:
        - Grouping strategy connection to ksqlDB
        - Deployment platform readiness (e.g., Docker Swarm manager availability)

    Returns:
        - 200 OK with {"status": "ready"} if ready.
        - 503 Service Unavailable with issues listed if not ready.
    """
    ready, issues = routing_controller.is_ready()
    if not ready:
        return JSONResponse(status_code=503, content={"status": "not ready", "issues": issues})
    return {"status": "ready"}

app.include_router(assets_router)

if __name__ == "__main__":
    uvicorn.run("routing_layer.app.main:app",
                host="0.0.0.0", port=5555,
                reload=True,
                log_level=settings.log_level)
