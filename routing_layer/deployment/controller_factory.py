"""
Factory module for creating a preconfigured RoutingController instance.

This ensures consistent configuration across deployment, teardown, and
runtime initialization scripts.
"""

from routing_layer.app.core.controller.routing_controller import RoutingController
from routing_layer.app.core.controller.grouping_strategy import UNSLevelGroupingStrategy
from routing_layer.app.core.controller.deployment_platform import SwarmDeploymentPlatform
import docker


def create_routing_controller() -> RoutingController:
    """
    Create a RoutingController with the default strategy and deployment backend.

    Returns:
        RoutingController: Configured controller instance.
    """
    docker_client = docker.from_env()

    return RoutingController(
        grouping_strategy=UNSLevelGroupingStrategy(grouping_level="workcenter"),
        deployment_platform=SwarmDeploymentPlatform(docker_client=docker_client),
    )
