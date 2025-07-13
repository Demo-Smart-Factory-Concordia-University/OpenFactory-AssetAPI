""" SSE endpoint for an OpenFactory Asset. """
import logging
from fastapi import APIRouter, Request, Query
from sse_starlette.sse import EventSourceResponse
from typing import Optional
import asyncio
import json
from stream_api.non_replicated.config import settings
from stream_api.non_replicated.app.core.kafka_dispatcher import subscriptions


logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.get("/asset_stream")
async def stream_asset_state(
    request: Request,
    asset_uuid: str = Query(...),
    dataitem_id: Optional[str] = Query(None, alias="id")
):
    """
    Stream real-time updates for a given Asset (or specific Asset DataItem).

    Streams messages from the asyncio subscriber queues via SSE.
    Filters by DataItem ID if specified by the client.

    Args:
        request (Request): The incoming client request, used to detect disconnects.
        asset_uuid (str): UUID of the Asset.
        dataitem_id (Optional[str]): ID of the DataItem (optional).

    Returns:
        SSE stream of JSON messages.

    Examples:
        Stream all DataItems for an Asset:

        ```
        GET /asset_stream?asset_uuid=PROVER3018
        ```

        Stream only the DataItem with ID 'Zact' from a specific Asset:

        ```
        GET /asset_stream?asset_uuid=PROVER3018&id=Zact
        ```
    """
    queue = asyncio.Queue(maxsize=settings.queue_maxsize)
    subscriptions[asset_uuid].append(queue)
    logger.info(f"[SSE] Client subscribed to {asset_uuid}")

    async def event_generator():
        try:
            while not await request.is_disconnected():
                msg = await queue.get()
                try:
                    if dataitem_id:
                        parsed = json.loads(msg)
                        if parsed.get("id") != dataitem_id:
                            continue  # skip non-matching dataitem_id
                    yield {
                        "event": "asset_update",
                        "data": msg
                    }
                except Exception as e:
                    logger.error(f"[SSE] Failed to process message: {e}")
        finally:
            if queue in subscriptions.get(asset_uuid, []):
                subscriptions[asset_uuid].remove(queue)
            if not subscriptions.get(asset_uuid):
                subscriptions.pop(asset_uuid, None)
            logger.info(f"[SSE] Client disconnected from {asset_uuid}")

    return EventSourceResponse(event_generator())
