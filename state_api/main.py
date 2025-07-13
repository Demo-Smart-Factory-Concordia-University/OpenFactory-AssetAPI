"""
Main application entrypoint for the OpenFactory State API.

This module creates and configures the FastAPI application,
including the registration of the asset_state router which exposes
the `/asset_state` REST endpoint to query the latest factory asset states.

It also launches the Uvicorn ASGI server when run as the main module,
using configuration values from the `settings` singleton.

Usage:
    Run locally for development:

        python -m state_api.main

    Or launch via Docker or other production orchestrators.

Environment variables from `state_api.config.Settings` control
behavior such as logging level and ksqlDB connection.
"""
import uvicorn
from fastapi import FastAPI
from state_api.config import settings
from state_api.app import asset_state


app = FastAPI(
    title="OpenFactory State API",
    description="Serving current state data of factory assets.",
)
app.include_router(asset_state.router)

if __name__ == "__main__":
    uvicorn.run("state_api.main:app",
                host="0.0.0.0", port=5555,
                reload=True,
                log_level=settings.log_level)
