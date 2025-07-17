"""
Routing controller for OpenFactory's Routing Layer.

This module defines the `RoutingController`, which orchestrates the behavior of
grouping strategies and deployment platforms. It is responsible for:

- Initializing and tearing down group-specific services and Kafka streams
- Handling incoming client requests and routing them to the appropriate group service
- Managing the lifecycle of group resources dynamically based on asset metadata
"""

import logging
from typing import Optional
from routing_layer.app.core.controller.grouping_strategy import GroupingStrategy
from routing_layer.app.core.controller.deployment_platform import DeploymentPlatform

logger = logging.getLogger("uvicorn.error")


class RoutingController:
    """
    Core controller for the Routing Layer.

    This class coordinates between a grouping strategy and a deployment platform to:
    - Create group-specific Kafka streams
    - Deploy corresponding FastAPI services
    - Dynamically route client requests to the appropriate group

    Args:
        grouping_strategy: Instance of a class implementing the GroupingStrategy interface.
        deployment_platform: Instance of a class implementing the DeploymentPlatform interface.
    """

    def __init__(self, grouping_strategy: GroupingStrategy, deployment_platform: DeploymentPlatform) -> None:
        """
        Initialize the RoutingController.

        Args:
            grouping_strategy (GroupingStrategy): The strategy used to determine how assets are grouped.
            deployment_platform (DeploymentPlatform): The platform used to deploy group-specific services.
        """
        self.grouping_strategy = grouping_strategy
        self.deployment_platform = deployment_platform

    def initialize(self) -> None:
        """
        Initialize the routing layer by creating streams and deploying services
        for all currently known groups.
        """
        logger.info("Initializing Routing Layer...")
        for group in self.grouping_strategy.get_all_groups():
            logger.info(f"  Spin up group [{group}]")
            self.grouping_strategy.create_derived_stream(group)
            self.deployment_platform.deploy_service(group)
        logger.info("✅ Routing Layer initialization complete.")

    def stop(self) -> None:
        """
        Tear down the routing layer by removing all group-specific streams.

        Note:
            Group services are not stopped here — only their Kafka streams are removed.
        """
        logger.info("Stopping Routing Layer...")
        for group in self.grouping_strategy.get_all_groups():
            logger.info(f"  Tearing down group [{group}]")
            self.grouping_strategy.remove_derived_stream(group)
            self.deployment_platform.remove_service(group)
        logger.info("✅ Routing Layer removal complete.")

    def handle_client_request(self, asset_uuid: str) -> Optional[str]:
        """
        Determine the group for a given asset UUID and return the corresponding service URL.

        This method performs lazy stream/service creation if the group is not yet deployed.

        Args:
            asset_uuid (str): The UUID of the asset making the request.

        Returns:
            Optional[str]: The service URL for the group, or None if the group could not be resolved.
        """
        group = self.grouping_strategy.get_group_for_asset(asset_uuid)
        if not group:
            logger.warning(f"⚠️ Could not determine group for asset {asset_uuid}")
            return None

        logger.info(f"📦 Asset {asset_uuid} → group '{group}'")
        # Lazy deploy/ensure resources
        self.grouping_strategy.create_derived_stream(group)
        self.deployment_platform.deploy_service(group)
        return self.deployment_platform.get_service_url(group)
