# File: backend/ml/stats_calc.py
# -*- coding: utf-8 -*-
"""统计计算封装 — Pearson / Mutual Info / Cosine / Euclidean / 回归拟合"""
import numpy as np
from scipy.spatial.distance import cosine, euclidean
from scipy.stats import pearsonr
from sklearn.linear_model import LinearRegression
from sklearn.feature_selection import mutual_info_regression


def compute_correlation_matrices(X):
    """计算 Pearson / Spearman / Partial / Mutual Info 四个 3×3 矩阵"""
    cols = ['salary', 'tenure', 'age']
    std_devs = X.std()
    if (std_devs == 0).any():
        pearson = np.eye(3).tolist()
        spearman = np.eye(3).tolist()
        partial = np.eye(3).tolist()
    else:
        try:
            pearson = X.corr().round(4).values.tolist()
            spearman = X.corr(method='spearman').round(4).values.tolist()

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

    mi = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            try:
                mi_val = mutual_info_regression(X.iloc[:, [i]].values, X.iloc[:, j].values)[0]
                mi[i][j] = round(float(mi_val), 4)
            except Exception:
                mi[i][j] = 0.0
    mi = mi.tolist()

    return pearson, spearman, partial, mi, cols


def to_echarts_heatmap(matrix, n_cols):
    """将 N×N 矩阵转为 ECharts 热力图三元组 [[x, y, value], ...]"""
    formatted = []
    for r_idx in range(n_cols):
        for c_idx in range(n_cols):
            formatted.append([c_idx, r_idx, matrix[r_idx][c_idx]])
    return formatted


def compute_regression(df):
    """拟合 tenure→salary 线性回归线及 95% 置信区间"""
    lr_scatter = LinearRegression()
    lr_scatter.fit(df[['tenure']].values, df['salary'].values)
    x_line = np.linspace(df['tenure'].min(), df['tenure'].max(), 50)
    y_line = lr_scatter.predict(x_line.reshape(-1, 1))

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
            ci.append({"x": round(float(x0), 1), "y_low": round(y0 - 1.96*se_y, 0),
                        "y_high": round(y0 + 1.96*se_y, 0)})

    regression = {
        "points": [{"x": float(r.tenure), "y": float(r.salary)} for r in df.itertuples()],
        "line": [{"x": round(float(x), 1), "y": round(float(y), 0)} for x, y in zip(x_line, y_line)],
        "ci": ci,
        "slope": round(float(lr_scatter.coef_[0]), 2),
        "intercept": round(float(lr_scatter.intercept_), 0),
        "r_squared": round(float(lr_scatter.score(df[['tenure']].values, df['salary'].values)), 4)
    }
    return regression


def compute_similarity_matrices(profiles, scaled, depts, n):
    """计算 Cosine 相似度和 Euclidean 距离矩阵"""
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
