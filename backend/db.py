# File: backend/db.py
# -*- coding: utf-8 -*-
"""数据库连接层 - DuckDB 分析引擎 (对接清洗后的 Parquet 数据)"""
import os
import tempfile
import duckdb

_CON = None
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PQ_DIR = os.path.join(_PROJECT_ROOT, "data", "processed", "parquet")
_DB_PATH = os.path.join(tempfile.gettempdir(), "hr_dashboard_analytics.duckdb")

# 数据集时间快照锚点（2002年8月），防止计算年龄/工龄时发生“时空穿越”
DATASET_MAX_DATE = "2002-08-01"


def get_parquet_path(pattern: str) -> str:
    """拼接 Parquet 文件路径，通配符由 DuckDB read_parquet 自行展开"""
    return os.path.join(_PQ_DIR, pattern).replace("\\", "/")


def _init(con):
    """初始化视图: 当前在职员工全景视图 + 历史薪资视图"""
    e = get_parquet_path("load_employees.parquet")
    s = get_parquet_path("load_salaries*.parquet")
    t = get_parquet_path("load_titles.parquet")
    de = get_parquet_path("load_dept_emp.parquet")
    d = get_parquet_path("load_departments.parquet")

    # 1. 当前在职员工视图 
    con.execute(f"""
        CREATE OR REPLACE VIEW current_employees AS
        SELECT
            e.emp_no, e.first_name, e.last_name, e.gender,
            e.birth_date, e.hire_date,
            s.salary,
            t.title,
            d.dept_name, d.dept_no
        FROM read_parquet('{e}') e
        JOIN read_parquet('{s}') s ON e.emp_no = s.emp_no AND s.to_date = '2099-01-01'
        JOIN read_parquet('{t}') t ON e.emp_no = t.emp_no AND t.to_date = '2099-01-01'
        JOIN read_parquet('{de}') de ON e.emp_no = de.emp_no AND de.to_date = '2099-01-01'
        JOIN read_parquet('{d}') d ON de.dept_no = d.dept_no
    """)

    # 2. 按年份的部门平均薪资视图
    con.execute(f"""
        CREATE OR REPLACE VIEW yearly_salary AS
        SELECT
            EXTRACT(YEAR FROM s.from_date) AS year,
            d.dept_name,
            AVG(s.salary) AS avg_salary,
            MEDIAN(s.salary) AS median_salary,
            COUNT(*) AS record_count
        FROM read_parquet('{s}') s
        JOIN read_parquet('{de}') de ON s.emp_no = de.emp_no
            AND s.from_date >= de.from_date
            AND s.from_date <= de.to_date
        JOIN read_parquet('{d}') d ON de.dept_no = d.dept_no
        WHERE EXTRACT(YEAR FROM s.from_date) BETWEEN 1985 AND 2002
        GROUP BY year, d.dept_name
    """)


def get_connection():
    """
    获取线程安全的 DuckDB 连接实例。
    
    【面向维护者的语义说明】：
    此处返回的是 `_CON.cursor()`。
    在 DuckDB 的 Python 驱动设计中，.cursor() 并非标准 DB-API 的受限游标，
    其返回的依然是一个完整的、线程安全的 `DuckDBPyConnection`（连接）对象，
    且共享主连接 `_CON` 的内存数据库空间。
    
    这种设计是 DuckDB 官方推荐的多线程并发查询标准方案，能够彻底避免 FastAPI 
    并发请求同一全局连接时产生的底层锁竞争（Connection Lock）与随机 500 报错。
    """
    global _CON
    if _CON is None:
        _CON = duckdb.connect(database=_DB_PATH)
        _init(_CON)
    return _CON.cursor()


def init_db():
    get_connection()