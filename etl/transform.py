# File: etl/transform.py
"""数据清洗/变换层 — 类型转换、属性标准化、时态合并、重叠修复、质量规则"""
import pandas as pd

from .config import INT_COLUMNS, DATE_COLUMNS, REQUIRED_COLUMNS


# ---- 类型转换 ----

def coerce_columns(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """将字符串列转换为目标类型（Int64 / datetime），替换 \\N 为 None"""
    df = df.replace({"\\N": None})

    for col in INT_COLUMNS.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in DATE_COLUMNS.get(table_name, []):
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"9999-01-01": "2099-01-01"})
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


# ---- 属性标准化 ----

def clean_employees(df: pd.DataFrame) -> pd.DataFrame:
    """Employees 表专项清洗：姓名补缺/格式化，性别标准化"""
    df["first_name"] = df["first_name"].fillna("Unknown").astype(str).str.strip().str.title()
    df.loc[df["first_name"] == "", "first_name"] = "Unknown"
    df["last_name"] = df["last_name"].fillna("Unknown").astype(str).str.strip().str.title()
    df.loc[df["last_name"] == "", "last_name"] = "Unknown"
    df["gender"] = df["gender"].fillna("U").astype(str).str.strip().str.upper()
    df.loc[~df["gender"].isin(["M", "F"]), "gender"] = "U"
    return df


# ---- 时态清洗 ----

def set_default_to_date(df: pd.DataFrame) -> pd.DataFrame:
    """将缺失的 to_date 填充为 2099-01-01"""
    if "to_date" in df.columns:
        mask = df["to_date"].isna()
        if mask.any():
            df.loc[mask, "to_date"] = pd.to_datetime("2099-01-01")
    return df


def merge_adjacent_same_dept(df: pd.DataFrame) -> tuple:
    """合并同一员工相邻且同一部门的连续记录"""
    df = df.sort_values(["emp_no", "from_date"]).reset_index(drop=True)

    emp_changed = df["emp_no"] != df["emp_no"].shift()
    dept_changed = df["dept_no"] != df.groupby("emp_no")["dept_no"].shift()
    gap = df["from_date"] > (df.groupby("emp_no")["to_date"].shift() + pd.Timedelta(days=1))

    group_id = (emp_changed | dept_changed | gap).cumsum()

    merged = df.groupby(group_id, sort=False).agg(
        emp_no=("emp_no", "first"),
        dept_no=("dept_no", "first"),
        from_date=("from_date", "min"),
        to_date=("to_date", "max"),
    ).reset_index(drop=True)

    merges = len(df) - len(merged)
    return merged, merges


def fix_overlaps_by_shifting(df: pd.DataFrame) -> tuple:
    """修复同一员工相邻记录的时间区间重叠"""
    if "from_date" not in df.columns or "to_date" not in df.columns:
        return df, 0

    df = df.sort_values(["emp_no", "from_date"]).reset_index(drop=True)

    same_emp = df["emp_no"] == df["emp_no"].shift(-1)
    true_overlap = df["to_date"] >= df["from_date"].shift(-1)
    needs_fix = same_emp & true_overlap
    fix_count = needs_fix.sum()

    if fix_count > 0:
        df.loc[needs_fix, "to_date"] = df["from_date"].shift(-1) - pd.Timedelta(days=1)

    return df, fix_count


# ---- 数据质量规则 ----

def apply_quality_rules(df: pd.DataFrame, table_name: str) -> tuple:
    """应用质量规则，返回 (cleaned_df, missing_counts, invalid_counts, dropped)"""
    required = REQUIRED_COLUMNS.get(table_name, [])

    row_missing = pd.Series(False, index=df.index)
    missing_counts = {}
    for col in required:
        if col not in df.columns:
            missing_counts[col] = len(df)
            row_missing |= True
            continue
        col_missing = df[col].isna()
        if df[col].dtype == object:
            col_missing |= df[col].astype(str).str.strip().eq("")
        missing_counts[col] = int(col_missing.sum())
        row_missing |= col_missing

    row_invalid = pd.Series(False, index=df.index)
    invalid_counts = {}

    if table_name in {"dept_emp", "dept_manager", "salaries", "titles"}:
        if "from_date" in df.columns and "to_date" in df.columns:
            invalid_date = df["from_date"].notna() & df["to_date"].notna() & (df["from_date"] > df["to_date"])
            invalid_counts["date_order"] = int(invalid_date.sum())
            row_invalid |= invalid_date

    if table_name == "employees":
        if "birth_date" in df.columns and "hire_date" in df.columns:
            invalid_birth = df["birth_date"].notna() & df["hire_date"].notna() & (df["birth_date"] >= df["hire_date"])
            invalid_counts["birth_after_hire"] = int(invalid_birth.sum())
            row_invalid |= invalid_birth

    if table_name == "salaries" and "salary" in df.columns:
        invalid_salary = df["salary"].notna() & (df["salary"] <= 0)
        invalid_counts["non_positive_salary"] = int(invalid_salary.sum())
        row_invalid |= invalid_salary

    cleaned = df.loc[~(row_missing | row_invalid)].copy()
    dropped = int(len(df) - len(cleaned))

    return cleaned, missing_counts, invalid_counts, dropped


def filter_by_employees(df: pd.DataFrame, employees_df: pd.DataFrame) -> tuple:
    """过滤不存在于 employees 表中的孤儿 emp_no 记录"""
    if employees_df is None or employees_df.empty or "emp_no" not in df.columns:
        return df, 0
    before = len(df)
    filtered = df[df["emp_no"].isin(employees_df["emp_no"])]
    return filtered, before - len(filtered)


def clamp_salary_outliers(df: pd.DataFrame) -> tuple:
    """将薪资 clamp 到 [P1, P99] 区间"""
    if len(df) == 0:
        return df, 0, 0, 0
    lo = df["salary"].quantile(0.01)
    hi = df["salary"].quantile(0.99)
    clamped = (df["salary"] < lo) | (df["salary"] > hi)
    n = clamped.sum()
    if n > 0:
        df.loc[df["salary"] < lo, "salary"] = int(lo)
        df.loc[df["salary"] > hi, "salary"] = int(hi)
    return df, int(n), int(lo), int(hi)
