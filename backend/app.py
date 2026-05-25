# File: backend/app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.config import FRONTEND_DIR
from backend.core.db import init_db

# 👇 换成导入我们刚才新建的 v1 router
from backend.api.v1.router import router as v1_router

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

app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

# 👇 挂载新的路由
app.include_router(v1_router, prefix="/api")

@app.get("/")
def root():
    route_count = len([r for r in app.routes if hasattr(r, "methods")])
    return {"service": "HR Insights 360 API v2.0", "endpoints": route_count}