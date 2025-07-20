"""
Upstream Proxy Module for OpenFactory Routing Layer.

This module defines the `asset_stream_proxy` function used to forward client
requests to the appropriate group-specific FastAPI service responsible for
streaming asset data.

It opens a streaming connection (`text/event-stream`) to the target URL,
forwards client disconnection signals, and handles basic upstream error reporting.

The proxy expects:
- A valid full URL pointing to a group-specific endpoint.
- The incoming request context to detect client disconnections.

Responsibilities:
- Forward SSE streams transparently from upstream services.
- Handle upstream connection errors and emit appropriate error events.
- Respect client disconnections to avoid unnecessary load.

Used by:
    - The `/asset_stream` endpoint in `router_asset.py`.
"""

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse
import httpx
import logging

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/asset_stream")
async def asset_stream_proxy(request: Request, full_url: str) -> StreamingResponse:
    """
    Proxy an incoming asset stream request to a downstream service.

    This function establishes a streaming connection to the given `full_url`,
    reads the response as a stream of SSE lines, and relays them back to the client.

    It also:
    - Detects and handles upstream HTTP errors.
    - Stops streaming if the client disconnects.
    - Forwards error events to the client if proxying fails.

    Args:
        request (Request): The incoming FastAPI request, used to detect disconnections.
        full_url (str): The full URL to the target downstream group service.

    Returns:
        StreamingResponse: A streaming response object that pipes data from upstream.

    Yields:
        bytes: SSE-compatible messages encoded as bytes.

    Example:
        GET /asset_stream?asset_uuid=...
    """
    async def sse_stream():
        logger.debug(f"[proxy] Will forward to {full_url}")
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("GET", full_url, headers={"Accept": "text/event-stream"}) as response:
                    if response.status_code != 200:
                        content = await response.aread()
                        logger.error(f"[proxy] Upstream error: {response.status_code} - {content}")
                        yield f"event: error\ndata: {content.decode()}\n\n".encode()
                        return

                    logger.info("[proxy] Connected to SSE upstream")

                    async for line in response.aiter_lines():
                        if await request.is_disconnected():
                            logger.info("[proxy] Client disconnected")
                            break

                        if line.strip():
                            logger.debug(f"[proxy][SSE] {line}")
                            yield (line + "\n").encode()

                    logger.info("[proxy] Upstream stream ended")

            except Exception as e:
                logger.exception(f"[proxy] Error streaming from upstream: {e}")
                yield f"event: error\ndata: {str(e)}\n\n".encode()

    return StreamingResponse(sse_stream(), media_type="text/event-stream")


async def read_and_log_sse_stream(request: Request, full_url: str):
    async def sse_iterator():
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("GET", full_url, headers={"Accept": "text/event-stream"}) as response:
                    if response.status_code != 200:
                        content = await response.aread()
                        logger.error(f"[proxy] Upstream error: {response.status_code} - {content}")
                        yield f"event: error\ndata: {content.decode()}\n\n".encode()
                        return

                    logger.info("[proxy] Connected to upstream SSE")

                    async for line in response.aiter_lines():
                        if await request.is_disconnected():
                            logger.info("[proxy] Client disconnected")
                            break

                        if line.strip():
                            logger.info(f"[proxy][SSE] {line}")
                            yield (line + "\n").encode()

            except Exception as e:
                logger.exception("[proxy] Exception while streaming SSE")
                yield f"event: error\ndata: {str(e)}\n\n".encode()

    return StreamingResponse(sse_iterator(), media_type="text/event-stream")
