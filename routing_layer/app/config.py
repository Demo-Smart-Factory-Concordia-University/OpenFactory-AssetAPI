"""
Configuration Module for Routing Layer
======================================

This module defines the configuration settings for the Routing Layer.

It uses Pydantic's `BaseSettings` to load configuration values from environment variables,
supporting easy integration with deployment tooling and environment management systems.

For local development, environment variables can be defined in a `.env` file located at the project root.

Unknown environment variables are ignored to allow shared `.env` files across multiple services.

Usage:
    Import the singleton `settings` object from this module to access configuration values
    throughout the application.

    .. code-block:: python
        from routing_layer.app.config import settings

        print(settings.ksqldb_url)

Environment Variables:

Kafka & ksqlDB:
    - `KAFKA_BROKER`: Kafka bootstrap server address (default: "localhost:9092")
    - `KSQLDB_URL`: URL of the ksqlDB server (default: "http://localhost:8088")
    - `KSQLDB_ASSETS_STREAM`: Name of the enriched asset stream (default: "enriched_assets_stream")
    - `KSQLDB_ASSETS_TABLE`: Table containing the current asset state (default: "assets")
    - `KSQLDB_UNS_MAP`: Name of the UNS map table in ksqlDB (default: "asset_to_uns_map")

FastAPI Group Services:
    - `FASTAPI_GROUP_IMAGE`: Docker image for group service containers
    - `FASTAPI_GROUP_REPLICAS`: Number of service replicas per group (default: 1)
    - `FASTAPI_GROUP_CPU_LIMIT`: CPU limit per group service (default: 1)
    - `FASTAPI_GROUP_CPU_RESERVATION`: CPU reservation per group service (default: 0.5)
    - `FASTAPI_GROUP_PORT_BASE`: Base host port to expose group services in local dev (default: 6000)
    - `UNS_FASTAPI_GROUP_GROUPING_LEVEL`: Grouping level for UNS-based FastAPI services, e.g., "workcenter" (default: "workcenter")

Routing Layer API:
    - `ROUTING_LAYER_IMAGE`: Docker image of the central routing layer API
    - `ROUTING_LAYER_REPLICAS`: Number of routing layer replicas to deploy (default: 1)
    - `ROUTING_LAYER_CPU_LIMIT`: CPU limit per routing layer container (default: 1)
    - `ROUTING_LAYER_CPU_RESERVATION`: CPU reservation per routing layer container (default: 0.5)

State API (used for asset state lookups):
    - `STATE_API_IMAGE`: Docker image for the state API service
    - `STATE_API_REPLICAS`: Number of replicas for the state API (default: 1)
    - `STATE_API_CPU_LIMIT`: CPU limit per state API container (default: 0.5)
    - `STATE_API_CPU_RESERVATION`: CPU reservation per state API container (default: 0.25)

Platform & Deployment Strategy:
    - `DOCKER_NETWORK`: Docker Swarm overlay network name (default: "factory-net")
    - `SWARM_NODE_HOST`: Host or IP address of the Swarm manager node (default: "localhost")
    - `DEPLOYMENT_PLATFORM`: Deployment backend to use: "docker", "swarm", etc. (default: "swarm")
    - `GROUPING_STRATEGY`: Asset grouping strategy, e.g., "workcenter" (default: "workcenter")

Environment & Logging:
    - `ENVIRONMENT`: Current environment ("local", "dev", "devswarm", or "production"; default: "production")
    - `LOG_LEVEL`: Logging level ("debug", "info", "warning", "error", "critical"; default: "info")
"""

import logging
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from openfactory.kafka import KSQLDBClient


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.

    Attributes:
        kafka_broker (str): Kafka bootstrap server addresses, e.g., "localhost:9092".
            Environment variable: `KAFKA_BROKER`
        ksqldb_url (str): URL of the ksqlDB server.
            Environment variable: `KSQLDB_URL`. Default: "http://localhost:8088".
        ksqldb_assets_stream (str): Name of the ksqlDB stream for enriched asset data.
            Environment variable: `KSQLDB_ASSETS_STREAM`. Default: "enriched_assets_stream".
        ksqldb_assets_table (str): Name of the table containing raw or processed assets.
            Environment variable: `KSQLDB_ASSETS_TABLE`.
        ksqldb_uns_map (str): Name of the table mapping assets to UNS paths in ksqlDB.
            Environment variable: `KSQLDB_UNS_MAP`. Default: "asset_to_uns_map".
        docker_network (str): Docker Swarm network used for deploying group services.
            Environment variable: `DOCKER_NETWORK`. Default: "factory-net".
        swarm_node_host (str): Host or IP address of the Swarm manager node (used for local proxying).
            Environment variable: `SWARM_NODE_HOST`. Default: "localhost".
        routing_layer_image (str): Docker image of the central routing layer API.
            Environment variable: `ROUTING_LAYER_IMAGE`.
            Default: "ghcr.io/demo-smart-factory-concordia-university/routing-layer:latest".
        routing_layer_replicas (int): Number of routing layer service replicas.
            Environment variable: `ROUTING_LAYER_REPLICAS`
        routing_layer_cpus_limit (float): CPU limit per routing layer container.
            Environment variable: `ROUTING_LAYER_CPU_LIMIT`
        routing_layer_cpus_reservation (float): CPU reservation per routing layer container.
            Environment variable: `ROUTING_LAYER_CPU_RESERVATION`
        fastapi_group_image (str): Docker image to use for group service containers.
            Environment variable: `FASTAPI_GROUP_IMAGE`.
            Default: "ghcr.io/demo-smart-factory-concordia-university/stream-api-non-replicated:latest".
        fastapi_group_replicas (int): Number of service replicas per group.
            Environment variable: `FASTAPI_GROUP_REPLICAS`. Default: 3.
        fastapi_group_cpus_limit (float): CPU limit per group container.
            Environment variable: `FASTAPI_GROUP_CPU_LIMIT`. Default: 1.
        fastapi_group_cpus_reservation (float): CPU reservation per group container.
            Environment variable: `FASTAPI_GROUP_CPU_RESERVATION`. Default: 0.5.
        fastapi_group_host_port_base (int): Base host port to publish services for local development.
            Environment variable: `FASTAPI_GROUP_PORT_BASE`. Default: 6000.
        uns_fastapi_group_grouping_level (str): Grouping level for UNS-based FastAPI group services.
            Determines how services are grouped, e.g., by "workcenter".
            Environment variable: `UNS_FASTAPI_GROUP_GROUPING_LEVEL`
        state_api_image (str): Docker image to use for the asset state API service.
            Environment variable: `STATE_API_IMAGE`.
            Default: "ghcr.io/demo-smart-factory-concordia-university/state-api:latest".
        state_api_replicas (int): Number of replicas for the asset state API service.
            Environment variable: `STATE_API_REPLICAS`. Default: 1.
        state_api_cpus_limit (float): CPU limit per asset state API container.
            Environment variable: `STATE_API_CPU_LIMIT`. Default: 0.5.
        state_api_cpus_reservation (float): CPU reservation per asset state API container.
            Environment variable: `STATE_API_CPU_RESERVATION`. Default: 0.25.
        log_level (str): Logging verbosity level for the service.
            Environment variable: `LOG_LEVEL`. Default: "info".
        environment (str): Environment the app is running in ("local", "dev", "devswarm", or "production").
            Environment variable: `ENVIRONMENT`. Default: "production".
        grouping_strategy (str): Strategy for grouping assets (e.g., "workcenter").
            Environment variable: `GROUPING_STRATEGY`. Default: "workcenter".
        deployment_platform (str): Deployment mode, either "swarm" or "docker".
            Environment variable: `DEPLOYMENT_PLATFORM`. Default: "swarm".
    """

    # Kafka & ksqlDB
    kafka_broker: str = Field(default="localhost:9092", env="KAFKA_BROKER")
    ksqldb_url: str = Field(default="http://localhost:8088", env="KSQLDB_URL")
    ksqldb_assets_stream: str = Field(default="enriched_assets_stream", env="KSQLDB_ASSETS_STREAM")
    ksqldb_assets_table: str = Field(default="assets", env="KSQLDB_ASSETS_TABLE")
    ksqldb_uns_map: str = Field(default="asset_to_uns_map", env="KSQLDB_UNS_MAP")

    # Docker & Swarm
    docker_network: str = Field(default="factory-net", env="DOCKER_NETWORK")
    swarm_node_host: str = Field(default="localhost", env="SWARM_NODE_HOST")

    # Routing layer API
    routing_layer_image: str = Field(
        default="ghcr.io/demo-smart-factory-concordia-university/routing-layer:latest",
        env="ROUTING_LAYER_IMAGE")
    routing_layer_replicas: int = Field(default=1, env="ROUTING_LAYER_REPLICAS")
    routing_layer_cpus_limit: float = Field(default=1, env="ROUTING_LAYER_CPU_LIMIT")
    routing_layer_cpus_reservation: float = Field(default=0.5, env="ROUTING_LAYER_CPU_RESERVATION")
    grouping_strategy: str = Field(default="workcenter", env="GROUPING_STRATEGY")
    deployment_platform: str = Field(default="swarm", env="DEPLOYMENT_PLATFORM")

    # FastAPI Group Services
    fastapi_group_image: str = Field(
        default="ghcr.io/demo-smart-factory-concordia-university/stream-api-non-replicated:latest",
        env="FASTAPI_GROUP_IMAGE")
    fastapi_group_replicas: int = Field(default=1, env="FASTAPI_GROUP_REPLICAS")
    fastapi_group_cpus_limit: float = Field(default=1, env="FASTAPI_GROUP_CPU_LIMIT")
    fastapi_group_cpus_reservation: float = Field(default=0.5, env="FASTAPI_GROUP_CPU_RESERVATION")
    fastapi_group_host_port_base: int = Field(default=6000, env="FASTAPI_GROUP_PORT_BASE")
    uns_fastapi_group_grouping_level: str = Field(default='workcenter', env='UNS_FASTAPI_GROUP_GROUPING_LEVEL')

    # State API
    state_api_image: str = Field(
        default="ghcr.io/demo-smart-factory-concordia-university/state-api:latest",
        env="STATE_API_IMAGE")
    state_api_replicas: int = Field(default=1, env="STATE_API_REPLICAS")
    state_api_cpus_limit: float = Field(default=0.5, env="STATE_API_CPU_LIMIT")
    state_api_cpus_reservation: float = Field(default=0.25, env="STATE_API_CPU_RESERVATION")

    # Miscellaneous
    log_level: str = Field(default="info", env="LOG_LEVEL")
    environment: str = Field(default="production", env="ENVIRONMENT")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        allowed = {"debug", "info", "warning", "error", "critical"}
        level = v.lower()
        if level not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        logging.getLogger("uvicorn.error").setLevel(level.upper())
        return level

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        allowed = {"local", "dev", "devswarm", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v.lower()


# Singleton settings object
settings = Settings()
ksql = KSQLDBClient(settings.ksqldb_url)
