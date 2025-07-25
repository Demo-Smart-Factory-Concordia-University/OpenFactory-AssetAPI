"""
Asset State Routing Endpoint for OpenFactory Routing Layer.

This module defines the `/asset_state` endpoint, which proxies client requests
to the centralized asset state API service. It uses deployment platform utilities
to resolve the service's location and proxies the request transparently.

Responsibilities:
- Forward all relevant query parameters to the downstream Asset State API.
- Preserve method and headers for full request fidelity.
- Return the exact response (status code + content) from the backend.

Raises:
    - HTTP 404: If the state API is unreachable or misconfigured.
    - HTTP 502: If the proxy fails to connect to the backend service.
"""

import logging
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from urllib.parse import urlencode
from typing import Optional
from routing_layer.app.dependencies import routing_controller

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/asset_state", tags=["Asset State"])
async def route_asset_state(request: Request, asset_uuid: str) -> JSONResponse:
    """
    Proxy client requests for asset state data to the centralized state API.

    This endpoint:
    - Receives an asset UUID and other filters as query parameters.
    - Forwards the request to the downstream State API.
    - Returns the streamed or JSON response back to the client.

    Args:
        request (Request): The incoming FastAPI request object.
        asset_uuid (str): The UUID of the asset.

    Returns:
        StreamingResponse: The response from the State API.

    Raises:
        HTTPException:
            - 404 if the target API cannot be resolved.
            - 502 if the proxy fails to connect to the backend.
    """
    logger.debug(f"[router] Proxying asset state for UUID: {asset_uuid}")

    # Get the base URL from the deployment platform
    target_base_url: Optional[str] = routing_controller.deployment_platform.get_state_api_url()
    logger.debug(f"[router] Baser URL: {target_base_url}")
    if not target_base_url:
        logger.error("[router] Asset State API route could not be resolved.")
        raise HTTPException(status_code=404, detail="Asset State API not available.")

    # Allowed query parameters to forward (extend this list as needed)
    allowed_params = {"asset_uuid", "id", "start_time", "end_time", "granularity"}
    filtered_params = {k: v for k, v in request.query_params.items() if k in allowed_params}

    # Construct full downstream URL
    query_string = urlencode(filtered_params)
    full_url = f"{target_base_url}/asset_state"
    if query_string:
        full_url = f"{full_url}?{query_string}"

    logger.debug(f"[router] Forwarding request to: {full_url}")

    # Proxy the request
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            proxy_response = await client.get(full_url, headers=dict(request.headers))

        return JSONResponse(
            status_code=proxy_response.status_code,
            content=proxy_response.json()
        )

    except httpx.RequestError as e:
        logger.exception(f"[router] HTTPX error proxying to State API: {e}")
        raise HTTPException(status_code=502, detail="Error contacting the State API.")
    except Exception as e:
        logger.exception(f"[router] Unexpected error proxying to State API: {e}")
        raise HTTPException(status_code=502, detail="Unexpected error proxying to State API.")
