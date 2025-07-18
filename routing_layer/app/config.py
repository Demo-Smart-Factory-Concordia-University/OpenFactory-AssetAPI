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
    - `KAFKA_BROKER`: Kafka bootstrap server address (default: "localhost:9092")
    - `KSQLDB_URL`: URL of the ksqlDB server (default: "http://localhost:8088")
    - `KSQLDB_ASSETS_STREAM`: Name of the enriched asset stream (default: "enriched_assets_stream")
    - `KSQLDB_UNS_MAP`: Name of the UNS map table in ksqlDB (default: "asset_to_uns_map")
    - `DOCKER_NETWORK`: Docker Swarm overlay network name (default: "factory-net")
    - `FASTAPI_GROUP_IMAGE`: Docker image for group service containers (default: "openfactory/fastapi-group:latest")
    - `FASTAPI_GROUP_REPLICAS`: Number of service replicas per group (default: 3)
    - `FASTAPI_GROUP_CPU_LIMIT`: CPU limit per group service (default: 1)
    - `FASTAPI_GROUP_CPU_RESERVATION`: CPU reservation per group service (default: 0.5)
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
        kafka_bootstrap (str): Kafka bootstrap server addresses, e.g., "localhost:9092".
            Environment variable: `KAFKA_BOOTSTRAP`
        ksqldb_url (str): URL of the ksqlDB server.
            Environment variable: `KSQLDB_URL`. Default: "http://localhost:8088".
        ksqldb_assets_stream (str): Name of the ksqlDB stream for enriched asset data.
            Environment variable: `KSQLDB_ASSETS_STREAM`. Default: "enriched_assets_stream".
        ksqldb_uns_map (str): Name of the table mapping assets to UNS paths in ksqlDB.
            Environment variable: `KSQLDB_UNS_MAP`. Default: "asset_to_uns_map".
        docker_network (str): Docker Swarm network used for deploying group services.
            Environment variable: `DOCKER_NETWORK`. Default: "factory-net".
        fastapi_group_image (str): Docker image to use for group service containers.
            Environment variable: `FASTAPI_GROUP_IMAGE`. Default: "openfactory/fastapi-group:latest".
        fastapi_group_replicas (int): Number of service replicas per group.
            Environment variable: `FASTAPI_GROUP_REPLICAS`. Default: 3.
        fastapi_group_cpus_limit (float): CPU limit per group container.
            Environment variable: `FASTAPI_GROUP_CPU_LIMIT`. Default: 1.
        fastapi_group_cpus_reservation (float): CPU reservation per group container.
            Environment variable: `FASTAPI_GROUP_CPU_RESERVATION`. Default: 0.5.
        log_level (str): Logging verbosity level for the service.
            Environment variable: `LOG_LEVEL`. Default: "info".
    """
    kafka_broker: str = Field(default="localhost:9092", env="KAFKA_BROKER")
    ksqldb_url: str = Field(default="http://localhost:8088", env="KSQLDB_URL")
    ksqldb_assets_stream: str = Field(default="enriched_assets_stream", env="KSQLDB_ASSETS_STREAM")
    ksqldb_uns_map: str = Field(default="asset_to_uns_map", env="KSQLDB_UNS_MAP")
    docker_network: str = Field(default="factory-net", env="DOCKER_NETWORK")
    fastapi_group_image: str = Field(default="openfactory/fastapi-group:latest", env="FASTAPI_GROUP_IMAGE")
    fastapi_group_replicas: int = Field(default=3, env="FASTAPI_GROUP_REPLICAS")
    fastapi_group_cpus_limit: float = Field(default=1, env="FASTAPI_GROUP_CPU_LIMIT")
    fastapi_group_cpus_reservation: float = Field(default=0.5, env="FASTAPI_GROUP_CPU_RESERVATION")
    log_level: str = Field(default="info", env="LOG_LEVEL")

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


# Singleton settings object
settings = Settings()
ksql = KSQLDBClient(settings.ksqldb_url)
