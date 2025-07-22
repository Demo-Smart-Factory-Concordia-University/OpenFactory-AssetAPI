"""
Asset Stream Routing Endpoint for OpenFactory Routing Layer.

This module defines the `/asset_stream` endpoint, which is responsible for routing
and proxying client requests to the appropriate group-specific service instance based
on the asset's UUID.

It delegates:
- Group resolution and routing logic to the `routing_controller`.
- Streaming the request to the downstream service via `asset_stream_proxy`.

This endpoint supports streaming protocols (e.g., Server-Sent Events),
making it suitable for real-time data delivery.

Endpoints:
    - GET /asset_stream?asset_uuid=... : Proxies the request to the correct group service.

Raises:
    - HTTP 404: If the asset UUID is not mapped to any group.
    - HTTP 502: If the proxy operation fails due to upstream errors.
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
from urllib.parse import urlencode
from typing import Union
from routing_layer.app.dependencies import routing_controller
from routing_layer.app.core.proxy import asset_stream_proxy

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/asset_stream", tags=["Asset Stream"], response_model=None)
async def route_asset_stream(request: Request, asset_uuid: str) -> Union[StreamingResponse, JSONResponse]:
    """
    Route client requests for asset data streams.

    This endpoint:
    - Receives an asset UUID as a query parameter.
    - Uses the routing controller to find the appropriate group-specific service URL.
    - Proxies the incoming request to the corresponding downstream service, preserving all query parameters.

    Args:
        request (Request): The incoming HTTP request object.
        asset_uuid (str): The UUID of the asset to route.

    Raises:
        HTTPException 404: If no group service is found for the given asset UUID.

    Returns:
        StreamingResponse: A streamed response proxying data from the downstream service.
    """
    logger.debug(f"[router] Received asset_uuid: {asset_uuid}")

    # Resolve target base URL from routing controller
    target_url = routing_controller.handle_client_request(asset_uuid)
    if not target_url:
        logger.warning(f"[router] No route found for asset_uuid {asset_uuid}")
        raise HTTPException(status_code=404, detail="Asset group not found")

    # Filter query parameters: whitelist only allowed keys to forward (e.g., 'asset_uuid', 'id', etc.)
    allowed_params = {"asset_uuid", "id", "start_time", "end_time"}  # example allowed keys
    filtered_params = {k: v for k, v in request.query_params.items() if k in allowed_params}

    query_string = urlencode(filtered_params)
    full_url = f"{target_url}/asset_stream?{query_string}" if query_string else target_url

    # Call proxy_request to stream upstream response
    try:
        return await asset_stream_proxy(request, full_url)
    except Exception as e:
        logger.exception(f"[router] Error proxying request to {full_url}: {e}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Failed to proxy request to group service"}
        )
