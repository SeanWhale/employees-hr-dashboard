# File: backend/services/advanced_srv.py
# -*- coding: utf-8 -*-
"""高级分析服务 — 调用 DAO + ML 模块，严格组装原 analytics.py 的 JSON 格式"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, OneHotEncoder

from backend.core.config import DATASET_MAX_DATE

try:
    from dao.advanced_dao import (get_clustering_data, get_correlation_data,
                                    get_dept_forecast_data, get_forecast_data,
                                    get_gender_dept_data, get_gender_promo_data,
                                    get_retention_data, get_sankey_data,
                                    get_similarity_data, get_stability_by_dept,
                                    get_title_transition_data)
except ImportError:
    from backend.dao.advanced_dao import (get_clustering_data, get_correlation_data,
                                            get_dept_forecast_data, get_forecast_data,
                                            get_gender_dept_data, get_gender_promo_data,
                                            get_retention_data, get_sankey_data,
                                            get_similarity_data, get_stability_by_dept,
                                            get_title_transition_data)

try:
    from ml.clustering import (build_label_map, compute_radar, compute_silhouette_scores,
                                 find_best_k, run_dbscan, run_hierarchical, run_kmeans,
                                 run_pca)
except ImportError:
    from backend.ml.clustering import (build_label_map, compute_radar, compute_silhouette_scores,
                                         find_best_k, run_dbscan, run_hierarchical, run_kmeans,
                                         run_pca)

try:
    from ml.forecasting import train_dept_forecast, train_forecast_models
except ImportError:
    from backend.ml.forecasting import train_dept_forecast, train_forecast_models

try:
    from ml.stats_calc import (compute_correlation_matrices, compute_regression,
                                 compute_similarity_matrices, to_echarts_heatmap)
except ImportError:
    from backend.ml.stats_calc import (compute_correlation_matrices, compute_regression,
                                         compute_similarity_matrices, to_echarts_heatmap)


# ============================================================
#  3. 多模型聚类
# ============================================================
def get_clustering():
    raw_df = get_clustering_data()

    if raw_df.empty:
        return {"scatter": [], "radar": [], "silhouette": [], "hierarchical": {}, "dbscan": {}, "pca": {}}

    df = raw_df.reset_index(drop=True)

    num = df[['salary', 'tenure', 'age']]
    scaler = StandardScaler()
    scaled_num = scaler.fit_transform(num)

    enc_d = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    dept_enc = enc_d.fit_transform(df[['dept_name']])
    enc_t = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    title_enc = enc_t.fit_transform(df[['title']])

    features = np.hstack([scaled_num, dept_enc, title_enc])

    sil_scores = compute_silhouette_scores(features)
    best_k = find_best_k(sil_scores)
    df['cluster'] = run_kmeans(features, best_k)

    label_map = build_label_map(best_k)
    df['cluster_name'] = df['cluster'].map(label_map)

    radar = compute_radar(df)

    comparison = [
        {
            "cluster_name": r["cluster_name"],
            "avg_salary": r["salary"],
            "avg_tenure": r["tenure"],
            "avg_age": r["age"],
            "count": r["count"]
        }
        for r in radar
    ]

    hierarchical = run_hierarchical(features, best_k, df)
    dbscan_result = run_dbscan(features, df)
    pca_result = run_pca(features, df)

    dept_mapping = {
        "Development": 0, "Sales": 1, "Marketing": 2, "Finance": 3,
        "Human Resources": 4, "Production": 5, "Quality Management": 6,
        "Research": 7, "Customer Service": 8
    }
    points_3d = []
    for _, r in df.iterrows():
        points_3d.append([
            float(r['tenure']),
            float(r['salary']),
            dept_mapping.get(r['dept_name'], -1),
            r['dept_name'],
            r['cluster_name']
        ])

    return {
        "scatter": df[['emp_no', 'salary', 'tenure', 'age', 'dept_name', 'title', 'cluster_name']].to_dict(orient="records"),
        "radar": radar,
        "silhouette": sil_scores,
        "hierarchical": hierarchical,
        "comparison": comparison,
        "dbscan": dbscan_result,
        "pca": pca_result,
        "points_3d": points_3d,
        "best_k": best_k,
        "as_of_date": DATASET_MAX_DATE
    }


# ============================================================
#  5. 多模型预测
# ============================================================
def get_forecast():
    raw = get_forecast_data()

    if raw.empty:
        return {"models": [], "comparison": []}

    train = raw[raw['yr'] <= 1996]
    X_train = train[['yr']].values
    y_train = train['avg_s'].values

    X_all = raw[['yr']].values
    n_train = len(train)

    models = train_forecast_models(X_train, y_train, X_all, raw, n_train)

    years = [int(y) for y in raw['yr']]
    actuals = [float(v) for v in raw['avg_s']]

    comparison = [{"name": m["name"], **m["metrics"]} for m in models]
    best = min(comparison, key=lambda x: x['rmse'])

    return {
        "years": years,
        "actuals": actuals,
        "models": models,
        "comparison": comparison,
        "best_model": best['name']
    }


# ============================================================
#  6. 相关性分析
# ============================================================
def get_correlation():
    raw_df = get_correlation_data()

    if raw_df.empty:
        return {}

    df = raw_df.reset_index(drop=True)

    pearson, spearman, partial, mi, labels = compute_correlation_matrices(df)

    regression = compute_regression(df)

    return {
        "labels": labels,
        "pearson": pearson,
        "spearman": spearman,
        "partial": partial,
        "mutual_info": mi,
        "pearson_heatmap": to_echarts_heatmap(pearson, len(labels)),
        "spearman_heatmap": to_echarts_heatmap(spearman, len(labels)),
        "partial_heatmap": to_echarts_heatmap(partial, len(labels)),
        "mutual_info_heatmap": to_echarts_heatmap(mi, len(labels)),
        "regression": regression
    }


# ============================================================
#  7. 相似性分析
# ============================================================
def get_similarity():
    df = get_similarity_data()

    profiles = {}
    for r in df.itertuples(index=False):
        profiles[r.dept_name] = np.array([
            float(r.avg_salary), float(r.avg_tenure), float(r.avg_age),
            float(r.emp_count), float(r.std_salary)
        ])

    depts = sorted(profiles.keys())
    n = len(depts)
    all_vecs = np.array([profiles[d] for d in depts])
    scaler = StandardScaler()
    scaled = scaler.fit_transform(all_vecs)

    return compute_similarity_matrices(profiles, scaled, depts, n)


# ============================================================
#  8. 职级流动桑基图
# ============================================================
def get_title_sankey():
    df = get_sankey_data()

    if df.empty:
        return {"nodes": [], "links": []}

    # 入职 → 最终：天然有向无环，无需消环/DAG 贪心
    all_titles = pd.unique(df[["source", "target"]].values.ravel("K"))
    nodes = [{"name": str(t)} for t in all_titles]
    links = df.to_dict(orient="records")

    return {"nodes": nodes, "links": links}


# ============================================================
#  10. 性别分析
# ============================================================
def get_gender_analysis():
    dept_gender = get_gender_dept_data()
    promo = get_gender_promo_data()

    dept_ratio = []
    for dept, g in dept_gender.groupby("dept_name"):
        m = g[g['gender'] == 'M']
        f = g[g['gender'] == 'F']
        mc = int(m['cnt'].values[0]) if len(m) > 0 else 0
        fc = int(f['cnt'].values[0]) if len(f) > 0 else 0
        tot = mc + fc
        dept_ratio.append({
            "dept_name": dept, "M": mc, "F": fc,
            "M_pct": round(mc/tot*100, 1) if tot > 0 else 0,
            "F_pct": round(fc/tot*100, 1) if tot > 0 else 0
        })

    dept_salary = []
    for _, r in dept_gender.iterrows():
        dept_salary.append({
            "dept_name": r['dept_name'], "gender": r['gender'],
            "avg_salary": int(r['avg_s']), "median_salary": int(r['med_s']),
            "avg_tenure": round(float(r['avg_tenure']), 1)
        })

    promo_data = []
    for _, r in promo.iterrows():
        promo_data.append({
            "gender": r['gender'],
            "total": int(r['total']),
            "avg_title_changes": round(float(r['avg_changes']), 2)
        })

    return {
        "dept_ratio": dept_ratio,
        "dept_salary": dept_salary,
        "promotion": promo_data
    }


# ============================================================
#  11. 职级转岗耗时
# ============================================================
def get_title_transition():
    df = get_title_transition_data()

    if df.empty:
        return {"box_data": [], "detail": []}

    box_data = []
    detail = []
    for r in df.itertuples(index=False):
        key = f"{r.from_t}→{r.to_t}"
        detail.append({
            "path": key, "from": r.from_t, "to": r.to_t,
            "count": int(r.cnt), "avg_years": round(float(r.avg_y), 2),
            "p50_years": round(float(r.median_y), 2)
        })
        box_data.append({
            "name": key,
            "data": [round(float(r.min_y), 2), round(float(r.q1_y), 2),
                     round(float(r.median_y), 2), round(float(r.q3_y), 2),
                     round(float(r.max_y), 2)]
        })

    box_data.sort(key=lambda x: x["data"][2])
    return {"box_data": box_data[:30], "detail": detail}


# ============================================================
#  15. 留任度分析
# ============================================================
def get_retention():
    merged = get_retention_data()

    merged["total"] = merged["dc"] + merged["tc"]

    merged["category"] = np.select(
        [merged["total"] <= 1, merged["total"] <= 3],
        ["stable", "moderate"],
        default="frequent"
    )

    labels = {"stable": "稳定型(≤1次)", "moderate": "适中型(2-3次)", "frequent": "高频型(>3次)"}
    colors_map = {"stable": "#2ed573", "moderate": "#f6e05e", "frequent": "#ff4757"}

    employees = []
    for r in merged.itertuples(index=False):
        employees.append({
            "emp_no": int(r.emp_no), "salary": int(r.salary),
            "dept_changes": int(r.dc), "title_changes": int(r.tc),
            "total_changes": int(r.total), "category": r.category,
            "dept": r.dept_name, "title": r.title
        })

    summary = []
    for cat, g in merged.groupby("category"):
        summary.append({
            "category": cat, "label": labels.get(cat, cat),
            "count": int(len(g)),
            "avg_salary": round(float(g["salary"].mean()), 0),
            "avg_dept_changes": round(float(g["dc"].mean()), 2),
            "avg_title_changes": round(float(g["tc"].mean()), 2),
            "pct": round(len(g) / len(merged) * 100, 1)
        })

    return {"employees": employees, "summary": summary, "labels": labels, "colors": colors_map}


# ============================================================
#  16. 部门稳定性构成
# ============================================================
def get_dept_stability():
    df = get_stability_by_dept()

    if df.empty:
        return {"departments": [], "datasets": {}}

    departments = sorted(df['dept_name'].unique().tolist())

    label_order = ['已离职', '在职-稳定未调岗', '在职-内部流动/晋升']
    datasets = {label: [] for label in label_order}

    for dept in departments:
        dept_data = df[df['dept_name'] == dept]
        for label in label_order:
            row = dept_data[dept_data['stability_label'] == label]
            datasets[label].append(int(row['cnt'].values[0]) if len(row) > 0 else 0)

    return {"departments": departments, "datasets": datasets}


# ============================================================
#  17. 分部门预测
# ============================================================
def get_dept_forecast():
    df = get_dept_forecast_data()

    departments = []
    comparison = []
    for dept, g in df.groupby("dept_name", sort=False):
        g = g.sort_values("year")
        result = train_dept_forecast(g, dept)
        if result is None:
            continue
        departments.append(result)
        comparison.append({
            "dept_name": dept,
            "mae": result["mae"], "rmse": result["rmse"], "mape": result["mape"]
        })

    comparison.sort(key=lambda x: x["mae"])
    return {"departments": departments, "comparison": comparison}
