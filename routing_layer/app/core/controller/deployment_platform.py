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
from abc import ABC, abstractmethod
from docker import DockerClient
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


class SwarmDeploymentPlatform(DeploymentPlatform):
    """
    Concrete deployment platform using Docker Swarm.

    Manages deployment of group services as Docker Swarm services
    and constructs their access URLs.
    """

    def __init__(self, docker_client: DockerClient) -> None:
        """
        Initialize the SwarmDeploymentPlatform with a Docker client.

        Args:
            docker_client (DockerClient): Docker SDK client instance for interacting with the Docker environment.
        """
        self.docker_client = docker_client

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

    def deploy_service(self, group_name: str) -> None:
        """
        Deploy or update the Docker Swarm service corresponding to the specified group.

        Args:
            group_name (str): The name of the group for which to deploy the service.

        Returns:
            None
        """
        logger.info(f"   🚀 Deploying Swarm service for group '{group_name}' using image '{settings.fastapi_group_image}'")
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
                 f'KAFKA_CONSUMER_GROUP_ID=asset_stream_{group_name}_consumer_group']
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
        return f"http://{self._service_name(group_name)}:5555/asset_stream"
