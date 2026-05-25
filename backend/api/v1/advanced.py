# File: backend/api/v1/advanced.py
"""高级分析 API — 9 个端点"""

from fastapi import APIRouter

try:
    from services.advanced_srv import (get_clustering, get_correlation, get_dept_forecast,
                                        get_forecast, get_gender_analysis, get_retention,
                                        get_similarity, get_title_sankey, get_title_transition)
except ImportError:
    from backend.services.advanced_srv import (get_clustering, get_correlation, get_dept_forecast,
                                                get_forecast, get_gender_analysis, get_retention,
                                                get_similarity, get_title_sankey, get_title_transition)

router = APIRouter(prefix="/advanced", tags=["advanced"])


@router.get("/clustering")
def api_clustering():
    return get_clustering()


@router.get("/forecast")
def api_forecast():
    return get_forecast()


@router.get("/correlation")
def api_correlation():
    return get_correlation()


@router.get("/similarity")
def api_similarity():
    return get_similarity()


@router.get("/title_sankey")
def api_sankey():
    return get_title_sankey()


@router.get("/gender_analysis")
def api_gender():
    return get_gender_analysis()


@router.get("/title_transition")
def api_transition():
    return get_title_transition()


@router.get("/retention")
def api_retention():
    return get_retention()


@router.get("/dept_forecast")
def api_dept_forecast():
    return get_dept_forecast()
