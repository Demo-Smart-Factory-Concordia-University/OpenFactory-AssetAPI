# stream_api/non_replicated/main.py
import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from stream_api.non_replicated.config import settings
from stream_api.non_replicated.app.core.kafka_dispatcher import start_kafka_dispatcher, KafkaDispatcher
from stream_api.non_replicated.app.api import asset_stream


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
app.include_router(asset_stream.router)


def setup_logging():
    level = settings.log_level.upper()
    uvicorn_loggers = ["uvicorn.error", "uvicorn.access", "uvicorn"]
    for logger_name in uvicorn_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)


if __name__ == "__main__":
    setup_logging()
    uvicorn.run("stream_api.non_replicated.main:app",
                host="0.0.0.0", port=5555,
                reload=True,
                log_level=settings.log_level)
