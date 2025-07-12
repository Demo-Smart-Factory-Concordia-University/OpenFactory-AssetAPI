# app/main.py
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.kafka_dispatcher import start_kafka_dispatcher
from app.api import asset_state
from app.api import asset_stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    start_kafka_dispatcher(loop)
    yield
    # Optionally: add any cleanup code here on shutdown

app = FastAPI(lifespan=lifespan)

app.include_router(asset_state.router)
app.include_router(asset_stream.router)
