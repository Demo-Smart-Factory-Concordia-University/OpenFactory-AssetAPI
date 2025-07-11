from fastapi import APIRouter, Request, Query
from sse_starlette.sse import EventSourceResponse
from typing import Optional
import asyncio
import threading
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
        request (Request): The incoming client request, used to detect disconnects.
        asset_uuid (str): UUID of the asset.
        id (Optional[str]): ID of the DataItem (optional).

    Returns:
        SSE stream of JSON messages.
    """
    key_prefix = f"{asset_uuid}|{id}" if id else f"{asset_uuid}|"
    print(f"[stream_asset_state] Using key_prefix = {key_prefix}")

    consumer = build_kafka_consumer("enriched_assets_stream_topic")
    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    stop_event = threading.Event()

    def background_polling():
        """
        Runs in a background thread to consume Kafka messages using a blocking poll.

        Messages that match the given key_prefix are pushed into the asyncio queue,
        so they can be streamed asynchronously to the client via SSE.

        This avoids blocking the FastAPI event loop with Kafka operations.
        """
        try:
            for msg in poll_messages(consumer, key_prefix):
                if stop_event.is_set():
                    break
                # Push message into the async queue from this thread
                future = asyncio.run_coroutine_threadsafe(queue.put(msg), loop)
                try:
                    future.result(timeout=2)
                except Exception as e:
                    print(f"[polling thread] Failed to queue message: {e}")
        finally:
            print("[polling thread] Closing Kafka consumer.")
            consumer.close()

    # Start the Kafka polling loop in a dedicated background thread.
    # This isolates blocking operations and gives us explicit control.
    thread = threading.Thread(target=background_polling, daemon=True)
    thread.start()

    async def event_generator():
        """
        Async generator that yields Kafka messages as SSE events.
        Pulls messages from the asyncio queue filled by the background polling thread.
        """
        try:
            while not await request.is_disconnected():
                msg = await queue.get()
                yield {
                    "event": "asset_update",
                    "data": msg
                }
        finally:
            # Ensure cleanup on client disconnect
            print("[event_generator] Client disconnected. Cleaning up.")
            stop_event.set()
            thread.join(timeout=5)
            print("[event_generator] Done.")

    return EventSourceResponse(event_generator())
