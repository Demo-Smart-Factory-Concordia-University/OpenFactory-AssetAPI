from fastapi import APIRouter, Request, Query
from sse_starlette.sse import EventSourceResponse
from typing import Optional
import asyncio
from app.core.kafka_consumer import build_kafka_consumer, poll_messages

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
        asset_uuid (str): UUID of the asset.
        id (Optional[str]): ID of the DataItem (optional).

    Returns:
        SSE stream of JSON messages.
    """
    key_prefix = f"{asset_uuid}|{id}" if id else f"{asset_uuid}|"
    consumer = build_kafka_consumer("enriched_assets_stream_topic")

    async def event_generator():
        try:
            for message in await asyncio.to_thread(lambda: poll_messages(consumer, key_prefix)):
                if await request.is_disconnected():
                    break
                yield {
                    "event": "asset_update",
                    "data": message
                }
        finally:
            consumer.close()

    return EventSourceResponse(event_generator())
