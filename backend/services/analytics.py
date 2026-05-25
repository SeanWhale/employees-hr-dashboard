# File: backend/services/analytics.py
# -*- coding: utf-8 -*-
"""HR 大数据分析引擎 — 聚类/预测/相关性/相似性/外部数据联动"""
import os
import sys
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler, OneHotEncoder, PolynomialFeatures
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.feature_selection import mutual_info_regression
from sklearn.pipeline import Pipeline
from scipy.spatial.distance import cosine, euclidean
from scipy.stats import pearsonr

from backend.core.db import get_connection, get_parquet_path
from backend.core.config import DATASET_MAX_DATE

get_connection = get_connection
get_parquet_path = get_parquet_path
DATASET_MAX_DATE = DATASET_MAX_DATE


# ============================================================
#  1. 核心 KPI (解决问题 12)
# ============================================================
def get_kpi():
    con = get_connection()
    row = con.execute("""
        SELECT COUNT(*) AS total, CAST(AVG(salary) AS INT) AS avg_s,
               MAX(salary) AS max_s, MIN(salary) AS min_s,
               CAST(STDDEV(salary) AS INT) AS std_s
        FROM current_employees
    """).df().fillna(0).to_dict(orient="records")[0]
    row["as_of_date"] = DATASET_MAX_DATE
    return row


# ============================================================
#  2. 部门分布
# ============================================================
def get_dept_distribution():
    con = get_connection()
    df = con.execute("""
        SELECT dept_name, COUNT(*) AS emp_count,
               CAST(AVG(salary) AS INT) AS avg_salary,
               CAST(MEDIAN(salary) AS INT) AS median_salary,
               MIN(salary) AS min_salary, MAX(salary) AS max_salary,
               CAST(STDDEV(salary) AS INT) AS std_salary
        FROM current_employees
        GROUP BY dept_name ORDER BY avg_salary DESC
    """).df()
    return df.to_dict(orient="records")


# ============================================================
#  3. 多模型聚类 (解决问题 7, 12)
# ============================================================
def get_clustering():
    con = get_connection()
    
    # 时态锚点校准至 2002-08-01
    raw_df = con.execute(f"""
        SELECT emp_no, salary, dept_name, title,
               DATEDIFF('year', CAST(hire_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS tenure,
               DATEDIFF('year', CAST(birth_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS age
        FROM current_employees
        ORDER BY hash(emp_no)
        LIMIT 5000
    """).df()

    if raw_df.empty:
        return {"scatter": [], "radar": [], "silhouette": [], "hierarchical": {}, "dbscan": {}, "pca": {}}

    df = raw_df.reset_index(drop=True)

    # 特征工程
    num = df[['salary', 'tenure', 'age']]
    scaler = StandardScaler()
    scaled_num = scaler.fit_transform(num)

    enc_d = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    dept_enc = enc_d.fit_transform(df[['dept_name']])
    enc_t = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    title_enc = enc_t.fit_transform(df[['title']])

    features = np.hstack([scaled_num, dept_enc, title_enc])

    # 轮廓系数寻找最优 K
    sil_scores = []
    for k in range(2, 6):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(features)
        sil = silhouette_score(features, labels)
        sil_scores.append({"k": k, "silhouette": round(float(sil), 4)})

    best_k = max(sil_scores, key=lambda x: x['silhouette'])['k'] if sil_scores else 4
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['cluster'] = km.fit_predict(features)

    label_map = {0: '核心高薪层', 1: '中坚平稳层', 2: '年轻潜力层', 3: '基层起步层'}
    if best_k != 4:
        label_map = {i: f'群体{i+1}' for i in range(best_k)}
    df['cluster_name'] = df['cluster'].map(label_map)

    # 聚类中心
    radar = []
    for cn, g in df.groupby('cluster_name'):
        radar.append({
            "cluster_name": cn,
            "salary": round(float(g['salary'].mean()), 0),
            "tenure": round(float(g['tenure'].mean()), 1),
            "age": round(float(g['age'].mean()), 1),
            "count": int(len(g))
        })

    # 聚类对比 (前端 ECharts 柱线混合图直接消费)
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

    # 层次聚类 (ECharts 嵌套格式重建)
    from scipy.cluster.hierarchy import linkage, fcluster
    features_sample = features[:300]
    Z = linkage(features_sample, method='ward')
    hc_labels = fcluster(Z, t=best_k, criterion='maxclust')

    def build_echarts_tree(Z_matrix, n_samples):
        nodes = [{"name": f"Emp {df.loc[i, 'emp_no']}"} for i in range(n_samples)]
        for i, row in enumerate(Z_matrix):
            left_idx, right_idx = int(row[0]), int(row[1])
            dist = float(row[2])
            parent_node = {
                "name": f"Node {n_samples + i} (d: {dist:.1f})",
                "children": [nodes[left_idx], nodes[right_idx]]
            }
            nodes.append(parent_node)
        return nodes[-1]

    hierarchical = {
        "linkage_matrix": Z.tolist(),
        "tree_data": build_echarts_tree(Z, len(features_sample)),
        "n_samples": len(features_sample),
        "n_clusters": int(len(np.unique(hc_labels)))
    }

    # DBSCAN (解决问题 7: 显式映射 -1 噪声点)
    db = DBSCAN(eps=2.5, min_samples=10)
    db_labels = db.fit_predict(features)
    db_label_names = ["离群噪声点" if x == -1 else f"密集簇_{x}" for x in db_labels]
    
    dbscan_result = {
        "labels": db_labels.tolist(),
        "label_names": db_label_names,
        "n_clusters": int(len(set(db_labels)) - (1 if -1 in db_labels else 0)),
        "n_noise": int(sum(db_labels == -1)),
        "salary": df['salary'].tolist(),
        "tenure": df['tenure'].tolist()
    }

    # PCA 投影
    pca = PCA(n_components=2)
    pca_proj = pca.fit_transform(features)
    pca_result = {
        "x": [round(float(v[0]), 2) for v in pca_proj],
        "y": [round(float(v[1]), 2) for v in pca_proj],
        "cluster": df['cluster'].tolist(),
        "cluster_name": df['cluster_name'].tolist(),
        "explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "salary": df['salary'].tolist(),
        "tenure": df['tenure'].tolist(),
        "age": df['age'].tolist(),
        "dept": df['dept_name'].tolist()
    }

    return {
        "scatter": df[['emp_no', 'salary', 'tenure', 'age', 'dept_name', 'title', 'cluster_name']].to_dict(orient="records"),
        "radar": radar,
        "silhouette": sil_scores,
        "hierarchical": hierarchical,
        "comparison": comparison,
        "dbscan": dbscan_result,
        "pca": pca_result,
        "best_k": best_k,
        "as_of_date": DATASET_MAX_DATE
    }


# ============================================================
#  4. 薪资历史 (解决问题 14: 强制排序去重)
# ============================================================
def get_salary_history():
    con = get_connection()
    df = con.execute("SELECT * FROM yearly_salary ORDER BY year, avg_salary DESC").df()
    # 强制进行时间排序，防止不连续年份导致的折线图突变
    df = df.sort_values(["year", "dept_name"]).reset_index(drop=True)
    return df.to_dict(orient="records")


# ============================================================
#  5. 多模型预测与验证 (解决问题 6: 解决 ECharts 折线断开)
# ============================================================
def get_forecast():
    con = get_connection()
    s_path = get_parquet_path("load_salaries*.parquet")
    
    raw = con.execute(f"""
        SELECT CAST(EXTRACT(YEAR FROM from_date) AS INT) AS yr, AVG(salary) AS avg_s
        FROM read_parquet('{s_path}')
        WHERE EXTRACT(YEAR FROM from_date) BETWEEN 1985 AND 2002
        GROUP BY yr ORDER BY yr
    """).df()

    if raw.empty:
        return {"models": [], "comparison": []}

    train = raw[raw['yr'] <= 1996]
    X_train = train[['yr']].values
    y_train = train['avg_s'].values
    
    # 预测区间的 X 轴对齐
    test_df = raw[raw['yr'] >= 1997]
    X_test = test_df[['yr']].values
    actual_test = test_df['avg_s'].values

    years = [int(y) for y in raw['yr']]
    actuals = [float(v) for v in raw['avg_s']]
    n_train = len(train)

    models = []
    for name, model in [
        ("线性回归", LinearRegression()),
        ("二次多项式", Pipeline([('poly', PolynomialFeatures(2)), ('lr', LinearRegression())])),
        ("三次多项式", Pipeline([('poly', PolynomialFeatures(3)), ('lr', LinearRegression())]))
    ]:
        model.fit(X_train, y_train)
        pred_all = model.predict(raw[['yr']].values)
        pred_test = model.predict(X_test)

        residuals = actual_test - pred_test
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        mape = float(np.mean(np.abs(residuals / actual_test)) * 100)

        denom = np.sum((actual_test - np.mean(actual_test))**2)
        r2 = float(1 - np.sum(residuals**2) / denom) if denom != 0 else 0.0

        # 残差在训练期填充 None，使其与完整年份数组对齐，避免 ECharts 错位
        residual_values = [round(float(r), 0) for r in residuals.tolist()]
        padded_residuals = [None] * n_train + residual_values

        models.append({
            "name": name,
            "predictions": [round(float(p), 0) for p in pred_all],
            "metrics": {"mae": round(mae, 0), "rmse": round(rmse, 0), "mape": round(mape, 2), "r2": round(r2, 4)},
            "residuals": padded_residuals,
            "test_years": [int(y) for y in test_df['yr']]
        })

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
#  6. 相关性分析 (解决问题 8: 零方差保护, 问题 10: ECharts 热力图三元组)
# ============================================================
def get_correlation():
    con = get_connection()
    
    raw_df = con.execute(f"""
        SELECT salary, dept_name, title,
               DATEDIFF('year', CAST(hire_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS tenure,
               DATEDIFF('year', CAST(birth_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE)) AS age
        FROM current_employees
        ORDER BY hash(emp_no)
        LIMIT 5000
    """).df()

    if raw_df.empty:
        return {}

    df = raw_df.reset_index(drop=True)
    cols = ['salary', 'tenure', 'age']
    X = df[cols].astype(float)

    # 解决问题 8：引入标准差检查，防止零方差引发除以零崩溃
    std_devs = X.std()
    if (std_devs == 0).any():
        pearson = np.eye(3).tolist()
        spearman = np.eye(3).tolist()
        partial = np.eye(3).tolist()
    else:
        try:
            pearson = X.corr().round(4).values.tolist()
            spearman = X.corr(method='spearman').round(4).values.tolist()
            
            # 偏相关计算（保护性容错）
            partial = np.zeros((3, 3))
            lr_partial = LinearRegression() 
            for i in range(3):
                for j in range(3):
                    if i == j:
                        partial[i][j] = 1.0
                    else:
                        k = 3 - i - j
                        ri, rj, rk = X.iloc[:, i], X.iloc[:, j], X.iloc[:, k]
                        lr_partial.fit(rk.values.reshape(-1, 1), ri.values)
                        ri_res = ri.values - lr_partial.predict(rk.values.reshape(-1, 1)).ravel()
                        lr_partial.fit(rk.values.reshape(-1, 1), rj.values)
                        rj_res = rj.values - lr_partial.predict(rk.values.reshape(-1, 1)).ravel()
                        
                        r_val, _ = pearsonr(ri_res, rj_res)
                        partial[i][j] = round(r_val, 4) if not np.isnan(r_val) else 0.0
            partial = partial.tolist()
        except Exception:
            pearson = np.eye(3).tolist()
            spearman = np.eye(3).tolist()
            partial = np.eye(3).tolist()

    # 互信息
    mi = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            try:
                mi_val = mutual_info_regression(X.iloc[:, [i]].values, X.iloc[:, j].values)[0]
                mi[i][j] = round(float(mi_val), 4)
            except Exception:
                mi[i][j] = 0.0
    mi = mi.tolist()

    # 解决问题 10：将 3x3 矩阵直接平铺为 ECharts 期待的三元组数据 [[x, y, value], ...]
    def to_echarts_heatmap(matrix):
        formatted = []
        for r_idx in range(len(cols)):
            for c_idx in range(len(cols)):
                formatted.append([c_idx, r_idx, matrix[r_idx][c_idx]])
        return formatted

    # 拟合回归线
    lr_scatter = LinearRegression()
    lr_scatter.fit(df[['tenure']].values, df['salary'].values)
    x_line = np.linspace(df['tenure'].min(), df['tenure'].max(), 50)
    y_line = lr_scatter.predict(x_line.reshape(-1, 1))

    # 计算置信区间
    n = len(df)
    x_mean = float(df['tenure'].mean())
    sxx = float(((df['tenure'] - x_mean) ** 2).sum())
    resid = df['salary'].values - lr_scatter.predict(df[['tenure']].values)
    se = float(np.sqrt(np.sum(resid**2) / (n - 2))) if n > 2 else 0

    ci = []
    if se > 0 and sxx > 0:
        for x0 in np.linspace(df['tenure'].min(), df['tenure'].max(), 30):
            y0 = float(lr_scatter.predict(np.array([[x0]]))[0])
            se_y = se * np.sqrt(1/n + (x0 - x_mean)**2 / sxx)
            ci.append({"x": round(float(x0), 1), "y_low": round(y0 - 1.96*se_y, 0), "y_high": round(y0 + 1.96*se_y, 0)})

    regression = {
        "points": [{"x": float(r.tenure), "y": float(r.salary)} for r in df.itertuples()],
        "line": [{"x": round(float(x), 1), "y": round(float(y), 0)} for x, y in zip(x_line, y_line)],
        "ci": ci,
        "slope": round(float(lr_scatter.coef_[0]), 2),
        "intercept": round(float(lr_scatter.intercept_), 0),
        "r_squared": round(float(lr_scatter.score(df[['tenure']].values, df['salary'].values)), 4)
    }

    return {
        "labels": cols,
        "pearson": pearson,
        "spearman": spearman,
        "partial": partial,
        "mutual_info": mi,
        "pearson_heatmap": to_echarts_heatmap(pearson),
        "spearman_heatmap": to_echarts_heatmap(spearman),
        "partial_heatmap": to_echarts_heatmap(partial),
        "mutual_info_heatmap": to_echarts_heatmap(mi),
        "regression": regression
    }


# ============================================================
#  7. 相似性分析 (解决问题 1: 消除 30 万行物理加载)
# ============================================================
def get_similarity():
    con = get_connection()
    
    # 解决问题 1：将计算完全下推至 DuckDB，只返回 9 行部门聚合指标
    df = con.execute(f"""
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

    cosine_sim = np.zeros((n, n))
    euclidean_dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            cosine_sim[i][j] = round(float(1 - cosine(scaled[i], scaled[j])), 4)
            euclidean_dist[i][j] = round(float(euclidean(scaled[i], scaled[j])), 4)

    return {
        "departments": depts,
        "cosine_similarity": cosine_sim.tolist(),
        "euclidean_distance": euclidean_dist.tolist()
    }


# ============================================================
#  8. 职级流动桑基图 (解决问题 3: 消除 transitions 字典列表)
# ============================================================
def get_title_sankey():
    con = get_connection()
    t_path = get_parquet_path("load_titles.parquet")
    
    # 彻底告别 itertuples 转换，由 SQL 一步搞定拓扑关系聚合
    df = con.execute(f"""
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

    if df.empty:
        return {"nodes": [], "links": []}

    # 消除双向环路：对每对 (A,B)，仅保留人流量更大的方向，确保桑基图 DAG 合法
    df['pair_key'] = df.apply(lambda r: tuple(sorted([r['source'], r['target']])), axis=1)
    df = df.loc[df.groupby('pair_key')['value'].idxmax()].drop(columns=['pair_key'])

    all_titles = pd.unique(df[["source", "target"]].values.ravel("K"))
    nodes = [{"name": str(t)} for t in all_titles]
    links = df.to_dict(orient="records")

    return {"nodes": nodes, "links": links}


# ============================================================
#  9. 薪资分布 (解决问题 2: 消除 30 万行物理加载)
# ============================================================
def get_salary_distribution():
    con = get_connection()
    
    # 解决问题 2：利用 SQL 算子聚合箱线图所需的五个核心分位数，内存开销几乎降为零
    df = con.execute("""
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

    # SQL 聚合后，再在 Python 端计算每部门的离群薪资点 (避免两次全表扫描)
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

    # 仅一次 SQL 查询，利用 DuckDB 本地谓词下推，按需加载各部门离群值，内存占用量压至最低
    if results:
        # 在 DuckDB 中基于分位数计算所有部门的离群判定边界
        outlier_df = con.execute("""
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


# ============================================================
#  10. 性别分析
# ============================================================
def get_gender_analysis():
    con = get_connection()
    e_path = get_parquet_path("load_employees.parquet")
    t_path = get_parquet_path("load_titles.parquet")

    dept_gender = con.execute(f"""
        SELECT gender, dept_name, COUNT(*) AS cnt,
               CAST(AVG(salary) AS INT) AS avg_s,
               CAST(MEDIAN(salary) AS INT) AS med_s,
               CAST(AVG(DATEDIFF('year', CAST(hire_date AS DATE), CAST('{DATASET_MAX_DATE}' AS DATE))) AS FLOAT) AS avg_tenure
        FROM current_employees
        GROUP BY gender, dept_name ORDER BY dept_name, gender
    """).df()

    promo = con.execute(f"""
        SELECT e.gender, COUNT(*) AS total, SUM(tc) AS total_changes, AVG(tc) AS avg_changes
        FROM (
            SELECT emp_no, COUNT(DISTINCT title)-1 AS tc FROM read_parquet('{t_path}') GROUP BY emp_no
        ) t
        JOIN read_parquet('{e_path}') e ON t.emp_no = e.emp_no
        GROUP BY e.gender
    """).df()

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
#  11. 职级转岗耗时 (解决问题 15: 说明 365.25 时间换算基础)
# ============================================================
def get_title_transition():
    con = get_connection()
    t_path = get_parquet_path("load_titles.parquet")
    
    # 解决问题 15：在 SQL 层面执行精确的 DATEDIFF 计算天数，备注标准回归年天数 365.25 的平摊误差
    df = con.execute(f"""
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
#  12. 薪资演变
# ============================================================
def get_salary_evolution():
    con = get_connection()
    s_path = get_parquet_path("load_salaries*.parquet")
    
    df = con.execute(f"""
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


# ============================================================
#  13. 外部数据联动
# ============================================================
def get_external_benchmark():
    con = get_connection()
    internal = con.execute("""
        SELECT dept_name, CAST(AVG(salary) AS INT) AS int_avg,
               CAST(MEDIAN(salary) AS INT) AS int_median, MAX(salary) AS int_max
        FROM current_employees GROUP BY dept_name
    """).df()

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


# ============================================================
#  14. 办公地图 (模拟中国城市)
# ============================================================
def get_office_map():
    con = get_connection()
    city_sql = """
        CASE
            WHEN dept_name IN ('Finance', 'Human Resources') THEN '北京'
            WHEN dept_name IN ('Sales', 'Marketing') THEN '上海'
            WHEN dept_name = 'Development' THEN '深圳'
            WHEN dept_name IN ('Production', 'Quality Management') THEN '广州'
            WHEN dept_name IN ('Customer Service', 'Research') THEN '成都'
            ELSE '北京'
        END AS city
    """
    df = con.execute(f"""
        SELECT {city_sql}, COUNT(*) AS cnt,
               CAST(AVG(salary) AS INT) AS avg_s, CAST(MEDIAN(salary) AS INT) AS med_s
        FROM current_employees GROUP BY city
    """).df()

    coords = {
        '北京': [116.40, 39.90], '上海': [121.47, 31.23], '深圳': [114.05, 22.54],
        '广州': [113.26, 23.13], '成都': [104.06, 30.67]
    }

    result = []
    for _, r in df.iterrows():
        city = r['city']
        coord = coords.get(city, [116.40, 39.90])
        result.append({
            "name": city,
            "value": [coord[0], coord[1], int(r['avg_s']), int(r['cnt'])]
        })
    return result


# ============================================================
#  15. 留任度分析 (解决问题 5: 避免 dc/tc 30 万行大表物理扫描, 问题 9: 区分 0/1 次变更)
# ============================================================
def get_retention():
    con = get_connection()
    de_path = get_parquet_path("load_dept_emp.parquet")
    t_path = get_parquet_path("load_titles.parquet")

    # 解决问题 5：不再全表聚合 dc/tc，在 SQL 中先将数据范围锁定在 5000 抽样员工内
    merged = con.execute(f"""
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
#  16. 分部门预测
# ============================================================
def get_dept_forecast():
    con = get_connection()
    df = con.execute("""
        SELECT year, dept_name, avg_salary AS avg_s 
        FROM yearly_salary 
        ORDER BY dept_name, year
    """).df()

    departments = []
    comparison = []
    for dept, g in df.groupby("dept_name", sort=False):
        g = g.sort_values("year")
        train = g[g["year"] <= 1996]
        if len(train) < 3:
            continue

        X_train = train[["year"]].values
        y_train = train["avg_s"].values
        lr = LinearRegression()
        lr.fit(X_train, y_train)

        yrs = g["year"].values
        actual = g["avg_s"].values
        pred = lr.predict(g[["year"]].values)

        test_mask = yrs >= 1997
        res = actual[test_mask] - pred[test_mask]
        mae = float(np.mean(np.abs(res))) if len(res) > 0 else 0
        rmse = float(np.sqrt(np.mean(res**2))) if len(res) > 0 else 0
        
        denom_mask = (actual[test_mask] != 0)
        mape = float(np.mean(np.abs(res[denom_mask]) / actual[test_mask][denom_mask]) * 100) if any(denom_mask) else 0

        departments.append({
            "dept_name": dept,
            "data": [{"year": int(y), "actual": round(float(a), 0), "prediction": round(float(p), 0)} for y, a, p in zip(yrs, actual, pred)],
            "slope": round(float(lr.coef_[0]), 1),
            "mae": round(mae, 0), "rmse": round(rmse, 0), "mape": round(mape, 2)
        })
        comparison.append({"dept_name": dept, "mae": round(mae, 0), "rmse": round(rmse, 0), "mape": round(mape, 2)})

    comparison.sort(key=lambda x: x["mae"])
    return {"departments": departments, "comparison": comparison}


# ============================================================
#  17. 薪资增长曲线 (解决问题 4: 消除临时表缓存复制与多重载入)
# ============================================================
def get_salary_growth():
    con = get_connection()
    s_path = get_parquet_path("load_salaries*.parquet")
    e_path = get_parquet_path("load_employees.parquet")

    # 使用 CTE 而非 TEMP TABLE，避免单例连接下并发请求间的数据串扰
    salary_yrs_cte = f"""
        salary_yrs AS (
            SELECT s.emp_no, s.salary,
                   CAST(EXTRACT(YEAR FROM s.from_date) - EXTRACT(YEAR FROM e.hire_date) AS INT) AS yrs,
                   ce.dept_name, ce.title
            FROM read_parquet('{s_path}') s
            JOIN read_parquet('{e_path}') e ON s.emp_no = e.emp_no
            JOIN current_employees ce ON s.emp_no = ce.emp_no
            WHERE s.salary > 0
        )
    """

    rates_df = con.execute(f"""
        WITH {salary_yrs_cte},
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

    rates_df = rates_df.dropna().reset_index(drop=True)

    # 抽取 50 条曲线供前端绘制多折线演化
    curves_raw = con.execute(f"""
        WITH {salary_yrs_cte},
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