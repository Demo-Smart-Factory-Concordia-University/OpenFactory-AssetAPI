"""
Teardown script for OpenFactory Routing Layer.

This script gracefully shuts down or removes the infrastructure managed by the routing layer,
according to the configured grouping strategy and deployment platform.

It may:
- Stop or delete group-specific service instances.
- Drop derived data streams or temporary resources.

Use this to clean up the environment or reset it before a fresh deployment.

Usage:
    python -m routing_layer.deployment.teardown
"""

from routing_layer.app.core.controller.routing_controller import RoutingController
from routing_layer.app.core.logger import setup_logging, get_logger

setup_logging()
logger = get_logger("teardown")


def main():
    controller = RoutingController()

    logger.info("[teardown] Stopping routing controller")
    controller.teardown()
    logger.info("[teardown] Teardown completed successfully")


if __name__ == "__main__":
    main()
