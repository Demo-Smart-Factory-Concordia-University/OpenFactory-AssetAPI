"""
Main application entrypoint for the OpenFactory Routing Layer API.

This module creates and configures the FastAPI application for the routing layer,
which dynamically manages routing logic based on asset grouping and deployment strategy.

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

    - GET /asset_state?asset_uuid=...:
        Routes asset state queries to the centralized Asset State API.
"""

import uvicorn
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import Dict
from routing_layer.app.config import settings
from routing_layer.app.dependencies import routing_controller
from routing_layer.app.api.router_asset import router as assets_router
from routing_layer.app.api.router_asset_state import router as asset_state_router


app = FastAPI(
    title="OpenFactory API Routing Layer",
    description="Routing layer for the OpenFactory serving layer"
)


@app.get("/health", include_in_schema=False)
async def health_check() -> Dict[str, str]:
    """
    Liveness probe endpoint.

    Returns:
        JSON object with status "ok". This confirms that the API process is
        running and responsive, but does not guarantee service dependencies are healthy.
    """
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
async def readiness_check() -> JSONResponse:
    """
    Readiness probe endpoint.

    This endpoint checks the internal readiness of the routing layer, including:
        - Grouping strategy connection to ksqlDB
        - Deployment platform readiness (e.g., Docker Swarm manager availability)

    Returns:
        JSONResponse: A JSON response indicating readiness status.
                      If ready, returns {"status": "ready"} with HTTP 200.
                      If not ready, returns HTTP 503 with content {"status": "not ready", "issues": <message>}.
    """
    ready, issues = routing_controller.is_ready()
    if not ready:
        return JSONResponse(status_code=503, content={"status": "not ready", "issues": issues})
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/info", summary="Get application metadata")
async def get_app_info() -> JSONResponse:
    """
    Application metadata endpoint.

    This endpoint returns metadata about the running application, including:
        - Application version
        - Build origin
        - OpenFactory platform version

    Returns:
        JSONResponse: A JSON response containing application metadata with HTTP 200.
    """
    version = os.environ.get("APPLICATION_VERSION", "local-dev")
    build_origin = os.environ.get("APPLICATION_MANUFACTURER", "local-dev")
    ofa_version = os.environ.get("OPENFACTORY_VERSION", "local-dev")
    return JSONResponse(content={
        "version": version,
        "build_origin": build_origin,
        "openfactory_version": ofa_version
    })


app.include_router(assets_router)
app.include_router(asset_state_router)

if __name__ == "__main__":
    uvicorn.run("routing_layer.app.main:app",
                host="0.0.0.0", port=5555,
                reload=True,
                log_level=settings.log_level)
