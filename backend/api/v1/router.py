# File: backend/api/v1/router.py
"""API v1 路由聚合"""

from fastapi import APIRouter

try:
    from api.v1.overview import router as overview_router
except ImportError:
    from backend.api.v1.overview import router as overview_router

router = APIRouter(prefix="/v1")
router.include_router(overview_router)
