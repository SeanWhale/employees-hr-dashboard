# File: backend/api/v1/salary.py
"""薪资分析 API — 5 个端点"""

from fastapi import APIRouter

try:
    from services.salary_srv import (get_external_benchmark, get_salary_distribution,
                                      get_salary_evolution, get_salary_growth,
                                      get_salary_history)
except ImportError:
    from backend.services.salary_srv import (get_external_benchmark, get_salary_distribution,
                                              get_salary_evolution, get_salary_growth,
                                              get_salary_history)

router = APIRouter(prefix="/salary", tags=["salary"])


@router.get("/history")
def api_history():
    return get_salary_history()


@router.get("/distribution")
def api_dist():
    return get_salary_distribution()


@router.get("/evolution")
def api_evolution():
    return get_salary_evolution()


@router.get("/growth")
def api_growth():
    return get_salary_growth()


@router.get("/external_benchmark")
def api_benchmark():
    return get_external_benchmark()
