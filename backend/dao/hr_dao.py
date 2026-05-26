# File: backend/dao/hr_dao.py
# -*- coding: utf-8 -*-
"""HR 数据访问层 — DuckDB SQL 执行，返回 DataFrame"""

try:
    from core.db import get_connection
except ImportError:
    from backend.core.db import get_connection


def get_kpi_data():
    """KPI 核心指标原始数据"""
    con = get_connection()
    return con.execute("""
        SELECT COUNT(*) AS total, CAST(AVG(salary) AS INT) AS avg_s,
               MAX(salary) AS max_s, MIN(salary) AS min_s,
               CAST(STDDEV(salary) AS INT) AS std_s
        FROM current_employees
    """).df()


def get_dept_distribution_data():
    """部门分布原始数据"""
    con = get_connection()
    return con.execute("""
        SELECT dept_name, COUNT(*) AS emp_count,
               CAST(AVG(salary) AS INT) AS avg_salary,
               CAST(MEDIAN(salary) AS INT) AS median_salary,
               MIN(salary) AS min_salary, MAX(salary) AS max_salary,
               CAST(STDDEV(salary) AS INT) AS std_salary
        FROM current_employees
        GROUP BY dept_name ORDER BY avg_salary DESC
    """).df()
