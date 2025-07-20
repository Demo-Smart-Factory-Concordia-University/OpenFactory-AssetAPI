"""
Dependency Initialization Module for OpenFactory Routing Layer.

This module defines shared, singleton-style dependencies used throughout the
Routing Layer application. It sets up:

- A Docker client for interacting with the host's Docker or Swarm environment.
- A `RoutingController` instance configured with:
    - A UNS-level-based grouping strategy (e.g., grouping by 'workcenter').
    - A Swarm-based deployment platform for group-specific FastAPI services.

These instances are imported by other parts of the application, such as the
FastAPI main entrypoint and endpoint routers.

Note:
    The dependencies are instantiated at module load time.
    This design is suitable for FastAPI apps where objects remain active
    across the app lifecycle.

Raises:
    docker.errors.DockerException: If Docker is not available or misconfigured.
"""

from routing_layer.app.core.controller.routing_controller import RoutingController
from routing_layer.app.core.controller.grouping_strategy import UNSLevelGroupingStrategy
from routing_layer.app.core.controller.deployment_platform import SwarmDeploymentPlatform

# Instantiate the routing controller with default grouping strategy and deployment backend
routing_controller = RoutingController(
    grouping_strategy=UNSLevelGroupingStrategy(grouping_level='workcenter'),
    deployment_platform=SwarmDeploymentPlatform(),
)
