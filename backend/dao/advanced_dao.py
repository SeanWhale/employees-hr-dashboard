# File: backend/dao/advanced_dao.py
# -*- coding: utf-8 -*-
"""高级分析数据访问层 — DuckDB SQL 执行，返回 DataFrame"""

try:
    from core.config import DATASET_MAX_DATE
    from core.db import get_connection, get_parquet_path
except ImportError:
    from backend.core.config import DATASET_MAX_DATE
    from backend.core.db import get_connection, get_parquet_path


def get_clustering_data():
    """聚类分析 — 5000 条抽样员工特征数据"""
    con = get_connection()
    return con.execute(f"""
        SELECT emp_no, salary, dept_name, title,
               DATEDIFF('year', CAST(hire_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS tenure,
               DATEDIFF('year', CAST(birth_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS age
        FROM current_employees
        ORDER BY hash(emp_no)
        LIMIT 5000
    """).df()


def get_forecast_data():
    """预测分析 — 年度平均薪资数据"""
    con = get_connection()
    s_path = get_parquet_path("load_salaries*.parquet")
    return con.execute(f"""
        SELECT CAST(EXTRACT(YEAR FROM from_date) AS INT) AS yr, AVG(salary) AS avg_s
        FROM read_parquet('{s_path}')
        WHERE EXTRACT(YEAR FROM from_date) BETWEEN 1985 AND 2002
        GROUP BY yr ORDER BY yr
    """).df()


def get_correlation_data():
    """相关性分析 — 5000 条抽样员工特征数据"""
    con = get_connection()
    return con.execute(f"""
        SELECT salary, dept_name, title,
               DATEDIFF('year', CAST(hire_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS tenure,
               DATEDIFF('year', CAST(birth_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS age
        FROM current_employees
        ORDER BY hash(emp_no)
        LIMIT 5000
    """).df()


def get_similarity_data():
    """相似性分析 — 部门聚合特征（9 行）"""
    con = get_connection()
    return con.execute(f"""
        SELECT
            dept_name,
            AVG(salary) AS avg_salary,
            AVG(DATEDIFF('day', CAST(hire_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) / 365.25) AS avg_tenure,
            AVG(DATEDIFF('day', CAST(birth_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) / 365.25) AS avg_age,
            COUNT(*) AS emp_count,
            STDDEV(salary) AS std_salary
        FROM current_employees
        GROUP BY dept_name
    """).df()


def get_sankey_data():
    """桑基图 — 职级流动拓扑关系"""
    con = get_connection()
    t_path = get_parquet_path("load_titles.parquet")
    return con.execute(f"""
        WITH ordered_titles AS (
            SELECT emp_no, title,
                   LEAD(title) OVER (PARTITION BY emp_no ORDER BY from_date) AS next_title
            FROM read_parquet('{t_path}')
        )
        SELECT title AS source, next_title AS target, COUNT(*) AS value
        FROM ordered_titles
        WHERE next_title IS NOT NULL AND title != next_title
        GROUP BY source, target
    """).df()


def get_gender_dept_data():
    """性别分析 — 部门维度性别薪资数据"""
    con = get_connection()
    return con.execute(f"""
        SELECT gender, dept_name, COUNT(*) AS cnt,
               CAST(AVG(salary) AS INT) AS avg_s,
               CAST(MEDIAN(salary) AS INT) AS med_s,
               CAST(AVG(DATEDIFF('year', CAST(hire_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE))) AS FLOAT) AS avg_tenure
        FROM current_employees
        GROUP BY gender, dept_name ORDER BY dept_name, gender
    """).df()


def get_gender_promo_data():
    """性别分析 — 职级变更次数数据"""
    con = get_connection()
    e_path = get_parquet_path("load_employees.parquet")
    t_path = get_parquet_path("load_titles.parquet")
    return con.execute(f"""
        SELECT e.gender, COUNT(*) AS total, SUM(tc) AS total_changes, AVG(tc) AS avg_changes
        FROM (
            SELECT emp_no, COUNT(DISTINCT title)-1 AS tc FROM read_parquet('{t_path}') GROUP BY emp_no
        ) t
        JOIN read_parquet('{e_path}') e ON t.emp_no = e.emp_no
        GROUP BY e.gender
    """).df()


def get_title_transition_data():
    """职级转岗 — 转岗耗时统计"""
    con = get_connection()
    t_path = get_parquet_path("load_titles.parquet")
    return con.execute(f"""
        WITH ordered_titles AS (
            SELECT emp_no, title, from_date,
                   LEAD(title) OVER (PARTITION BY emp_no ORDER BY from_date) AS next_title,
                   LEAD(from_date) OVER (PARTITION BY emp_no ORDER BY from_date) AS next_from_date
            FROM read_parquet('{t_path}')
        ),
        deltas AS (
            SELECT title AS from_t, next_title AS to_t,
                   DATEDIFF('day', from_date, next_from_date) / 365.25 AS years
            FROM ordered_titles
            WHERE next_title IS NOT NULL AND title != next_title
        )
        SELECT
            from_t, to_t,
            COUNT(*) AS cnt,
            AVG(years) AS avg_y,
            MIN(years) AS min_y,
            QUANTILE(years, 0.25) AS q1_y,
            MEDIAN(years) AS median_y,
            QUANTILE(years, 0.75) AS q3_y,
            MAX(years) AS max_y
        FROM deltas
        GROUP BY from_t, to_t
        HAVING cnt >= 3
    """).df()


def get_retention_data():
    """留任度分析 — 5000 抽样员工的部门/职级变更次数"""
    con = get_connection()
    de_path = get_parquet_path("load_dept_emp.parquet")
    t_path = get_parquet_path("load_titles.parquet")
    return con.execute(f"""
        WITH sampled_cur AS (
            SELECT emp_no, salary, dept_name, title
            FROM current_employees
            ORDER BY hash(emp_no)
            LIMIT 5000
        ),
        dc AS (
            SELECT de.emp_no, COUNT(DISTINCT de.dept_no) - 1 AS dc
            FROM read_parquet('{de_path}') de
            WHERE de.emp_no IN (SELECT emp_no FROM sampled_cur)
            GROUP BY de.emp_no
        ),
        tc AS (
            SELECT t.emp_no, COUNT(DISTINCT t.title) - 1 AS tc
            FROM read_parquet('{t_path}') t
            WHERE t.emp_no IN (SELECT emp_no FROM sampled_cur)
            GROUP BY t.emp_no
        )
        SELECT sc.emp_no, sc.salary, sc.dept_name, sc.title,
               COALESCE(dc.dc, 0) AS dc, COALESCE(tc.tc, 0) AS tc
        FROM sampled_cur sc
        LEFT JOIN dc ON sc.emp_no = dc.emp_no
        LEFT JOIN tc ON sc.emp_no = tc.emp_no
    """).df()


def get_dept_forecast_data():
    """分部门预测 — 历史部门年度薪资"""
    con = get_connection()
    return con.execute("""
        SELECT year, dept_name, avg_salary AS avg_s
        FROM yearly_salary
        ORDER BY dept_name, year
    """).df()
