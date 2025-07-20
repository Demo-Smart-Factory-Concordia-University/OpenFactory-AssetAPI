"""
Deployment script for OpenFactory Routing Layer.

This script initializes all backend infrastructure required by the routing layer,
based on the configured grouping strategy and deployment platform.

It prepares:
- Derived data streams or structures based on asset groupings.
- Group-specific service infrastructure if required by the deployment backend.

This script should be run before deploying the routing-layer API in production.

Usage:
    python -m routing_layer.deployment.deploy
"""

from routing_layer.deployment.controller_factory import create_routing_controller
from routing_layer.app.core.logger import setup_logging, get_logger

setup_logging()
logger = get_logger("deploy")


def main():
    controller = create_routing_controller()

    logger.info("Initializing routing controller")
    controller.initialize()

    logger.info("Deployment completed successfully")


if __name__ == "__main__":
    main()
