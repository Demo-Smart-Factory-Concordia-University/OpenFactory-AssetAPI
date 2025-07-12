from fastapi import APIRouter, Request, Query
from sse_starlette.sse import EventSourceResponse
from typing import Optional
import asyncio
from app.core.kafka_dispatcher import subscriptions

router = APIRouter()


@router.get("/asset_stream")
async def stream_asset_state(
    request: Request,
    asset_uuid: str = Query(...),
    id: Optional[str] = Query(None)
):
    """
    Stream real-time updates for a given asset (or specific DataItem).

    Streams messages from the enriched_assets_stream_topic Kafka topic via SSE.

    Args:
        request (Request): The incoming client request, used to detect disconnects.
        asset_uuid (str): UUID of the asset.
        id (Optional[str]): ID of the DataItem (optional).

    Returns:
        SSE stream of JSON messages.
    """
    key_prefix = f"{asset_uuid}|{id}" if id else f"{asset_uuid}|"
    queue = asyncio.Queue()
    subscriptions[key_prefix].append(queue)
    print(f"[SSE] Client subscribed to {key_prefix}")

    async def event_generator():
        try:
            while not await request.is_disconnected():
                msg = await queue.get()
                yield {
                    "event": "asset_update",
                    "data": msg
                }
        finally:
            subscriptions[key_prefix].remove(queue)
            if not subscriptions[key_prefix]:
                del subscriptions[key_prefix]
            print(f"[SSE] Client disconnected from {key_prefix}")

    return EventSourceResponse(event_generator())
