# File: backend/routes/api.py
"""API 路由 — 17 个端点覆盖所有分析维度"""
from fastapi import APIRouter
from fastapi import APIRouter

# 强制使用绝对路径
from backend.services import analytics as A

router = APIRouter(prefix="/api")


@router.get("/kpi")
def api_kpi():
    return A.get_kpi()


@router.get("/dept_distribution")
def api_dept():
    return A.get_dept_distribution()


@router.get("/clustering")
def api_clustering():
    return A.get_clustering()


@router.get("/salary_history")
def api_history():
    return A.get_salary_history()


@router.get("/forecast")
def api_forecast():
    return A.get_forecast()


@router.get("/correlation")
def api_correlation():
    return A.get_correlation()


@router.get("/similarity")
def api_similarity():
    return A.get_similarity()


@router.get("/title_sankey")
def api_sankey():
    return A.get_title_sankey()


@router.get("/salary_distribution")
def api_dist():
    return A.get_salary_distribution()


@router.get("/gender_analysis")
def api_gender():
    return A.get_gender_analysis()


@router.get("/title_transition")
def api_transition():
    return A.get_title_transition()


@router.get("/salary_evolution")
def api_evolution():
    return A.get_salary_evolution()


@router.get("/external_benchmark")
def api_benchmark():
    return A.get_external_benchmark()


@router.get("/office_map")
def api_map():
    return A.get_office_map()


@router.get("/retention")
def api_retention():
    return A.get_retention()


@router.get("/dept_forecast")
def api_dept_forecast():
    return A.get_dept_forecast()


@router.get("/salary_growth")
def api_growth():
    return A.get_salary_growth()
