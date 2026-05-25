# File: backend/parse_dumps.py
"""
ETL Pipeline: MySQL dump files -> Clean Parquet
Parses data/dump/*.dump (MySQL INSERT statements) -> data/processed/parquet/*.parquet
Also outputs raw parquet to data/parquet/ and a quality report to data/processed/data_quality_report.json
"""
import re
import ast
import json
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DUMP_DIR = PROJECT_ROOT / "data" / "dump"
RAW_DIR = PROJECT_ROOT / "data" / "parquet"
CLEAN_DIR = PROJECT_ROOT / "data" / "processed" / "parquet"
REPORT_DIR = PROJECT_ROOT / "data" / "processed"

# ------------------------------------------------------------
# Schema definitions
# ------------------------------------------------------------
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

# 优化 1：调整执行顺序，确保 employees 最先被解析以作为外键过滤基准
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


def _filename_to_tablename(filename: str) -> str:
    name = filename.replace("load_", "").replace(".dump", "")
    return re.sub(r"\d+$", "", name)


# ------------------------------------------------------------
# Type coercion & column-level cleaning
# ------------------------------------------------------------
def _coerce_columns(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    df = df.replace({"\\N": None})

    for col in INT_COLUMNS.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in DATE_COLUMNS.get(table_name, []):
        if col in df.columns:
            # 优化 2：在转为 Datetime 之前将 9999-01-01 替换为 Pandas 支持的 2099-01-01
            df[col] = df[col].astype(str).replace({'9999-01-01': '2099-01-01'})
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def _clean_employees(df: pd.DataFrame) -> pd.DataFrame:
    df["first_name"] = df["first_name"].fillna("Unknown").astype(str).str.strip().str.title()
    df.loc[df["first_name"] == "", "first_name"] = "Unknown"
    df["last_name"] = df["last_name"].fillna("Unknown").astype(str).str.strip().str.title()
    df.loc[df["last_name"] == "", "last_name"] = "Unknown"
    df["gender"] = df["gender"].fillna("U").astype(str).str.strip().str.upper()
    df.loc[~df["gender"].isin(["M", "F"]), "gender"] = "U"
    return df


# ------------------------------------------------------------
# Temporal logic cleaning (vectorized)
# ------------------------------------------------------------
def _set_default_to_date(df: pd.DataFrame) -> pd.DataFrame:
    if "to_date" in df.columns:
        mask = df["to_date"].isna()
        if mask.any():
            df.loc[mask, "to_date"] = pd.to_datetime("2099-01-01")
    return df


def _merge_adjacent_same_dept(df: pd.DataFrame) -> tuple:
    df = df.sort_values(["emp_no", "from_date"]).reset_index(drop=True)

    emp_changed = df["emp_no"] != df["emp_no"].shift()
    dept_changed = df["dept_no"] != df.groupby("emp_no")["dept_no"].shift()
    gap = df["from_date"] > (df.groupby("emp_no")["to_date"].shift() + pd.Timedelta(days=1))

    # 由于前置步骤已经清洗了空值，此处 cumsum() 不会因 <NA> 崩溃
    group_id = (emp_changed | dept_changed | gap).cumsum()

    merged = df.groupby(group_id, sort=False).agg(
        emp_no=("emp_no", "first"),
        dept_no=("dept_no", "first"),
        from_date=("from_date", "min"),
        to_date=("to_date", "max"),
    ).reset_index(drop=True)

    merges = len(df) - len(merged)
    return merged, merges


def _fix_overlaps_by_shifting(df: pd.DataFrame) -> tuple:
    if "from_date" not in df.columns or "to_date" not in df.columns:
        return df, 0

    df = df.sort_values(["emp_no", "from_date"]).reset_index(drop=True)

    same_emp = df["emp_no"] == df["emp_no"].shift(-1)
    true_overlap = df["to_date"] >= df["from_date"].shift(-1)
    needs_fix = same_emp & true_overlap
    fix_count = needs_fix.sum()

    if fix_count > 0:
        # 优化 3：使用更加安全高效的 shift(-1) 代替 index 算术运算
        df.loc[needs_fix, "to_date"] = df["from_date"].shift(-1) - pd.Timedelta(days=1)

    return df, fix_count


# ------------------------------------------------------------
# Quality rules
# ------------------------------------------------------------
def _apply_quality_rules(df: pd.DataFrame, table_name: str) -> tuple:
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


def _filter_by_employees(df: pd.DataFrame, employees_df: pd.DataFrame) -> tuple:
    if employees_df is None or employees_df.empty or "emp_no" not in df.columns:
        return df, 0
    before = len(df)
    filtered = df[df["emp_no"].isin(employees_df["emp_no"])]
    return filtered, before - len(filtered)


def _clamp_salary_outliers(df: pd.DataFrame) -> tuple:
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


# ------------------------------------------------------------
# MySQL dump parser (Corrected for multi-line format)
# ------------------------------------------------------------
def parse_mysql_dump(file_path: str, columns: list, table_name: str) -> pd.DataFrame:
    """解析 MySQL dump 文件。完美兼容 test_db 数据集的一行一条记录的多行 INSERT 格式。"""
    data = []
    in_insert = False
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 1. 检测到 INSERT 语句开始
            if line.startswith("INSERT INTO") or line.startswith("insert into"):
                in_insert = True
                # 检查 VALUES 同行是否带有第一条数据（如 employees/salaries 等多 INSERT 块文件）
                upper = line.upper()
                if "VALUES" in upper:
                    val_idx = upper.find("VALUES") + 6
                    rest = line[val_idx:].strip()
                    if rest.startswith("("):
                        line = rest  # 交给下面的数据解析逻辑处理，不跳过
                    else:
                        continue
                else:
                    continue
            
            # 2. 如果处于插入状态，逐行读取数据
            if in_insert:
                if line.startswith("("):
                    is_last = line.endswith(";")
                    
                    # 剥离前后的括号和行尾逗号/分号
                    content = line
                    if content.startswith("("):
                        content = content[1:]
                    if content.endswith(";"):
                        content = content[:-1]
                    if content.endswith(")"):
                        content = content[:-1]
                    elif content.endswith("),"):
                        content = content[:-2]
                    
                    try:
                        # 替换 MySQL NULL 值为 Python 的 None
                        safe = re.sub(r"\bNULL\b", "None", content)
                        row = ast.literal_eval(f"({safe})")
                        data.append(row)
                    except (ValueError, SyntaxError):
                        pass
                    
                    # 如果遇到分号结束，说明该 insert 块结束
                    if is_last:
                        in_insert = False

    # 3. 预防性处理：如果没有任何数据，返回带正确列名的空 DataFrame，防止 Pandas 报错
    if not data:
        df = pd.DataFrame(columns=columns)
    else:
        df = pd.DataFrame(data, columns=columns)
        
    df = df.drop_duplicates()
    return _coerce_columns(df, table_name)


# ------------------------------------------------------------
# Main ETL pipeline
# ------------------------------------------------------------
def run_etl():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    employees_df = None
    quality_report = {}
    total_stats = {}

    for filename in DUMP_FILES:
        file_path = DUMP_DIR / filename
        if not file_path.exists():
            print(f"[SKIP] File not found: {file_path}")
            continue

        table_name = _filename_to_tablename(filename)
        print(f"\n{'='*60}")
        print(f"Processing: {filename} -> table '{table_name}'")

        # 1. 解析原始数据
        df = parse_mysql_dump(str(file_path), SCHEMAS[table_name], table_name)
        print(f"  Parsed: {len(df):,} rows")

        # 2. 【核心修复】保存真正的、未被污染的原始 Parquet 镜像
        raw_df = df.copy()
        raw_name = filename.replace(".dump", ".parquet")
        raw_df.to_parquet(str(RAW_DIR / raw_name), engine="pyarrow")
        print(f"  Raw saved: {RAW_DIR / raw_name} ({len(raw_df):,} rows)")

        # 3. 【核心修复】必须优先执行“质量过滤规则”，防止 NaN 破坏后置时态逻辑
        df, missing_counts, invalid_counts, dropped = _apply_quality_rules(df, table_name)
        if dropped:
            print(f"  Quality: dropped {dropped:,} rows (missing: {missing_counts}, invalid: {invalid_counts})")

        # 4. 在清洗干净的数据集上进行属性标准化
        if table_name == "employees":
            df = _clean_employees(df)
            employees_df = df # 更新员工注册库，供后续表过滤孤儿数据
            
        if table_name == "dept_emp":
            df = df.drop_duplicates(subset=["emp_no", "dept_no", "from_date", "to_date"])

        # 5. 时态清洗
        # 5a. 删除零时长幻影记录 (from_date == to_date)
        zero_dropped = 0
        if table_name in {"dept_emp", "salaries", "titles"}:
            before = len(df)
            df = df[df["from_date"] != df["to_date"]]
            zero_dropped = before - len(df)
            if zero_dropped:
                print(f"  Temporal: dropped {zero_dropped:,} zero-duration phantom records")

        df = _set_default_to_date(df)

        # 5b. 合并相邻同部门记录 (仅 dept_emp)
        merges = 0
        if table_name == "dept_emp":
            df, merges = _merge_adjacent_same_dept(df)
            if merges:
                print(f"  Temporal: merged {merges:,} adjacent department periods")

        # 5c. 修复时间区间重叠 (dept_emp / titles / salaries)
        overlaps_fixed = 0
        if table_name in {"dept_emp", "titles", "salaries"}:
            df, overlaps_fixed = _fix_overlaps_by_shifting(df)
            if overlaps_fixed:
                print(f"  Temporal: fixed {overlaps_fixed:,} overlapping intervals")

        # 6. 过滤孤儿数据
        orphan_drop = 0
        if table_name in {"salaries", "titles", "dept_emp", "dept_manager"}:
            df, orphan_drop = _filter_by_employees(df, employees_df)
            if orphan_drop:
                print(f"  Orphans: removed {orphan_drop:,} records referencing non-existent employees")

        # 8. 保存清洗完成的 Parquet 文件
        clean_name = filename.replace(".dump", ".parquet")
        df.to_parquet(str(CLEAN_DIR / clean_name), engine="pyarrow")
        print(f"  Clean saved: {CLEAN_DIR / clean_name} ({len(df):,} rows)")

        # 9. 记录清洗指标
        report_key = filename.replace(".dump", "")
        quality_report[report_key] = {
            "rows_in": int(len(raw_df)),
            "rows_out": int(len(df)),
            "dropped": int(dropped),
            "zero_duration_dropped": int(zero_dropped),
            "missing": {k: int(v) for k, v in missing_counts.items()},
            "invalid": {k: int(v) for k, v in invalid_counts.items()},
            "orphan_emp_no": int(orphan_drop),
            "merged_adjacent_dept": int(merges),
            "overlap_fixed": int(overlaps_fixed),
        }
        total_stats[table_name] = total_stats.get(table_name, 0) + int(len(df))

    # 生成质量报告
    report_path = REPORT_DIR / "data_quality_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("ETL COMPLETE -- Summary")
    print(f"{'='*60}")
    for t, n in total_stats.items():
        print(f"  {t:<18} {n:>10,} rows")
    print(f"\n  Raw output:     {RAW_DIR}")
    print(f"  Clean output:   {CLEAN_DIR}")
    print(f"  Quality report: {report_path}")


if __name__ == "__main__":
    run_etl()