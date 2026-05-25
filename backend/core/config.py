# File: backend/core/config.py
# -*- coding: utf-8 -*-
"""项目级常量配置"""
import os
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PQ_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "parquet")

# 👇 新增这一行：前端静态文件目录，供 app.py 挂载 Vue 大屏使用
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

DB_PATH = os.path.join(tempfile.gettempdir(), "hr_dashboard_analytics.duckdb")

# 数据集时间快照锚点（2002年8月），防止计算年龄/工龄时发生"时空穿越"
DATASET_MAX_DATE = "2002-08-01"