"""
Configuration Module
====================

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
    - KAFKA_BROKER: Kafka bootstrap server addresses (default: "localhost:9092")
    - KSQLDB_URL: URL to ksqlDB instance (default: "http://localhost:8088")
    - KSQLDB_ASSETS_TABLE: Name of the ksqlDB table for asset states (default: "assets")
    - KSQLDB_ASSETS_STREAM: Name of the ksqlDB stream for enriched asset data (default: "enriched_assets_stream")
    - KSQLDB_UNS_MAP: Name of the ksqlDB table mapping assets to UNS paths (default: "asset_to_uns_map")
    - DOCKER_NETWORK: Docker Swarm overlay network name (default: "factory-net")
    - FASTAPI_GROUP_IMAGE: Docker image for FastAPI group service (default: "openfactory/fastapi-group:latest")
    - LOG_LEVEL: Logging verbosity level (one of: "debug", "info", "warning", "error", "critical"; default: "info")
"""
import logging
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from openfactory.kafka import KSQLDBClient


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.

    Attributes:
        ksqldb_url (str): URL to the ksqlDB server.
            Env var: KSQLDB_URL. Default: "http://localhost:8088".
        ksqldb_assets_stream (str): Name of the ksqlDB stream for enriched assets.
            Env var: KSQLDB_ASSETS_STREAM. Default: "enriched_assets_stream".
        ksqldb_uns_map (str): Name of the ksqlDB table mapping assets to UNS hierarchy.
            Env var: KSQLDB_UNS_MAP. Default: "asset_to_uns_map".
        docker_network (str): Name of the Docker Swarm overlay network used for service communication.
            Env var: DOCKER_NETWORK. Default: "factory-net".
        fastapi_group_image (str): Docker image used for running group service replicas.
            Env var: FASTAPI_GROUP_IMAGE. Default: "openfactory/fastapi-group:latest".
        log_level (str): Logging level ("debug", "info", "warning", "error", "critical").
            Env var: LOG_LEVEL. Default: "info".
    """
    ksqldb_url: str = Field(default="http://localhost:8088", env="KSQLDB_URL")
    ksqldb_assets_stream: str = Field(default="enriched_assets_stream", env="KSQLDB_ASSETS_STREAM")
    ksqldb_uns_map: str = Field(default="asset_to_uns_map", env="KSQLDB_UNS_MAP")
    docker_network: str = Field(default="factory-net", env="DOCKER_NETWORK")
    fastapi_group_image: str = Field(default="openfactory/fastapi-group:latest", env="FASTAPI_GROUP_IMAGE")
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
