"""ETL 清洗任务启动入口 — 调用 extract → transform → load 并生成质量报告

用法: python -m etl
"""
from .config import DUMP_DIR, RAW_DIR, CLEAN_DIR, REPORT_DIR, SCHEMAS, DUMP_FILES, filename_to_tablename
from .extract import parse_mysql_dump
from .transform import (
    coerce_columns, clean_employees, set_default_to_date,
    merge_adjacent_same_dept, fix_overlaps_by_shifting,
    apply_quality_rules, filter_by_employees
)
from .load import save_raw_parquet, save_clean_parquet, save_quality_report


def run_etl():
    """主 ETL 流水线：批量解析 dump → 清洗 → 写出 Parquet + 质量报告"""
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

        table_name = filename_to_tablename(filename)
        print(f"\n{'='*60}")
        print(f"Processing: {filename} -> table '{table_name}'")

        # 1. Extract: 解析原始数据
        df = parse_mysql_dump(str(file_path), SCHEMAS[table_name])
        print(f"  Parsed: {len(df):,} rows")

        # 2. 保存原始 Parquet 镜像（未经类型转换的原始字符串数据）
        raw_df = df.copy()
        raw_name = filename.replace(".dump", ".parquet")
        save_raw_parquet(raw_df, RAW_DIR / raw_name)
        print(f"  Raw saved: {RAW_DIR / raw_name} ({len(raw_df):,} rows)")

        # 3. Transform: 类型转换
        df = coerce_columns(df, table_name)

        # 4. Transform: 质量规则过滤（须在类型转换之后执行）
        df, missing_counts, invalid_counts, dropped = apply_quality_rules(df, table_name)
        if dropped:
            print(f"  Quality: dropped {dropped:,} rows (missing: {missing_counts}, invalid: {invalid_counts})")

        # 5. Transform: 属性标准化
        if table_name == "employees":
            df = clean_employees(df)
            employees_df = df

        if table_name == "dept_emp":
            df = df.drop_duplicates(subset=["emp_no", "dept_no", "from_date", "to_date"])

        # 6. Transform: 时态清洗
        zero_dropped = 0
        if table_name in {"dept_emp", "salaries", "titles"}:
            before = len(df)
            df = df[df["from_date"] != df["to_date"]]
            zero_dropped = before - len(df)
            if zero_dropped:
                print(f"  Temporal: dropped {zero_dropped:,} zero-duration phantom records")

        df = set_default_to_date(df)

        merges = 0
        if table_name == "dept_emp":
            df, merges = merge_adjacent_same_dept(df)
            if merges:
                print(f"  Temporal: merged {merges:,} adjacent department periods")

        overlaps_fixed = 0
        if table_name in {"dept_emp", "titles", "salaries"}:
            df, overlaps_fixed = fix_overlaps_by_shifting(df)
            if overlaps_fixed:
                print(f"  Temporal: fixed {overlaps_fixed:,} overlapping intervals")

        # 7. 过滤孤儿数据
        orphan_drop = 0
        if table_name in {"salaries", "titles", "dept_emp", "dept_manager"}:
            df, orphan_drop = filter_by_employees(df, employees_df)
            if orphan_drop:
                print(f"  Orphans: removed {orphan_drop:,} records referencing non-existent employees")

        # 8. Load: 写出清洗完成的 Parquet
        clean_name = filename.replace(".dump", ".parquet")
        save_clean_parquet(df, CLEAN_DIR / clean_name)
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
    save_quality_report(quality_report, report_path)

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
