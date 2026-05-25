# File: backend/app.py
"""Enterprise HR Insights 360 — FastAPI Backend v2.0"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.config import FRONTEND_DIR
from backend.core.db import init_db
from backend.routes.api import router as api_router

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FRONTEND_DIR = os.path.join(_BASE_DIR, "frontend")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="HR Insights 360 API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/frontend", StaticFiles(directory=_FRONTEND_DIR), name="frontend")
app.include_router(api_router)


@app.get("/")
def root():
    route_count = len([r for r in app.routes if hasattr(r, "methods")])
    return {"service": "HR Insights 360 API v2.0", "endpoints": route_count}
