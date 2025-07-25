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
"""

import hashlib
import httpx
from typing import Tuple
from abc import ABC, abstractmethod
from routing_layer.app.config import settings
from routing_layer.app.core.logger import get_logger


logger = get_logger("uvicorn.error")


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
    def initialize(self) -> None:
        """
        Initialize the deployment platform.

        This method is called once during the deployment and teardown phase by the `RoutingController`.
        It is responsible for preparing the deployment backend, such as validating
        environment setup, establishing connections, or verifying infrastructure state
        (e.g., checking Swarm mode or Kubernetes connectivity).

        Important:
            Subclasses must override this method to perform any setup required before deploying
            services.

        Raises:
            NotImplementedError: If not implemented in a subclass.
        """
        raise NotImplementedError("initialize() must be implemented by subclasses.")

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
            logger.debug(f"[DeploymentPlatform] check readiness of group {group_name}: {readiness_url}")
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

    @abstractmethod
    def deploy_state_api(self) -> None:
        """
        Deploy the centralized State API service.

        This service exposes the asset state via an HTTP API, typically backed by a materialized view
        such as ksqlDB or Kafka Streams.

        Important:
            This method must be implemented by subclasses.
        """
        raise NotImplementedError("deploy_state_api() must be implemented by subclasses.")

    @abstractmethod
    def remove_state_api(self) -> None:
        """
        Remove the centralized State API service.

        Important:
            This method must be implemented by subclasses.
        """
        raise NotImplementedError("remove_state_api() must be implemented by subclasses.")

    @abstractmethod
    def get_state_api_url(self) -> str:
        """
        Retrieve the service URL for the State API.

        Used by the routing layer to forward requests to the asset state endpoint.

        Returns:
            str: The resolved URL of the State API service.
        """
        raise NotImplementedError("get_state_api_url() must be implemented by subclasses.")
