"""
Dependency Initialization Module for OpenFactory Routing Layer.

This module defines shared, singleton-style dependencies used throughout the
Routing Layer application.

It sets up a `RoutingController` instance by dynamically loading:

  - A grouping strategy from the `openfactory.grouping_strategies` entry point group.
  - A deployment platform from the `openfactory.deployment_platforms` entry point group.

The exact implementation used is determined by the environment variables:
    - `GROUPING_STRATEGY`
    - `DEPLOYMENT_PLATFORM`

These are defined in the global application configuration (via `Settings`).

This instance is imported by other parts of the application, such as the
FastAPI main entrypoint and endpoint routers.

Note:
    The dependencies are instantiated at module load time.
    This design is suitable for FastAPI apps where objects remain active
    across the app lifecycle.
"""

from routing_layer.app.core.controller.routing_controller import RoutingController

# Instantiate the routing controller with default grouping strategy and deployment backend
routing_controller = RoutingController()
