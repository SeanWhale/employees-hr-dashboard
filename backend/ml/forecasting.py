# File: backend/ml/forecasting.py
# -*- coding: utf-8 -*-
"""预测算法封装 — LinearRegression / PolynomialFeatures"""
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline


def train_forecast_models(X_train, y_train, X_all, raw, n_train):
    """训练 3 个预测模型（线性 / 二次 / 三次），计算评估指标"""
    test_mask = raw['yr'] >= 1997
    X_test = raw[test_mask][['yr']].values
    actual_test = raw[test_mask]['avg_s'].values

    models = []
    for name, model in [
        ("线性回归", LinearRegression()),
        ("二次多项式", Pipeline([('poly', PolynomialFeatures(2)), ('lr', LinearRegression())])),
        ("三次多项式", Pipeline([('poly', PolynomialFeatures(3)), ('lr', LinearRegression())]))
    ]:
        model.fit(X_train, y_train)
        pred_all = model.predict(X_all)
        pred_test = model.predict(X_test)

        residuals = actual_test - pred_test
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        mape = float(np.mean(np.abs(residuals / actual_test)) * 100)

        denom = np.sum((actual_test - np.mean(actual_test))**2)
        r2 = float(1 - np.sum(residuals**2) / denom) if denom != 0 else 0.0

        residual_values = [round(float(r), 0) for r in residuals.tolist()]
        padded_residuals = [None] * n_train + residual_values

        models.append({
            "name": name,
            "predictions": [round(float(p), 0) for p in pred_all],
            "metrics": {"mae": round(mae, 0), "rmse": round(rmse, 0), "mape": round(mape, 2), "r2": round(r2, 4)},
            "residuals": padded_residuals,
            "test_years": [int(y) for y in raw[test_mask]['yr']]
        })

    return models


def train_dept_forecast(g, dept):
    """单个部门的线性回归预测"""
    train = g[g["year"] <= 1996]
    if len(train) < 3:
        return None

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

    return {
        "dept_name": dept,
        "data": [{"year": int(y), "actual": round(float(a), 0), "prediction": round(float(p), 0)}
                 for y, a, p in zip(yrs, actual, pred)],
        "slope": round(float(lr.coef_[0]), 1),
        "mae": round(mae, 0), "rmse": round(rmse, 0), "mape": round(mape, 2)
    }
