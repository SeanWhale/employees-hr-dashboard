# File: backend/services/overview_srv.py
# -*- coding: utf-8 -*-
"""总览看板服务 — 调用 DAO 组装数据，注入 DATASET_MAX_DATE"""

from backend.core.config import DATASET_MAX_DATE

try:
    from dao.hr_dao import get_dept_distribution_data, get_kpi_data, get_office_map_data
except ImportError:
    from backend.dao.hr_dao import get_dept_distribution_data, get_kpi_data, get_office_map_data

COORDS = {
    '北京': [116.40, 39.90], '上海': [121.47, 31.23], '深圳': [114.05, 22.54],
    '广州': [113.26, 23.13], '成都': [104.06, 30.67]
}


def get_kpi():
    df = get_kpi_data()
    row = df.fillna(0).to_dict(orient="records")[0]
    row["as_of_date"] = DATASET_MAX_DATE
    return row


def get_dept_distribution():
    df = get_dept_distribution_data()
    return df.to_dict(orient="records")


def get_office_map():
    df = get_office_map_data()
    result = []
    for _, r in df.iterrows():
        city = r['city']
        coord = COORDS.get(city, [116.40, 39.90])
        result.append({
            "name": city,
            "value": [coord[0], coord[1], int(r['avg_s']), int(r['cnt'])]
        })
    return result
