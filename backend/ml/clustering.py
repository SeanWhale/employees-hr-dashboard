# File: backend/ml/clustering.py
# -*- coding: utf-8 -*-
"""聚类算法封装 — KMeans / DBSCAN / PCA / 层次聚类"""
import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from scipy.cluster.hierarchy import linkage, fcluster


def compute_silhouette_scores(features):
    """计算 k=2..5 的轮廓系数"""
    sil_scores = []
    for k in range(2, 6):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(features)
        sil = silhouette_score(features, labels)
        sil_scores.append({"k": k, "silhouette": round(float(sil), 4)})
    return sil_scores


def find_best_k(sil_scores):
    """锁定 4 类员工画像：核心高薪层 / 中坚平稳层 / 年轻潜力层 / 基层起步层
       轮廓系数仍在 compute_silhouette_scores 中计算，供大屏图表展示历史对比数据。"""
    return 4


def run_kmeans(features, best_k):
    """KMeans 聚类，返回标签"""
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    return km.fit_predict(features)


def build_label_map(best_k):
    """构建聚类名称映射"""
    if best_k == 4:
        return {0: '核心高薪层', 1: '中坚平稳层', 2: '年轻潜力层', 3: '基层起步层'}
    return {i: f'群体{i+1}' for i in range(best_k)}


def compute_radar(df):
    """构建聚类雷达图数据"""
    radar = []
    for cn, g in df.groupby('cluster_name'):
        radar.append({
            "cluster_name": cn,
            "salary": round(float(g['salary'].mean()), 0),
            "tenure": round(float(g['tenure'].mean()), 1),
            "age": round(float(g['age'].mean()), 1),
            "count": int(len(g))
        })
    return radar


def run_hierarchical(features, best_k, df):
    """层次聚类 — Ward 法，构建 ECharts 嵌套树"""
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

    return {
        "linkage_matrix": Z.tolist(),
        "tree_data": build_echarts_tree(Z, len(features_sample)),
        "n_samples": len(features_sample),
        "n_clusters": int(len(np.unique(hc_labels)))
    }


def run_dbscan(features, df):
    """DBSCAN 密度聚类"""
    db = DBSCAN(eps=2.5, min_samples=10)
    db_labels = db.fit_predict(features)
    db_label_names = ["离群噪声点" if x == -1 else f"密集簇_{x}" for x in db_labels]

    return {
        "labels": db_labels.tolist(),
        "label_names": db_label_names,
        "n_clusters": int(len(set(db_labels)) - (1 if -1 in db_labels else 0)),
        "n_noise": int(sum(db_labels == -1)),
        "salary": df['salary'].tolist(),
        "tenure": df['tenure'].tolist()
    }


def run_pca(features, df):
    """PCA 降维至 2 维"""
    pca = PCA(n_components=2)
    pca_proj = pca.fit_transform(features)

    return {
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
