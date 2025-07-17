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
"""

import docker
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import AsyncGenerator
from routing_layer.app.config import settings
from routing_layer.app.core.controller.routing_controller import RoutingController
from routing_layer.app.core.controller.grouping_strategy import UNSLevelGroupingStrategy
from routing_layer.app.core.controller.deployment_platform import SwarmDeploymentPlatform


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
    docker_client = docker.from_env()

    routing_controller = RoutingController(
        grouping_strategy=UNSLevelGroupingStrategy(grouping_level='workcenter'),
        deployment_platform=SwarmDeploymentPlatform(docker_client=docker_client),
    )
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

if __name__ == "__main__":
    uvicorn.run("routing_layer.app.main:app",
                host="0.0.0.0", port=5555,
                reload=True,
                log_level=settings.log_level)
