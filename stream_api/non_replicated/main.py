"""
Main entrypoint for the non-replicated Stream API service.

This service exposes an HTTP interface for asset data streaming,
intended to be used by the OpenFactory Routing Layer. It serves
group-specific data via FastAPI endpoints and consumes messages
from Kafka using a shared dispatcher.

Key Responsibilities:
    - Start and manage the Kafka dispatcher that handles fan-out of messages
      to async queues for asset-specific subscribers.
    - Expose streaming endpoints for asset data via `/asset_stream`.
    - Provide a `/ready` health probe for readiness checks by orchestration systems.
    - Manage service lifecycle through FastAPI's lifespan context.

Run:
    This file can be run directly as a module or launched via a process manager.

    .. code-block:: bash
        python -m stream_api.non_replicated.main

Endpoints:
    - GET /asset_stream: Streams asset-specific data (proxy entrypoint).
    - GET /ready: Health/readiness probe endpoint for orchestration checks.

Environment Variables:
    - KAFKA_BROKER: Address of the Kafka broker.
    - KAFKA_TOPIC: Kafka topic to consume messages from.
    - KAFKA_CONSUMER_GROUP_ID: Kafka consumer group ID.
    - LOG_LEVEL: Logging verbosity ("debug", "info", "warning", etc.)
"""

import asyncio
import logging
import uvicorn
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from stream_api.non_replicated.config import settings
from stream_api.non_replicated.app.core.kafka_dispatcher import start_kafka_dispatcher
from stream_api.non_replicated.app.api import asset_stream
from stream_api.non_replicated.app.api import readiness


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Initializes the Kafka dispatcher when the app starts,
    and ensures it is stopped cleanly during shutdown.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None
    """
    loop = asyncio.get_running_loop()
    dispatcher = start_kafka_dispatcher(loop)
    app.state.kafka_dispatcher = dispatcher
    try:
        yield
    finally:
        # Wait for dispatcher to stop cleanly
        dispatcher.stop()

app = FastAPI(lifespan=lifespan)
app.include_router(readiness.router)
app.include_router(asset_stream.router)


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


def setup_logging():
    """ Configure logging for Uvicorn and service-specific loggers. """
    level = settings.log_level.upper()
    uvicorn_loggers = ["uvicorn.error", "uvicorn.access", "uvicorn"]
    for logger_name in uvicorn_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)


if __name__ == "__main__":
    # Entry point for running the service directly
    setup_logging()
    uvicorn.run("stream_api.non_replicated.main:app",
                host="0.0.0.0", port=5555,
                reload=True,
                log_level=settings.log_level)
