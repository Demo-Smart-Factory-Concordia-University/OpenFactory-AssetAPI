"""
Deployment platform interfaces and implementations for OpenFactory routing layer.

This module defines the abstract base class `DeploymentPlatform`, which specifies the
interface for managing deployment of group-based services and retrieving their connection URLs.

The concrete implementation `SwarmDeploymentPlatform` uses Docker Swarm to deploy services
for each group, relying on the Docker SDK client and configuration settings.

Usage:
    - Implementations of `DeploymentPlatform` are responsible for handling
      service lifecycle events, such as creation, updating, and removal.
    - The routing layer uses these implementations to manage service availability
      per logical group.

Note:
    Uses configuration values from the shared `settings` module for Docker network and image.
"""

import re
import hashlib
import docker.errors
import httpx
import docker
from typing import Tuple
from abc import ABC, abstractmethod
from docker import DockerClient
from docker.types import EndpointSpec
from routing_layer.app.config import settings
from routing_layer.app.core.logger import get_logger


logger = get_logger(__name__)


class DeploymentPlatform(ABC):
    """
    Abstract base class defining the deployment interface for routing-layer components.

    A deployment platform is responsible for managing the lifecycle of containerized services
    (e.g., in Docker Swarm) that are dynamically created per logical group
    (such as workcenters or zones) and for deploying the routing layer API.

    Responsibilities are divided between:

    - Deployment Phase:
        - `deploy_service(group_name)`: Start a new service instance for a group.
        - `deploy_routing_layer_api()`: Deploy the central routing layer API service.

    - Runtime Phase:
        - `get_service_url(group_name)`: Retrieve the URL of the deployed group service.
        - `check_service_ready(group_name)`: Check if the service is up and ready to receive traffic.

    - Teardown:
        - `remove_service(group_name)`: Remove a deployed group service.
        - `remove_routing_layer_api()`: Remove the central routing layer API service.

    Subclasses must implement these methods using the underlying infrastructure (e.g., Docker, k8s).
    """
    @abstractmethod
    def deploy_service(self, group_name: str) -> None:
        """
        Deploy the service associated with the specified group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group to deploy the service for.
        """
        raise NotImplementedError("deploy_service() must be implemented by subclasses.")

    @abstractmethod
    def remove_service(self, group_name: str) -> None:
        """
        Remove the service associated with the specified group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group whose service should be removed.
        """
        raise NotImplementedError("remove_service() must be implemented by subclasses.")

    @abstractmethod
    def deploy_routing_layer_api(self) -> None:
        """
        Deploy the central routing layer API service.

        This is typically a long-running FastAPI process exposed on the edge of the platform.

        Important:
            This method must be implemented by subclasses.
        """
        raise NotImplementedError("deploy_routing_layer_api() must be implemented by subclasses.")

    @abstractmethod
    def remove_routing_layer_api(self) -> None:
        """
        Remove the central routing layer API service.

        Important:
            This method must be implemented by subclasses.
        """
        raise NotImplementedError("remove_routing_layer_api() must be implemented by subclasses.")

    @abstractmethod
    def get_service_url(self, group_name: str) -> str:
        """
        Retrieve the service URL for the specified group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group.

        Returns:
            str: The service connection URL.
        """
        raise NotImplementedError("get_service_url() must be implemented by subclasses.")

    def check_service_ready(self, group_name: str) -> Tuple[bool, str]:
        """
        Check whether the service for the specified group is ready to accept requests.

        Sends an HTTP GET request to the `/ready` endpoint of the service URL returned
        by `get_service_url()`.

        The readiness endpoint should return a JSON object like:

        .. code-block:: json

            {
                "status": "ready",
                "issues": {}
            }
            or
            {
                "status": "not ready",
                "issues": {
                    "database": "connection timeout"
                }
            }

        Args:
            group_name (str): The name of the group.

        Returns:
            Tuple: A tuple where the first element is True if the service is ready, False otherwise.
                   The second element is a message string summarizing the issue.

        Note:
            Can be overridden if the deployed services provide different mechanisms to
            communicate their ready state.
        """
        try:
            url = self.get_service_url(group_name)
            readiness_url = f"{url.rstrip('/')}/ready"
            response = httpx.get(readiness_url, timeout=2.0)
            if response.status_code == 404:
                return False, "Service does not expose a /ready endpoint (404 Not Found)"
            if response.status_code != 200:
                return False, f"Received status code {response.status_code}"

            data = response.json()
            status = data.get("status")
            issues = data.get("issues", {})

            if status == 'ready':
                return True, "Service is ready"
            else:
                issues_str = "; ".join(f"{k}: {v}" for k, v in issues.items())
                return False, f"Service readiness check failed: {issues_str or 'unknown issues'}"
        except httpx.RequestError as e:
            # Covers connection errors, DNS issues, timeouts, etc.
            return False, f"Service is not reachable: {e}"
        except Exception as e:
            return False, f"Unexpected error while checking readiness: {e}"

    def _get_host_port(self, group_name: str) -> int:
        """
        Compute the host port to bind to this group in 'local' mode.

        Uses a hash-based offset to reduce conflicts.

        Args:
            group_name (str): Group name used to derive the port.

        Returns:
            int: Host port to bind.
        """
        base = settings.fastapi_group_host_port_base
        h = int(hashlib.md5(group_name.encode()).hexdigest(), 16)
        return base + (h % 1000)  # Allows for up to 1000 unique ports


class SwarmDeploymentPlatform(DeploymentPlatform):
    """
    Concrete deployment platform using Docker Swarm.

    Manages dynamic deployment of group services as Swarm service replicas
    and resolves their accessible URLs (local or internal network).

    Notes:
        - Supports a 'local' mode (settings.environment == "local") where the routing
          API runs locally, while group services run inside the Swarm cluster.
        - Validates Swarm manager role and connectivity during initialization if
          `docker_client` is provided.
    """

    def __init__(self, docker_client: DockerClient = None) -> None:
        """
        Initialize the Swarm deployment backend.

        If `docker_client` is not None, checks that:
          - The Docker Engine is reachable
          - Swarm mode is active
          - The current node is a Swarm manager

        If any of these are not satisfied, an exception is raised.

        Args:
            docker_client (DockerClient): Optional Docker SDK client instance.

        Raises:
            RuntimeError: If Docker is unreachable or Swarm is not active/manager node.

        Note:
            During the running phase, `docker_client` must be set to None.
        """
        self.docker_client = docker_client

        if docker_client is None:
            return

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
            return

        logger.info(f"  🚀 Deploying Swarm service for group '{group_name}' using image '{settings.fastapi_group_image}'")

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
        logger.info(f"    Removing Swarm service for group '{group_name}'")
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
                     f'KSQLDBFASTAPI_GROUP_IMAGE_UNS_MAP={settings.fastapi_group_image}',
                     f'FASTAPI_GROUP_REPLICAS={settings.fastapi_group_replicas}',
                     f'FASTAPI_GROUP_CPU_LIMIT={settings.fastapi_group_cpus_limit}',
                     f'FASTAPI_GROUP_CPU_RESERVATION={settings.fastapi_group_cpus_reservation}',
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
