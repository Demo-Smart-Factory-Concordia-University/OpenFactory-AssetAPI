"""
State API Configuration Module
==============================

This module defines the configuration settings for the Asset state API service.

It uses Pydantic's `BaseSettings` to load configuration values from environment variables,
supporting easy integration with deployment tooling and environment management systems.

For local development, environment variables can be defined in a `.env` file located at the project root.

Unknown environment variables are ignored to allow shared `.env` files across multiple services.

Usage:
    Import the singleton `settings` object from this module to access configuration values
    throughout the application.

    .. code-block:: python
        from state_api.config import settings

        print(settings.ksqldb_url)

Environment Variables:
    - `KSQLDB_URL`: URL to ksqlDB.
    - `LOG_LEVEL`: Logging verbosity level.

Note:
    Ensure that your deployment environment or tool provides all required environment variables
    before starting the application.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from openfactory.kafka import KSQLDBClient


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.

    All configuration values should be provided via environment variables
    by the deployment tool or environment management system. Defaults are
    provided for local development convenience.

    Attributes:
        ksqldb_url (str): URL to ksqlDB. Environment variable: KSQLDB_URL
        ksqldb_assets_table (str): ksqlDB tables with Assets states. Environment variable: KSQLDB_ASSETS_TABLE
        log_level (str): Logging level, e.g., "info", "debug", "warning".
            Environment variable: LOG_LEVEL

    Note:
        - The deployment tool is responsible for setting these environment variables.
        - For local development, values can be set in a `.env` file located at the project root.
        - Unknown environment variables are ignored to allow sharing config files among multiple services.
    """
    ksqldb_url: str = Field(default="http://localhost:8088", env="KSQLDB_URL")
    ksqldb_assets_table: str = Field(default="assets", env="KSQLDB_ASSETS_TABLE")
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


# Singleton settings and ksql object
settings = Settings()
ksql = KSQLDBClient(settings.ksqldb_url)
