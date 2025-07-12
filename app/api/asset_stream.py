from fastapi import APIRouter, Request, Query
from sse_starlette.sse import EventSourceResponse
from typing import Optional
import asyncio
import json
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
    Filters by DataItem ID if specified by the client.

    Args:
        request (Request): The incoming client request, used to detect disconnects.
        asset_uuid (str): UUID of the asset.
        id (Optional[str]): ID of the DataItem (optional).

    Returns:
        SSE stream of JSON messages.

    Examples:
        Stream all DataItems for an asset:

        ```
        GET /asset_stream?asset_uuid=PROVER3018
        ```

        Stream only the DataItem with ID 'Zact' from a specific asset:

        ```
        GET /asset_stream?asset_uuid=PROVER3018&id=Zact
        ```
    """
    queue = asyncio.Queue()
    subscriptions[asset_uuid].append(queue)
    print(f"[SSE] Client subscribed to {asset_uuid}")

    async def event_generator():
        try:
            while not await request.is_disconnected():
                msg = await queue.get()
                try:
                    if id:
                        parsed = json.loads(msg)
                        if parsed.get("id") != id:
                            continue  # skip non-matching ID
                    yield {
                        "event": "asset_update",
                        "data": msg
                    }
                except Exception as e:
                    print(f"[SSE] Failed to process message: {e}")
        finally:
            subscriptions[asset_uuid].remove(queue)
            if not subscriptions[asset_uuid]:
                del subscriptions[asset_uuid]
            print(f"[SSE] Client disconnected from {asset_uuid}")

    return EventSourceResponse(event_generator())
