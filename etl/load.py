# File: etl/load.py
"""数据写出层 — Raw / Clean Parquet 持久化与质量报告生成"""
import json


def save_raw_parquet(df, filepath):
    """保存原始 Parquet 镜像"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(str(filepath), engine="pyarrow")


def save_clean_parquet(df, filepath):
    """保存清洗后的 Parquet 文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(str(filepath), engine="pyarrow")


def save_quality_report(report: dict, filepath):
    """将质量报告写入 JSON 文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
