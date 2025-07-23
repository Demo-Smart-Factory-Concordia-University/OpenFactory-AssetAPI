"""
Deployment Script for OpenFactory Routing Layer.

This script sets up the full backend infrastructure required to operate
the routing layer in production or local development.

What it does:
  - Initializes derived Kafka streams (based on asset grouping strategy)
  - Deploys a service instance per group (via the deployment platform)
  - Deploys the central routing-layer API as a Swarm service (when not in local mode)

Usage:
    python -m routing_layer.deployment.deploy

Note:
    In 'local' mode, the API is not deployed as a Swarm service. Instead, run it manually via:

        python -m routing_layer.manage runserver
"""

from routing_layer.app.core.controller.routing_controller import RoutingController
from routing_layer.app.core.logger import setup_logging, get_logger
from routing_layer.app.config import settings

setup_logging()
logger = get_logger("deploy")


def main():
    controller = RoutingController()

    logger.info("Deploying OpenFactory routing API layer")
    controller.deploy()
    logger.info("Deployment completed successfully")

    if settings.environment == 'local':
        logger.info("To run the OpenFactory routing API layer use: python -m routing_layer.manage runserver")


if __name__ == "__main__":
    main()
