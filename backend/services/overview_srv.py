# File: backend/services/overview_srv.py
# -*- coding: utf-8 -*-
"""总览看板服务 — 调用 DAO 组装数据，注入 DATASET_MAX_DATE"""

from backend.core.config import DATASET_MAX_DATE

try:
    from dao.hr_dao import get_dept_distribution_data, get_kpi_data
except ImportError:
    from backend.dao.hr_dao import get_dept_distribution_data, get_kpi_data


def get_kpi():
    df = get_kpi_data()
    row = df.fillna(0).to_dict(orient="records")[0]
    row["as_of_date"] = DATASET_MAX_DATE
    return row


def get_dept_distribution():
    df = get_dept_distribution_data()
    return df.to_dict(orient="records")
