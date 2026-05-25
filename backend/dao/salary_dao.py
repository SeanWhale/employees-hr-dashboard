# File: backend/dao/salary_dao.py
# -*- coding: utf-8 -*-
"""薪资数据访问层 — DuckDB SQL 执行，返回 DataFrame"""

try:
    from core.db import get_connection, get_parquet_path
except ImportError:
    from backend.core.db import get_connection, get_parquet_path


def get_salary_history_data():
    """薪资历史 — yearly_salary 视图全量数据"""
    con = get_connection()
    return con.execute("SELECT * FROM yearly_salary ORDER BY year, avg_salary DESC").df()


def get_salary_distribution_data():
    """薪资分布 — 部门分位数聚合（箱线图所需五个核心分位数）"""
    con = get_connection()
    return con.execute("""
        SELECT
            dept_name,
            MIN(salary) AS min_s,
            QUANTILE(salary, 0.25) AS q1_s,
            MEDIAN(salary) AS median_s,
            QUANTILE(salary, 0.75) AS q3_s,
            MAX(salary) AS max_s,
            AVG(salary) AS avg_s,
            STDDEV(salary) AS std_s,
            COUNT(*) AS cnt
        FROM current_employees
        GROUP BY dept_name
    """).df()


def get_salary_outliers_data():
    """薪资分布 — 基于 1.5 IQR 的离群值判定查询"""
    con = get_connection()
    return con.execute("""
        WITH fences AS (
            SELECT dept_name,
                   QUANTILE(salary, 0.25) AS q1,
                   QUANTILE(salary, 0.75) AS q3
            FROM current_employees
            GROUP BY dept_name
        )
        SELECT ce.dept_name, ce.salary
        FROM current_employees ce
        JOIN fences f ON ce.dept_name = f.dept_name
        WHERE ce.salary < f.q1 - 1.5 * (f.q3 - f.q1)
           OR ce.salary > f.q3 + 1.5 * (f.q3 - f.q1)
        ORDER BY ce.dept_name, ce.salary
    """).df()


def get_salary_evolution_data():
    """薪资演变 — 年度多维统计（含 QUANTILE / SKEWNESS / STDDEV）"""
    con = get_connection()
    s_path = get_parquet_path("load_salaries*.parquet")
    return con.execute(f"""
        SELECT
            CAST(EXTRACT(YEAR FROM from_date) AS INT) AS year,
            AVG(salary) AS mean,
            MEDIAN(salary) AS median,
            STDDEV(salary) AS std,
            QUANTILE(salary, 0.25) AS q1,
            QUANTILE(salary, 0.75) AS q3,
            QUANTILE(salary, 0.10) AS p10,
            QUANTILE(salary, 0.90) AS p90,
            SKEWNESS(salary) AS skew,
            COUNT(*) AS record_count
        FROM read_parquet('{s_path}')
        WHERE EXTRACT(YEAR FROM from_date) BETWEEN 1985 AND 2002
        GROUP BY year
        ORDER BY year
    """).df()


def get_salary_growth_rates_data():
    """薪资增长 — REGR_SLOPE / REGR_R2 回归系数（2000 名有效员工抽样）"""
    con = get_connection()
    s_path = get_parquet_path("load_salaries*.parquet")
    e_path = get_parquet_path("load_employees.parquet")
    return con.execute(f"""
        WITH salary_yrs AS (
            SELECT s.emp_no, s.salary,
                   CAST(EXTRACT(YEAR FROM s.from_date) - EXTRACT(YEAR FROM e.hire_date) AS INT) AS yrs,
                   ce.dept_name, ce.title
            FROM read_parquet('{s_path}') s
            JOIN read_parquet('{e_path}') e ON s.emp_no = e.emp_no
            JOIN current_employees ce ON s.emp_no = ce.emp_no
            WHERE s.salary > 0
        ),
        valid_emps AS (
            SELECT emp_no
            FROM salary_yrs
            GROUP BY emp_no
            HAVING COUNT(*) >= 5
            ORDER BY hash(emp_no)
            LIMIT 2000
        )
        SELECT sy.emp_no, sy.dept_name, sy.title,
               REGR_SLOPE(sy.salary, sy.yrs) AS growth,
               REGR_R2(sy.salary, sy.yrs) AS r2
        FROM salary_yrs sy
        JOIN valid_emps ve ON sy.emp_no = ve.emp_no
        GROUP BY sy.emp_no, sy.dept_name, sy.title
    """).df()


def get_salary_growth_curves_data():
    """薪资增长 — 50 条样本曲线数据（供前端多折线演化图）"""
    con = get_connection()
    s_path = get_parquet_path("load_salaries*.parquet")
    e_path = get_parquet_path("load_employees.parquet")
    return con.execute(f"""
        WITH salary_yrs AS (
            SELECT s.emp_no, s.salary,
                   CAST(EXTRACT(YEAR FROM s.from_date) - EXTRACT(YEAR FROM e.hire_date) AS INT) AS yrs,
                   ce.dept_name, ce.title
            FROM read_parquet('{s_path}') s
            JOIN read_parquet('{e_path}') e ON s.emp_no = e.emp_no
            JOIN current_employees ce ON s.emp_no = ce.emp_no
            WHERE s.salary > 0
        ),
        target_emps AS (
            SELECT emp_no
            FROM salary_yrs
            GROUP BY emp_no
            HAVING COUNT(*) >= 5
            ORDER BY hash(emp_no)
            LIMIT 50
        )
        SELECT sy.emp_no, sy.dept_name AS dept, sy.title, sy.yrs AS x, sy.salary AS y
        FROM salary_yrs sy
        JOIN target_emps te ON sy.emp_no = te.emp_no
        ORDER BY sy.emp_no, sy.yrs
    """).df()


def get_external_benchmark_data():
    """外部基准 — 部门内部薪资聚合"""
    con = get_connection()
    return con.execute("""
        SELECT dept_name, CAST(AVG(salary) AS INT) AS int_avg,
               CAST(MEDIAN(salary) AS INT) AS int_median, MAX(salary) AS int_max
        FROM current_employees GROUP BY dept_name
    """).df()
