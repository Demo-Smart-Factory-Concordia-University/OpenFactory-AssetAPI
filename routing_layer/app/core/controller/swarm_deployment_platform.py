"""
Swarm Deployment Backend for Dynamic Service Management.

This module implements the `SwarmDeploymentPlatform`, a concrete deployment backend
based on Docker Swarm. It supports dynamically deploying and removing service containers
for processing groups in a distributed architecture.

Features:
    - Deployment of per-group FastAPI services as Docker Swarm services.
    - Central routing layer API deployment to interface with all group services.
    - Docker Swarm health and manager node verification during initialization.
    - Environment-aware endpoint resolution (supports 'local' and production modes).
    - CPU resource constraints and Kafka stream configuration injection.

Intended Use:
    - Designed to run as part of the routing layer in OpenFactory's streaming pipeline.
    - Should only be used in environments where Docker Swarm mode is active and the
      node is part of a manager quorum.

Dependencies:
    - Docker SDK for Python (`docker`)
    - OpenFactory `settings` module for runtime configuration
    - Custom logging via `get_logger`

Raises:
    - RuntimeError if Docker Swarm is not active or misconfigured at startup.

Note:
    - Services are named using the prefix "stream-api-group-" followed by a sanitized
      group name to maintain uniqueness and DNS-safe formatting.
"""

import re
import docker
import docker.errors
from docker.types import EndpointSpec
from routing_layer.app.config import settings
from routing_layer.app.core.logger import get_logger
from routing_layer.app.core.controller.deployment_platform import DeploymentPlatform


logger = get_logger(__name__)


class SwarmDeploymentPlatform(DeploymentPlatform):
    """
    Deployment platform using Docker Swarm.

    Manages dynamic deployment of group services as Swarm service replicas
    and resolves their accessible URLs (local or internal network).

    Notes:
        - Supports a 'local' mode (settings.environment == "local") where the routing
          API runs locally, while group services run inside the Swarm cluster.
        - Validates Swarm manager role and connectivity during initialization if
          `docker_client` is provided.
    """

    def initialize(self) -> None:
        """
        Initialize the Swarm deployment backend.

        Establishes a connection to the local Docker Engine and performs the following checks:
            - The Docker Engine is reachable.
            - Docker Swarm mode is active on the node.
            - The current node has Swarm manager privileges.

        If any of these conditions are not met, a RuntimeError is raised.

        Raises:
            RuntimeError: If the Docker Engine is unreachable, Swarm mode is inactive,
                          or the node is not a Swarm manager.

        Note:
            This method is intended to be called **only** during the deployment and teardown phases
            by the `RoutingController`.
        """
        self.docker_client = docker.from_env()

        try:
            self.docker_client.ping()
        except Exception as e:
            raise RuntimeError(f"Docker Engine unreachable during init: {str(e)}")

        try:
            info = self.docker_client.info()
            swarm_state = info.get("Swarm", {}).get("LocalNodeState", "")
            is_manager = info.get("Swarm", {}).get("ControlAvailable", False)

            if swarm_state != "active":
                raise RuntimeError(f"Swarm is not active on this node (state: {swarm_state})")

            if not is_manager:
                raise RuntimeError("Swarm manager required during init: This node is not a Swarm manager.")

        except Exception as e:
            raise RuntimeError(f"Failed to verify Swarm configuration during init: {str(e)}")

    def _sanitize_group_name(self, group_name: str) -> str:
        """
        Sanitizes the group name to be a valid Docker Swarm service name component.

        Args:
            group_name (str): The raw group name.

        Returns:
            str: A sanitized, lowercase, dash-safe string suitable for service naming.
        """
        sanitized = re.sub(r'[^a-z0-9]+', '-', group_name.lower())  # Replace non-alphanumerics with dash
        return sanitized.strip('-')

    def _service_name(self, group_name: str) -> str:
        """
        Generate the Docker Swarm service name for a group.

        Args:
            group_name (str): The name of the group.

        Returns:
            str: A sanitized Docker service name.
        """
        safe_name = self._sanitize_group_name(group_name)
        return f"stream-api-group-{safe_name}"

    def deploy_service(self, group_name: str) -> None:
        """
        Deploy a Docker Swarm service for the given group if not already deployed.

        Args:
            group_name (str): The name of the group for which to deploy the service.

        Returns:
            None
        """
        # check if service is alreay deployed
        existing_services = self.docker_client.services.list(filters={"name": self._service_name(group_name)})
        if existing_services:
            logger.info(f" 🔄 Swarm service for group '{group_name}' already running.")
            return

        logger.info(f" 🚀 Deploying Swarm service for group '{group_name}' using image '{settings.fastapi_group_image}'")

        # Default endpoint spec (no published port)
        endpoint_spec = None

        # In local mode, publish port 5555 to host
        if settings.environment == "local":
            endpoint_spec = EndpointSpec(
                ports={self._get_host_port(group_name): 5555}  # host:container
            )

        try:
            self.docker_client.services.create(
                image=settings.fastapi_group_image,
                name=self._service_name(group_name),
                networks=[settings.docker_network],
                mode={"Replicated": {"Replicas": settings.fastapi_group_replicas}},
                resources={
                        "Limits": {"NanoCPUs": int(1000000000*settings.fastapi_group_cpus_limit)},
                        "Reservations": {"NanoCPUs": int(1000000000*settings.fastapi_group_cpus_reservation)}
                        },
                env=[f'KAFKA_BROKER={settings.kafka_broker}',
                     f'KAFKA_TOPIC=asset_stream_{group_name}_topic',
                     f'KAFKA_CONSUMER_GROUP_ID=asset_stream_{group_name}_consumer_group'],
                endpoint_spec=endpoint_spec
            )
        except docker.errors.APIError as e:
            logger.error(f"  Docker API error during deployment of group '{group_name}': {e}")

    def remove_service(self, group_name: str) -> None:
        """
        Remove the service associated with the given group.

        Args:
            group_name (str): The name of the group whose service should be removed.
        """
        logger.info(f"  Removing Swarm service for group '{group_name}'")
        try:
            service = self.docker_client.services.get(self._service_name(group_name))
            service.remove()
        except docker.errors.NotFound:
            logger.warning(f"  Swarm service for group '{group_name}' not deployed on OpenFactory Swarm cluster")
        except docker.errors.APIError as e:
            logger.error(f"  Docker API error: {e}")

    def deploy_routing_layer_api(self) -> None:
        """ Deploy the central routing layer API service. """

        existing_services = self.docker_client.services.list(filters={"name": 'serving_layer_router'})
        if existing_services:
            logger.info("🚀 Routing layer API already deployed on OpenFactory Swarm cluster")
            return

        logger.info("🚀 Deploying routing layer API on OpenFactory Swarm cluster")
        try:
            self.docker_client.services.create(
                image=settings.routing_layer_image,
                name='serving_layer_router',
                networks=[settings.docker_network],
                mode={"Replicated": {"Replicas": settings.routing_layer_replicas}},
                resources={
                        "Limits": {"NanoCPUs": int(1000000000*settings.routing_layer_cpus_limit)},
                        "Reservations": {"NanoCPUs": int(1000000000*settings.routing_layer_cpus_reservation)}
                        },
                env=[f'KSQLDB_URL={settings.ksqldb_url}',
                     f'KAFKA_BROKER={settings.kafka_broker}',
                     f'KSQLDB_ASSETS_STREAM={settings.ksqldb_assets_stream}',
                     f'KSQLDB_UNS_MAP={settings.ksqldb_uns_map}',
                     f'LOG_LEVEL={settings.log_level}',
                     'ENVIRONMENT=production'],
                endpoint_spec=EndpointSpec(ports={5555: 5555})
            )
        except docker.errors.APIError as e:
            logger.error(f"  Docker API error: {e}")

    def remove_routing_layer_api(self) -> None:
        """ Remove the central routing layer API service. """
        logger.info("  Removing routing layer API from the OpenFactory Swarm cluster")
        try:
            service = self.docker_client.services.get('serving_layer_router')
            service.remove()
        except docker.errors.NotFound:
            logger.warning("  Routing layer API not deployed on OpenFactory Swarm cluster")
        except docker.errors.APIError as e:
            logger.error(f"  Docker API error: {e}")

    def get_service_url(self, group_name: str) -> str:
        """
        Resolve the endpoint URL for a group service.

        In 'local' mode, maps to localhost; otherwise, uses internal Docker DNS.

        Args:
            group_name (str): The name of the group.

        Returns:
            str: Resolved HTTP service endpoint.
        """
        if settings.environment == "local":
            logger.info("Using local override for target URL")
            host_port = self._get_host_port(group_name)
            return f"http://{settings.swarm_node_host}:{host_port}"
        return f"http://{self._service_name(group_name)}:5555"
