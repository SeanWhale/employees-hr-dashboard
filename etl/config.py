"""ETL 元数据配置 — 路径、表结构、类型映射、dump 文件清单"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DUMP_DIR = PROJECT_ROOT / "data" / "dump"
RAW_DIR = PROJECT_ROOT / "data" / "parquet"
CLEAN_DIR = PROJECT_ROOT / "data" / "processed" / "parquet"
REPORT_DIR = PROJECT_ROOT / "data" / "processed"

SCHEMAS = {
    "departments": ["dept_no", "dept_name"],
    "dept_emp": ["emp_no", "dept_no", "from_date", "to_date"],
    "dept_manager": ["emp_no", "dept_no", "from_date", "to_date"],
    "employees": ["emp_no", "birth_date", "first_name", "last_name", "gender", "hire_date"],
    "salaries": ["emp_no", "salary", "from_date", "to_date"],
    "titles": ["emp_no", "title", "from_date", "to_date"],
}

REQUIRED_COLUMNS = {
    "departments": ["dept_no", "dept_name"],
    "dept_emp": ["emp_no", "dept_no", "from_date", "to_date"],
    "dept_manager": ["emp_no", "dept_no", "from_date", "to_date"],
    "employees": ["emp_no", "birth_date", "first_name", "last_name", "gender", "hire_date"],
    "salaries": ["emp_no", "salary", "from_date", "to_date"],
    "titles": ["emp_no", "title", "from_date", "to_date"],
}

DATE_COLUMNS = {
    "dept_emp": ["from_date", "to_date"],
    "dept_manager": ["from_date", "to_date"],
    "employees": ["birth_date", "hire_date"],
    "salaries": ["from_date", "to_date"],
    "titles": ["from_date", "to_date"],
}

INT_COLUMNS = {
    "dept_emp": ["emp_no"],
    "dept_manager": ["emp_no"],
    "employees": ["emp_no"],
    "salaries": ["emp_no", "salary"],
    "titles": ["emp_no"],
}

# employees 最先解析以作为后续表的外键过滤基准
DUMP_FILES = [
    "load_employees.dump",
    "load_departments.dump",
    "load_dept_emp.dump",
    "load_dept_manager.dump",
    "load_salaries1.dump",
    "load_salaries2.dump",
    "load_salaries3.dump",
    "load_titles.dump",
]


def filename_to_tablename(filename: str) -> str:
    """将 dump 文件名映射到逻辑表名，如 'load_salaries1.dump' → 'salaries'"""
    name = filename.replace("load_", "").replace(".dump", "")
    return re.sub(r"\d+$", "", name)
