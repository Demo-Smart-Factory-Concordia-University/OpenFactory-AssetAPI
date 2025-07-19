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

import logging
import re
import hashlib
from typing import Tuple
from abc import ABC, abstractmethod
from docker import DockerClient
from docker.types import EndpointSpec
from routing_layer.app.config import settings


logger = logging.getLogger("uvicorn.error")


class DeploymentPlatform(ABC):
    """
    Abstract base class defining deployment platform interface.

    A deployment platform manages the lifecycle and access endpoints of
    service instances corresponding to logical groups.

    Subclasses must implement deployment and URL retrieval for groups.
    """
    @abstractmethod
    def deploy_service(self, group_name: str) -> None:
        """
        Deploy or ensure the deployment of the service associated with the specified group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group to deploy the service for.

        Returns:
            None
        """
        raise NotImplementedError("deploy_service() must be implemented by subclasses.")

    @abstractmethod
    def remove_service(self, group_name: str) -> None:
        """
        Remove the service associated with the given group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group whose service should be removed.
        """
        raise NotImplementedError("remove_service() must be implemented by subclasses.")

    @abstractmethod
    def get_service_url(self, group_name: str) -> str:
        """
        Get the URL that clients should use to connect to the service for the specified group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group.

        Returns:
            str: The service connection URL.
        """
        raise NotImplementedError("get_service_url() must be implemented by subclasses.")

    @abstractmethod
    def is_ready(self) -> Tuple[bool, str]:
        """
        Check if the deployment platform is ready.

        This method should verify that the platform can manage services,
        e.g., can connect to Docker Swarm API, list services, etc.

        Returns:
            A tuple where the first element is a boolean indicating readiness,
            and the second element is a diagnostic message explaining the status
            or error.
        """
        raise NotImplementedError("is_ready() must be implemented by subclasses.")

    def _get_host_port(self, group_name: str) -> int:
        """
        Generate a consistent but unique host port for a group name.
        """
        base = settings.fastapi_group_host_port_base
        h = int(hashlib.md5(group_name.encode()).hexdigest(), 16)
        return base + (h % 1000)  # Allows for up to 1000 unique ports


class SwarmDeploymentPlatform(DeploymentPlatform):
    """
    Concrete deployment platform using Docker Swarm.

    Manages deployment of group services as Docker Swarm services
    and constructs their access URLs.
    """

    def __init__(self, docker_client: DockerClient) -> None:
        """
        Initialize the SwarmDeploymentPlatform with a Docker client.

        This checks that:
        - The Docker Engine is reachable
        - Swarm mode is active
        - The current node is a Swarm manager

        If any of these are not satisfied, an exception is raised.

        Args:
            docker_client (DockerClient): Docker SDK client instance for interacting with the Docker environment.

        Raises:
            RuntimeError: If Docker or Swarm are not properly configured.
        """
        self.docker_client = docker_client

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
        Returns Docker service name associated with a group.

        Args:
            group_name (str): The name of the group.

        Returns:
            str: A sanitized Docker service name.
        """
        safe_name = self._sanitize_group_name(group_name)
        return f"stream-api-group-{safe_name}"

    def is_ready(self) -> Tuple[bool, str]:
        """
        Check if the Docker Swarm deployment platform is still healthy at runtime.

        This includes:
        - Docker Engine is reachable
        - Swarm mode is still active
        - Swarm service metadata can be listed (e.g., manager is still functional)

        Returns:
            A tuple of (readiness: bool, diagnostic message: str)
        """
        try:
            self.docker_client.ping()
        except Exception as e:
            return False, f"Docker Engine unreachable: {str(e)}"

        try:
            info = self.docker_client.info()
            if info.get("Swarm", {}).get("LocalNodeState", "") != "active":
                return False, "Swarm is no longer active"

            # Checking that we can interact with the manager
            self.docker_client.services.list()

            return True, "ok"
        except Exception as e:
            return False, f"Swarm interaction failed: {str(e)}"

    def deploy_service(self, group_name: str) -> None:
        """
        Deploy or update the Docker Swarm service corresponding to the specified group.

        Args:
            group_name (str): The name of the group for which to deploy the service.

        Returns:
            None
        """
        # check if service is alreay deployed
        existing_services = self.docker_client.services.list(filters={"name": self._service_name(group_name)})
        if existing_services:
            return

        logger.info(f"   🚀 Deploying Swarm service for group '{group_name}' using image '{settings.fastapi_group_image}'")

        # Default endpoint spec (no published port)
        endpoint_spec = None

        # In local mode, publish port 5555 to host
        if settings.environment == "local":
            endpoint_spec = EndpointSpec(
                ports={self._get_host_port(group_name): 5555}  # host:container
            )

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

    def remove_service(self, group_name: str) -> None:
        """
        Remove the service associated with the given group.

        Args:
            group_name (str): The name of the group whose service should be removed.
        """
        logger.info(f"    Removing Swarm service for group '{group_name}'")
        service = self.docker_client.services.get(self._service_name(group_name))
        service.remove()

    def get_service_url(self, group_name: str) -> str:
        """
        Return the URL for clients to access the service of the specified group.

        Args:
            group_name (str): The name of the group.

        Returns:
            str: The URL to connect to the group's service.
        """
        if settings.environment == "local":
            logger.info("Using local override for target URL")
            host_port = self._get_host_port(group_name)
            return f"http://{settings.swarm_node_host}:{host_port}/asset_stream"
        return f"http://{self._service_name(group_name)}:5555/asset_stream"
