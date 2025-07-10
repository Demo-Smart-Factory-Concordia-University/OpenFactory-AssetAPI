# app/main.py
from fastapi import FastAPI
from app.api import asset_state

app = FastAPI()
app.include_router(asset_state.router)
