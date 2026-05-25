# File: backend/api/v1/overview.py
"""总览看板 API — 3 个端点"""

from fastapi import APIRouter

try:
    from services.overview_srv import get_dept_distribution, get_kpi, get_office_map
except ImportError:
    from backend.services.overview_srv import get_dept_distribution, get_kpi, get_office_map

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/kpi")
def api_kpi():
    return get_kpi()


@router.get("/dept_distribution")
def api_dept():
    return get_dept_distribution()


@router.get("/office_map")
def api_map():
    return get_office_map()
