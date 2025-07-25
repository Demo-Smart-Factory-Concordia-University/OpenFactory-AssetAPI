"""
Routing controller for OpenFactory's Routing Layer.

This module defines the `RoutingController`, which orchestrates the behavior of
grouping strategies and deployment platforms. It is responsible for:

- Initializing and tearing down group-specific services and Kafka streams
- Deploying the OpenFactory routing layer API
- Handling incoming client requests and routing them to the appropriate group service
"""

import httpx
from typing import Optional, Tuple, Dict
from routing_layer.app.core.logger import get_logger
from routing_layer.app.config import settings
from routing_layer.app.core.utils import load_plugin
from routing_layer.app.core.controller.grouping_strategy import GroupingStrategy
from routing_layer.app.core.controller.deployment_platform import DeploymentPlatform

logger = get_logger(__name__)


class RoutingController:
    """
    Core controller for the Routing Layer.

    This class coordinates between a grouping strategy and a deployment platform to:
    - Create group-specific Kafka streams
    - Deploy corresponding FastAPI services
    - Dynamically route client requests to the appropriate group
    """

    def __init__(self) -> None:
        """
        Initialize the RoutingController using plugin-based configuration.

        This constructor dynamically loads the grouping strategy and deployment platform
        based on the environment variables `GROUPING_STRATEGY` and `DEPLOYMENT_PLATFORM`
        defined in the application settings.

        The corresponding classes must be registered as entry points in `pyproject.toml` under:

        - `openfactory.grouping_strategies`
        - `openfactory.deployment_platforms`

        Raises:
            ValueError: If no matching plugin is found, or if the loaded class does not
                        subclass the expected interface.
        """
        strategy_cls = load_plugin("openfactory.grouping_strategies", settings.grouping_strategy)
        platform_cls = load_plugin("openfactory.deployment_platforms", settings.deployment_platform)

        if not issubclass(strategy_cls, GroupingStrategy):
            raise TypeError(
                f"Plugin '{settings.grouping_strategy}' does not inherit from GroupingStrategy"
            )

        if not issubclass(platform_cls, DeploymentPlatform):
            raise TypeError(
                f"Plugin '{settings.deployment_platform}' does not inherit from DeploymentPlatform"
            )

        self.grouping_strategy = strategy_cls()
        self.deployment_platform = platform_cls()

    def _initialize(self) -> None:
        """
        Initialize the routing layer by creating streams and deploying services
        for all currently known groups.
        """
        logger.info("Initializing Routing Layer...")
        self.deployment_platform.initialize()
        for group in self.grouping_strategy.get_all_groups():
            logger.info(f"Spin up group [{group}]")
            self.grouping_strategy.create_derived_stream(group)
            self.deployment_platform.deploy_service(group)
        logger.info("Spin up State-API")
        self.deployment_platform.deploy_state_api()
        logger.info("✅ Routing Layer initialization complete.")

    def deploy(self) -> None:
        """  Deploy the OpenFactory routing layer API. """
        self._initialize()
        if settings.environment != 'local':
            self.deployment_platform.deploy_routing_layer_api()
            logger.info("✅ Routing Layer API deployement complete.")

    def teardown(self) -> None:
        """
        Tear down the routing layer by removing all group-specific streams and services.
        """
        logger.info("Stopping Routing Layer...")
        self.deployment_platform.initialize()
        for group in self.grouping_strategy.get_all_groups():
            logger.info(f"  Tearing down group [{group}]")
            self.grouping_strategy.remove_derived_stream(group)
            self.deployment_platform.remove_service(group)
        logger.info("  Tearing State-API")
        self.deployment_platform.remove_state_api()
        if settings.environment != 'local':
            self.deployment_platform.remove_routing_layer_api()
        logger.info("✅ Routing Layer removal complete.")

    def handle_client_request(self, asset_uuid: str) -> Optional[str]:
        """
        Determine the group for a given asset UUID and return the corresponding service URL.

        Args:
            asset_uuid (str): The UUID of the asset making the request.

        Returns:
            Optional[str]: The service URL for the group, or None if the group could not be resolved.
        """
        group = self.grouping_strategy.get_group_for_asset(asset_uuid)
        if not group or group == 'UNAVAILABLE':
            logger.warning(f"[controller] Could not determine group for asset {asset_uuid}")
            return None

        logger.debug(f"[controller] Asset {asset_uuid} is in group '{group}'")
        return self.deployment_platform.get_service_url(group)

    def is_ready(self) -> Tuple[bool, Dict[str, str]]:
        """
        Check the readiness status of the routing controller and its subcomponents.

        This method verifies whether the routing layer is ready to handle incoming requests
        by checking both the grouping strategy and the deployment platform. Each subcomponent's
        readiness is determined by calling its own `is_ready()` method, which returns a tuple
        of (bool, str) — indicating readiness and an optional diagnostic message.

        Returns:
            Tuple: A tuple where the first element is a boolean indicating
            overall readiness, and the second element is a dictionary mapping component
            names (e.g., "grouping_strategy") to diagnostic messages if not ready.

        Example:
        .. code-block:: python

            (True, {})
            (False, {
                "grouping_strategy": "ksqlDB unreachable",
                "deployment_platform": "Docker not reachable"
            })
        """
        issues = {}

        grouping_ready, grouping_msg = self.grouping_strategy.is_ready()
        if not grouping_ready:
            issues["grouping_strategy"] = grouping_msg

        # Check readiness status of deployed services
        for group in self.grouping_strategy.get_all_groups():
            healthy, msg = self.deployment_platform.check_service_ready(group)
            if not healthy:
                issues[f"service:{group}"] = msg

        # Check readiness status of state API
        state_url = self.deployment_platform.get_state_api_url()
        try:
            response = httpx.get(f"{state_url.rstrip('/')}/ready", timeout=2.0)
            if response.status_code == 404:
                issues["state_api"] = "No /ready endpoint defined"
            elif response.status_code != 200:
                issues["state_api"] = f"Status code {response.status_code}"
            else:
                data = response.json()
                if data.get("status") != "ready":
                    issues["state_api"] = "Reported not ready"
        except Exception as e:
            issues["state_api"] = f"{state_url} not reachable: {e}"

        return (len(issues) == 0, issues)
