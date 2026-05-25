# File: backend/services/salary_srv.py
# -*- coding: utf-8 -*-
"""薪资分析服务 — 调用 DAO 组装数据，执行 Pandas/Numpy 业务逻辑"""

import pandas as pd

try:
    from dao.salary_dao import (get_external_benchmark_data,
                                 get_salary_distribution_data,
                                 get_salary_evolution_data,
                                 get_salary_growth_curves_data,
                                 get_salary_growth_rates_data,
                                 get_salary_history_data,
                                 get_salary_outliers_data)
except ImportError:
    from backend.dao.salary_dao import (get_external_benchmark_data,
                                         get_salary_distribution_data,
                                         get_salary_evolution_data,
                                         get_salary_growth_curves_data,
                                         get_salary_growth_rates_data,
                                         get_salary_history_data,
                                         get_salary_outliers_data)


def get_salary_history():
    df = get_salary_history_data()
    df = df.sort_values(["year", "dept_name"]).reset_index(drop=True)
    return df.to_dict(orient="records")


def get_salary_distribution():
    df = get_salary_distribution_data()

    results = []
    for r in df.itertuples(index=False):
        q1, q3 = float(r.q1_s), float(r.q3_s)
        iqr = q3 - q1
        results.append({
            "dept_name": r.dept_name,
            "box": [round(float(r.min_s), 0), round(q1, 0), round(float(r.median_s), 0),
                    round(q3, 0), round(float(r.max_s), 0)],
            "stats": {
                "mean": round(float(r.avg_s), 0), "median": round(float(r.median_s), 0),
                "std": round(float(r.std_s), 0), "count": int(r.cnt),
                "min": round(float(r.min_s), 0), "max": round(float(r.max_s), 0),
                "q1": round(q1, 0), "q3": round(q3, 0), "iqr": round(iqr, 0),
                "outliers_low": 0, "outliers_high": 0
            },
            "outliers_low": [],
            "outliers_high": []
        })

    if results:
        outlier_df = get_salary_outliers_data()
        for item in results:
            dept_outliers = outlier_df[outlier_df["dept_name"] == item["dept_name"]]["salary"]
            q1_v = item["stats"]["q1"]
            q3_v = item["stats"]["q3"]
            iqr_v = q3_v - q1_v
            lo = dept_outliers[dept_outliers < q1_v - 1.5 * iqr_v]
            hi = dept_outliers[dept_outliers > q3_v + 1.5 * iqr_v]
            item["outliers_low"] = [round(float(v), 0) for v in lo]
            item["outliers_high"] = [round(float(v), 0) for v in hi]
            item["stats"]["outliers_low"] = int(len(lo))
            item["stats"]["outliers_high"] = int(len(hi))

    results.sort(key=lambda x: x["stats"]["median"], reverse=True)
    return {"departments": results}


def get_salary_evolution():
    df = get_salary_evolution_data()
    stats = []
    for r in df.itertuples(index=False):
        stats.append({
            "year": int(r.year),
            "mean": round(float(r.mean), 0),
            "median": round(float(r.median), 0),
            "std": round(float(r.std), 0) if r.std is not None else 0.0,
            "q1": round(float(r.q1), 0),
            "q3": round(float(r.q3), 0),
            "p10": round(float(r.p10), 0),
            "p90": round(float(r.p90), 0),
            "skew": round(float(r.skew), 3) if r.skew is not None else 0.0,
            "count": int(r.record_count)
        })
    return {"yearly": stats}


def get_salary_growth():
    rates_df = get_salary_growth_rates_data()
    curves_raw = get_salary_growth_curves_data()

    rates_df = rates_df.dropna().reset_index(drop=True)

    curves = []
    for emp_no, g in curves_raw.groupby("emp_no", sort=False):
        curves.append({
            "emp_no": int(emp_no),
            "dept": str(g["dept"].iloc[0]),
            "title": str(g["title"].iloc[0]),
            "actual": [{"x": int(row.x), "y": int(row.y)} for row in g.itertuples()]
        })

    if rates_df.empty:
        return {"dept": [], "title": [], "curves": curves}

    dept_agg = rates_df.groupby("dept_name").agg(
        avg=("growth", "mean"), median=("growth", "median"), n=("growth", "count")
    ).reset_index()
    title_agg = rates_df.groupby("title").agg(
        avg=("growth", "mean"), median=("growth", "median"), n=("growth", "count")
    ).reset_index()

    return {
        "dept": dept_agg.to_dict(orient="records"),
        "title": title_agg.to_dict(orient="records"),
        "curves": curves
    }


def get_external_benchmark():
    internal = get_external_benchmark_data()

    industry = pd.DataFrame([
        {"dept_name": "Development", "ind_avg": 75000, "ind_max": 140000, "function": "Technology"},
        {"dept_name": "Sales", "ind_avg": 72000, "ind_max": 140000, "function": "Commercial"},
        {"dept_name": "Marketing", "ind_avg": 68000, "ind_max": 115000, "function": "Commercial"},
        {"dept_name": "Finance", "ind_avg": 70000, "ind_max": 120000, "function": "Corporate"},
        {"dept_name": "Human Resources", "ind_avg": 58000, "ind_max": 90000, "function": "Corporate"},
        {"dept_name": "Production", "ind_avg": 55000, "ind_max": 82000, "function": "Operations"},
        {"dept_name": "Quality Management", "ind_avg": 60000, "ind_max": 88000, "function": "Operations"},
        {"dept_name": "Research", "ind_avg": 78000, "ind_max": 140000, "function": "Technology"},
        {"dept_name": "Customer Service", "ind_avg": 50000, "ind_max": 75000, "function": "Operations"},
    ])

    merged = pd.merge(internal, industry, on="dept_name", how="left")
    merged["diff_amount"] = merged["int_avg"] - merged["ind_avg"]
    merged["diff_pct"] = (merged["diff_amount"] / merged["ind_avg"] * 100).round(2)

    cpi_by_year = []
    for yr in range(1985, 2003):
        cpi = round(100 * (1.03 ** (yr - 1985)), 1)
        cpi_by_year.append({"year": yr, "cpi": cpi})

    result = []
    for _, r in merged.iterrows():
        result.append({
            "dept_name": r["dept_name"],
            "internal_avg": int(r["int_avg"]),
            "industry_avg": int(r["ind_avg"]),
            "diff_amount": int(r["diff_amount"]),
            "diff_pct": round(float(r["diff_pct"]), 2),
            "function": r["function"]
        })

    func_summary = merged.groupby("function").agg(
        internal=("int_avg", "mean"), industry=("ind_avg", "mean")
    ).reset_index()
    func_summary["diff_pct"] = ((func_summary["internal"] - func_summary["industry"]) / func_summary["industry"] * 100).round(2)

    return {
        "dept_comparison": sorted(result, key=lambda x: x["diff_pct"], reverse=True),
        "function_summary": func_summary.to_dict(orient="records"),
        "cpi_by_year": cpi_by_year
    }
