"""
Stream API Configuration Module
===============================

This module defines the configuration settings for the non-replicated streaming API service.

It uses Pydantic's `BaseSettings` to load configuration values from environment variables,
supporting easy integration with deployment tooling and environment management systems.

Configuration values include Kafka connection details, consumer group ID, internal queue sizes,
and logging levels.

For local development, environment variables can be defined in a `.env` file located at the project root.

Unknown environment variables are ignored to allow shared `.env` files across multiple services.

Usage:
    Import the singleton `settings` object from this module to access configuration values
    throughout the application.

    .. code-block:: python
        from stream_api.non_replicated.config import settings

        print(settings.kafka_bootstrap)
        print(settings.kafka_topic)

Environment Variables:
    - `KAFKA_BOOTSTRAP`: Kafka bootstrap server addresses.
    - `KAFKA_TOPIC`: Kafka topic to consume from.
    - `KAFKA_CONSUMER_GROUP_ID`: Kafka consumer group identifier.
    - `QUEUE_MAXSIZE`: Maximum size of the internal Kafka message queue.
    - `LOG_LEVEL`: Logging verbosity level.

Note:
    Ensure that your deployment environment or tool provides all required environment variables
    before starting the application.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.

    All configuration values should be provided via environment variables
    by the deployment tool or environment management system. Defaults are
    provided for local development convenience.

    Attributes:
        kafka_bootstrap (str): Kafka bootstrap server addresses, e.g., "localhost:9092".
            Environment variable: KAFKA_BOOTSTRAP
        kafka_topic (str): Kafka topic to consume from, e.g., "ofa_assets".
            Environment variable: KAFKA_TOPIC
        kafka_consumer_group_id (str): Kafka consumer group ID for managing offset commits and partition assignment.
            Should be unique per deployed service instance group to ensure proper load balancing.
            Example: "ofa_openfactory-stream-api-non-replicated-sharedassets".
            Environment variable: KAFKA_CONSUMER_GROUP_ID
        queue_maxsize (int): Maximum size of the internal message queue used to buffer Kafka messages before streaming.
            Environment variable: QUEUE_MAXSIZE
        log_level (str): Logging level, e.g., "info", "debug", "warning".
            Environment variable: LOG_LEVEL

    Note:
        - The deployment tool is responsible for setting these environment variables.
        - For local development, values can be set in a `.env` file located at the project root.
        - Unknown environment variables are ignored to allow sharing config files among multiple services.
    """
    kafka_broker: str = Field(default="localhost:9092", env="KAFKA_BROKER")
    kafka_topic: str = Field(default="ofa_assets", env="KAFKA_TOPIC")
    kafka_consumer_group_id: str = Field(default="ofa_openfactory-stream-api-non-replicated-sharedassets",
                                         env="KAFKA_CONSUMER_GROUP_ID")
    queue_maxsize: int = Field(default=1000, env="QUEUE_MAXSIZE")
    log_level: str = Field(default="info", env="LOG_LEVEL")

    model_config = {
        "env_file": ".env",               # can be used for local development
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        allowed = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.lower()


# Singleton settings object
settings = Settings()
