# app/main.py
from fastapi import FastAPI
from app.api import asset_state
from app.api import asset_stream

app = FastAPI()
app.include_router(asset_state.router)
app.include_router(asset_stream.router)
