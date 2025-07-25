"""
Local Docker Deployment Backend for OpenFactory Routing Layer.

This module implements the `DockerDeploymentPlatform`, a deployment backend
using standard Docker containers (non-Swarm). It enables launching and removing
per-group FastAPI services, the central routing layer API, and the State API directly
on the local host or development machine.

Intended for:
    - Local development or testing environments without Docker Swarm.
    - Environments where container orchestration is handled externally.

Features:
    - Group-specific FastAPI services are launched as individual containers.
    - Central routing layer API deployment for handling asset stream routing.
    - Centralized State API deployment for querying asset state via materialized views.
    - Environment-aware endpoint resolution in 'local' mode (uses host ports).
    - CPU limits, environment variables, and internal networking per container.

Dependencies:
    - Docker SDK for Python (`docker`)
    - `routing_layer.app.config.settings`
    - Custom logging via `get_logger`

Notes:
    - Group service containers are named "stream-api-group-<group_name>".
    - Routing layer container is named "serving-layer-router".
    - State API container is named "openfactory-state-api".
    - Default service port is 5555 for all components.
"""

import re
import docker
import docker.errors
from routing_layer.app.config import settings
from routing_layer.app.core.logger import get_logger
from routing_layer.app.core.controller.deployment_platform import DeploymentPlatform

logger = get_logger(__name__)


class DockerDeploymentPlatform(DeploymentPlatform):
    """
    Deployment platform using standard Docker containers.

    Spawns FastAPI services for each group using local Docker containers.
    Suitable for local dev/testing environments without Docker Swarm.
    """

    def initialize(self) -> None:
        """
        Initializes the Docker client and checks connectivity.
        """
        self.docker_client = docker.from_env()
        try:
            self.docker_client.ping()
        except Exception as e:
            raise RuntimeError(f"Docker Engine unreachable: {str(e)}")

    def _sanitize_group_name(self, group_name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", group_name.lower()).strip("-")

    def _container_name(self, group_name: str) -> str:
        return f"stream-api-group-{self._sanitize_group_name(group_name)}"

    def deploy_service(self, group_name: str) -> None:
        """
        Launch a group-specific FastAPI service as a Docker container.

        Args:
            group_name (str): Group name to deploy.
        """
        container_name = self._container_name(group_name)

        # Check if container already exists
        try:
            self.docker_client.containers.get(container_name)
            logger.info(f"🔄 Docker container for group '{group_name}' already running.")
            return
        except docker.errors.NotFound:
            pass

        logger.info(f"🚀 Starting Docker container for group '{group_name}'")

        ports = {}
        if settings.environment == "local":
            ports = {"5555/tcp": self._get_host_port(group_name)}

        env_vars = {
            "KAFKA_BROKER": settings.kafka_broker,
            "KAFKA_TOPIC": f"asset_stream_{group_name}_topic",
            "KAFKA_CONSUMER_GROUP_ID": f"asset_stream_{group_name}_consumer_group",
            "DEPLOYMENT_PLATFORM": "docker"
        }

        try:
            self.docker_client.containers.run(
                image=settings.fastapi_group_image,
                name=container_name,
                detach=True,
                network=settings.docker_network,
                ports=ports,
                environment=env_vars,
                cpu_quota=int(100000 * settings.fastapi_group_cpus_limit),  # microseconds/100ms
                cpu_period=100000,
            )
        except docker.errors.APIError as e:
            logger.error(f"💥 Docker error launching group '{group_name}': {e}")

    def remove_service(self, group_name: str) -> None:
        """
        Remove a running group-specific container.

        Args:
            group_name (str): Group to remove.
        """
        container_name = self._container_name(group_name)
        logger.info(f" Removing Docker container for group '{group_name}'")
        try:
            container = self.docker_client.containers.get(container_name)
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            logger.warning(f"⚠️ Container '{container_name}' not found.")
        except docker.errors.APIError as e:
            logger.error(f"💥 Docker error removing container: {e}")

    def deploy_routing_layer_api(self) -> None:
        """
        Deploy the central routing layer API as a Docker container.
        """
        container_name = "serving-layer-router"

        try:
            self.docker_client.containers.get(container_name)
            logger.info("✅ Routing layer API already running.")
            return
        except docker.errors.NotFound:
            pass

        logger.info("🚀 Deploying routing layer API")

        env_vars = {
            "KSQLDB_URL": settings.ksqldb_url,
            "KAFKA_BROKER": settings.kafka_broker,
            "KSQLDB_ASSETS_STREAM": settings.ksqldb_assets_stream,
            "KSQLDB_UNS_MAP": settings.ksqldb_uns_map,
            "LOG_LEVEL": settings.log_level,
            "ENVIRONMENT": "production",
            "DEPLOYMENT_PLATFORM": "docker"
        }

        try:
            self.docker_client.containers.run(
                image=settings.routing_layer_image,
                name=container_name,
                detach=True,
                network=settings.docker_network,
                ports={"5555/tcp": 5555},
                environment=env_vars,
                cpu_quota=int(100000 * settings.routing_layer_cpus_limit),
                cpu_period=100000,
            )
        except docker.errors.APIError as e:
            logger.error(f"💥 Docker error launching routing layer API: {e}")

    def remove_routing_layer_api(self) -> None:
        """
        Remove the routing layer API container.
        """
        logger.info("Removing routing layer API container")
        try:
            container = self.docker_client.containers.get("serving-layer-router")
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            logger.warning("⚠️ Routing layer API container not found.")
        except docker.errors.APIError as e:
            logger.error(f"💥 Docker error removing routing layer API: {e}")

    def get_service_url(self, group_name: str) -> str:
        """
        Get the HTTP URL of the container exposing the FastAPI group service.

        Args:
            group_name (str): Group name.

        Returns:
            str: URL like http://localhost:<port>
        """
        if settings.environment == "local":
            return f"http://localhost:{self._get_host_port(group_name)}"
        return f"http://{self._container_name(group_name)}:5555"

    def deploy_state_api(self) -> None:
        """
        Deploy the centralized State API as a Docker container.
        """
        container_name = "openfactory-state-api"

        try:
            self.docker_client.containers.get(container_name)
            logger.info("✅ State API already running.")
            return
        except docker.errors.NotFound:
            pass

        logger.info("🚀 Deploying State API container")

        env_vars = {
            "KSQLDB_URL": settings.ksqldb_url,
            "KSQLDB_ASSETS_TABLE": settings.ksqldb_assets_table,
            "LOG_LEVEL": settings.log_level,
            "DEPLOYMENT_PLATFORM": "docker"
        }

        ports = {"5555/tcp": 5556} if settings.environment == "local" else {}

        try:
            self.docker_client.containers.run(
                image=settings.state_api_image,
                name=container_name,
                detach=True,
                network=settings.docker_network,
                ports=ports,
                environment=env_vars,
                cpu_quota=int(100000 * settings.state_api_cpus_limit),
                cpu_period=100000,
            )
        except docker.errors.APIError as e:
            logger.error(f"💥 Docker error launching State API: {e}")

    def remove_state_api(self) -> None:
        """
        Remove the State API Docker container.
        """
        logger.info("Removing State API container")
        try:
            container = self.docker_client.containers.get("openfactory-state-api")
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            logger.warning("⚠️  State API container not found.")
        except docker.errors.APIError as e:
            logger.error(f"💥  Docker error removing State API: {e}")

    def get_state_api_url(self) -> str:
        """
        Return the resolved internal or local URL of the State API.

        Returns:
            str: URL like http://localhost:5555 or internal Docker network address.
        """
        if settings.environment == "local":
            logger.info("Using local override for State API URL")
            return "http://localhost:5556"
        return "http://openfactory-state-api:5555"
