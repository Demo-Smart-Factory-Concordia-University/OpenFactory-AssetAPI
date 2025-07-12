# app/main.py
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.kafka_dispatcher import start_kafka_dispatcher, KafkaDispatcher
from app.api import asset_state
from app.api import asset_stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    dispatcher: KafkaDispatcher = start_kafka_dispatcher(loop)
    try:
        yield
    finally:
        # Wait for dispatcher to stop cleanly
        dispatcher.stop()

app = FastAPI(lifespan=lifespan)

app.include_router(asset_state.router)
app.include_router(asset_stream.router)
