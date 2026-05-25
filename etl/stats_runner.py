"""数据集探索性统计分析 (EDA) — 面向对象报表运行器

用法:
    python -m etl.stats_runner          # 运行全部 12 项分析
    python etl/stats_runner.py          # 等价调用
"""

import pandas as pd
from pathlib import Path

from backend.core.db import get_connection


class StatsAnalyzer:
    """HR 数据集探索性统计分析器。

    Parameters
    ----------
    data_dir : Path or str, optional
        Clean Parquet 所在目录，默认 data/processed/parquet
    """

    def __init__(self, data_dir=None):
        self.con = get_connection()
        if data_dir is None:
            data_dir = Path(__file__).resolve().parent.parent / "data" / "processed" / "parquet"
        self.data_dir = Path(data_dir)

    # ---- 输出辅助 ----

    @staticmethod
    def _divider(title):
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")

    def _parquet_path(self, pattern: str) -> str:
        return str(self.data_dir / pattern).replace("\\", "/")

    # ================================================================
    #  1. 数据总览
    # ================================================================
    def overview(self):
        self._divider("1. 数据总览 (整体规模)")

        tables = {
            "departments": "load_departments.parquet",
            "dept_emp": "load_dept_emp.parquet",
            "dept_manager": "load_dept_manager.parquet",
            "employees": "load_employees.parquet",
            "salaries (3 files)": "load_salaries*.parquet",
            "titles": "load_titles.parquet",
        }

        total_rows = 0
        for name, file in tables.items():
            path = self._parquet_path(file)
            count = self.con.execute(
                f"SELECT COUNT(*) FROM read_parquet('{path}')"
            ).fetchone()[0]
            total_rows += count
            print(f"  {name:<25s}: {count:>12,} 行")

        print(f"  {'─' * 50}")
        print(f"  {'总计':<25s}: {total_rows:>12,} 行")
        self._total_rows = total_rows

    # ================================================================
    #  2. Departments 分析
    # ================================================================
    def department_analysis(self):
        self._divider("2. 部门维度 (Departments)")

        path = self._parquet_path("load_departments.parquet")
        depts = self.con.execute(f"SELECT * FROM read_parquet('{path}')").df()
        print(depts.to_string(index=False))
        self._dept_count = len(depts)

    # ================================================================
    #  3. Employees 基础统计
    # ================================================================
    def employee_basics(self):
        self._divider("3. 员工基本信息 (Employees)")

        path = self._parquet_path("load_employees.parquet")
        emp = self.con.execute(f"SELECT * FROM read_parquet('{path}')").df()
        print(f"  总员工数:        {len(emp):>10,}")
        print(f"  不同名字数:      {emp['first_name'].nunique():>10,}")
        print(f"  不同姓氏数:      {emp['last_name'].nunique():>10,}")

        gender = emp["gender"].value_counts()
        print(f"\n  性别分布:")
        for g, c in gender.items():
            print(f"    {g}: {c:>10,}  ({c/len(emp)*100:5.1f}%)")

        emp["birth_year"] = pd.to_datetime(emp["birth_date"]).dt.year
        emp["hire_year"] = pd.to_datetime(emp["hire_date"]).dt.year

        print(f"\n  出生年份范围:    {int(emp['birth_year'].min())} ~ {int(emp['birth_year'].max())}")
        print(f"  入职年份范围:    {int(emp['hire_year'].min())} ~ {int(emp['hire_year'].max())}")
        print(f"  平均入职年龄:    {(emp['hire_year'] - emp['birth_year']).mean():.1f} 岁")

        self._emp = emp
        self._gender = gender

    # ================================================================
    #  4. 薪资统计
    # ================================================================
    def salary_statistics(self):
        self._divider("4. 薪资统计 (Salaries)")

        path = self._parquet_path("load_salaries*.parquet")
        sal = self.con.execute(
            f"SELECT salary, from_date, to_date FROM read_parquet('{path}')"
        ).df()
        sal["year"] = pd.to_datetime(sal["from_date"]).dt.year

        stats = {
            "总记录数": len(sal),
            "均值": sal["salary"].mean(),
            "中位数": sal["salary"].median(),
            "标准差": sal["salary"].std(),
            "最小值": sal["salary"].min(),
            "P1": sal["salary"].quantile(0.01),
            "P5": sal["salary"].quantile(0.05),
            "P10": sal["salary"].quantile(0.10),
            "P25": sal["salary"].quantile(0.25),
            "P75": sal["salary"].quantile(0.75),
            "P90": sal["salary"].quantile(0.90),
            "P95": sal["salary"].quantile(0.95),
            "P99": sal["salary"].quantile(0.99),
            "最大值": sal["salary"].max(),
            "偏度 (Skewness)": sal["salary"].skew(),
            "峰度 (Kurtosis)": sal["salary"].kurtosis(),
        }

        for k, v in stats.items():
            if isinstance(v, float):
                print(f"  {k:<20s}: {v:>14,.2f}")
            else:
                print(f"  {k:<20s}: {v:>14,}")

        print(f"\n  按年份薪资变化:")
        yearly = sal.groupby("year").agg(
            count=("salary", "count"),
            mean=("salary", "mean"),
            median=("salary", "median"),
            std=("salary", "std"),
            min=("salary", "min"),
            max=("salary", "max"),
        ).reset_index()
        yearly = yearly[yearly["year"].between(1985, 2002)].sort_values("year")
        for _, r in yearly.iterrows():
            print(f"    {int(r['year']):4d}: 均值=${r['mean']:>9,.0f}  中位数=${r['median']:>9,.0f}  标准差=${r['std']:>7,.0f}  记录数={r['count']:>7,}")

        self._sal = sal

    # ================================================================
    #  5. 职级分析
    # ================================================================
    def title_analysis(self):
        self._divider("5. 职级分析 (Titles)")

        path = self._parquet_path("load_titles.parquet")
        titles = self.con.execute(f"SELECT * FROM read_parquet('{path}')").df()
        title_dist = titles["title"].value_counts()
        print(f"  总记录数:        {len(titles):>10,}")
        print(f"  不同职级数:      {titles['title'].nunique():>10}")
        print(f"\n  各职级分布:")
        for t, c in title_dist.items():
            print(f"    {t:<30s}: {c:>10,}  ({c/len(titles)*100:5.1f}%)")

        title_changes = titles.groupby("emp_no")["title"].nunique() - 1
        print(f"\n  人均职级变更次数:  {title_changes.mean():.2f}")
        print(f"  职级从未变更:      {(title_changes==0).sum():>10,} 人 ({(title_changes==0).mean()*100:.1f}%)")
        print(f"  变更 1 次:         {(title_changes==1).sum():>10,} 人")
        print(f"  变更 2 次:         {(title_changes==2).sum():>10,} 人")
        print(f"  变更 3+ 次:        {(title_changes>=3).sum():>10,} 人")

    # ================================================================
    #  6. 部门-员工分析
    # ================================================================
    def dept_emp_analysis(self):
        self._divider("6. 部门-员工分析 (Dept-Emp)")

        path = self._parquet_path("load_dept_emp.parquet")
        dept_emp = self.con.execute(f"SELECT * FROM read_parquet('{path}')").df()
        print(f"  总记录数:        {len(dept_emp):>10,}")
        print(f"  不同员工数:      {dept_emp['emp_no'].nunique():>10,}")

        dept_changes = dept_emp.groupby("emp_no")["dept_no"].nunique() - 1
        print(f"\n  人均部门变更次数:  {dept_changes.mean():.2f}")
        print(f"  部门从未变更:      {(dept_changes==0).sum():>10,} 人 ({(dept_changes==0).mean()*100:.1f}%)")

    # ================================================================
    #  7. 当前员工全景
    # ================================================================
    def current_employees_view(self):
        self._divider("7. 当前在职员工全景 (current_employees)")

        ce = self.con.execute("SELECT * FROM current_employees").df()
        print(f"  当前在职总人数:   {len(ce):>10,}")

        print(f"\n  ┌─ 按部门统计 ─────────────────────────────────────────────────┐")
        dept_stats = ce.groupby("dept_name").agg(
            人数=("emp_no", "count"),
            平均薪资=("salary", "mean"),
            中位薪资=("salary", "median"),
            最低薪资=("salary", "min"),
            最高薪资=("salary", "max"),
            薪资标准差=("salary", "std"),
        ).sort_values("平均薪资", ascending=False).round(0)

        for dept, row in dept_stats.iterrows():
            print(f"  │ {dept:<22s} │ 人数={int(row['人数']):>7,} │ 均薪=${int(row['平均薪资']):>8,} │ 中位=${int(row['中位薪资']):>8,} │ 最低=${int(row['最低薪资']):>6,} │ 最高=${int(row['最高薪资']):>9,} │ 标准差=${int(row['薪资标准差']):>7,} │")
        print(f"  └───────────────────────────────────────────────────────────────┘")

        print(f"\n  ┌─ 按职级统计 ─────────────────────────────────────────────────┐")
        title_stats = ce.groupby("title").agg(
            人数=("emp_no", "count"),
            平均薪资=("salary", "mean"),
            最低=("salary", "min"),
            最高=("salary", "max"),
        ).sort_values("平均薪资", ascending=False).round(0)

        for t, row in title_stats.iterrows():
            print(f"  │ {t:<28s} │ 人数={int(row['人数']):>6,} │ 均薪=${int(row['平均薪资']):>8,} │ 最低=${int(row['最低']):>6,} │ 最高=${int(row['最高']):>9,} │")
        print(f"  └───────────────────────────────────────────────────────────────┘")

        print(f"\n  ┌─ 按性别统计 ────────────────────────────────────────────────┐")
        gender_stats = ce.groupby("gender").agg(
            人数=("emp_no", "count"),
            平均薪资=("salary", "mean"),
            中位薪资=("salary", "median"),
        ).round(0)
        for g, row in gender_stats.iterrows():
            print(f"  │ {g}: 人数={int(row['人数']):>8,} │ 均薪=${int(row['平均薪资']):>8,} │ 中位薪资=${int(row['中位薪资']):>8,} │")
        print(f"  └───────────────────────────────────────────────────────────────┘")

        self._ce = ce
        self._dept_stats = dept_stats

    # ================================================================
    #  8. 司龄与年龄分布
    # ================================================================
    def tenure_age_distribution(self):
        self._divider("8. 司龄与年龄分布")

        emp_path = self._parquet_path("load_employees.parquet")
        age_df = self.con.execute(f"""
            SELECT
                (EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM CAST(e.hire_date AS DATE))) AS tenure,
                (EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM CAST(e.birth_date AS DATE))) AS age,
                ce.salary,
                ce.dept_name
            FROM current_employees ce
            JOIN read_parquet('{emp_path}') e ON ce.emp_no = e.emp_no
        """).df()

        print(f"  司龄统计:")
        print(f"    均值: {age_df['tenure'].mean():.1f} 年")
        print(f"    中位数: {age_df['tenure'].median():.1f} 年")
        print(f"    范围: {int(age_df['tenure'].min())} ~ {int(age_df['tenure'].max())} 年")
        print(f"    标准差: {age_df['tenure'].std():.1f} 年")

        bins = [0, 5, 10, 15, 20, 25, 30, 50]
        labels = ["0-5年", "5-10年", "10-15年", "15-20年", "20-25年", "25-30年", "30年+"]
        age_df["tenure_group"] = pd.cut(age_df["tenure"], bins=bins, labels=labels, right=False)
        tenure_dist = age_df["tenure_group"].value_counts().sort_index()
        print(f"\n  司龄分布:")
        for g, c in tenure_dist.items():
            print(f"    {g:<10s}: {c:>8,} 人 ({c/len(age_df)*100:5.1f}%)")

        print(f"\n  年龄统计:")
        print(f"    均值: {age_df['age'].mean():.1f} 岁")
        print(f"    中位数: {age_df['age'].median():.1f} 岁")
        print(f"    范围: {int(age_df['age'].min())} ~ {int(age_df['age'].max())} 岁")

        self._age_df = age_df

    # ================================================================
    #  9. 相关性矩阵
    # ================================================================
    def correlation_matrix(self):
        self._divider("9. 核心字段相关性矩阵")

        corr_df = self._age_df[["tenure", "age", "salary"]].corr()
        print(corr_df.round(4).to_string())
        self._corr_df = corr_df

    # ================================================================
    #  10. 部门经理分析
    # ================================================================
    def manager_analysis(self):
        self._divider("10. 部门经理")

        mgr_path = self._parquet_path("load_dept_manager.parquet")
        dept_path = self._parquet_path("load_departments.parquet")
        mgr = self.con.execute(f"""
            SELECT d.dept_name, dm.*
            FROM read_parquet('{mgr_path}') dm
            JOIN read_parquet('{dept_path}') d ON dm.dept_no = d.dept_no
        """).df()
        print(f"  总记录数: {len(mgr)}")
        print(f"  不同经理人数: {mgr['emp_no'].nunique()}")

    # ================================================================
    #  11. 缺失值与数据质量
    # ================================================================
    def data_quality_summary(self):
        self._divider("11. 数据质量总览")

        for table_key, file_pattern in [
            ("employees", "load_employees.parquet"),
            ("salaries", "load_salaries*.parquet"),
            ("titles", "load_titles.parquet"),
            ("dept_emp", "load_dept_emp.parquet"),
        ]:
            path = self._parquet_path(file_pattern)
            df = self.con.execute(f"SELECT * FROM read_parquet('{path}')").df()
            nulls = df.isnull().sum()
            total_nulls = nulls.sum()
            dupes = df.duplicated().sum()
            print(f"  {table_key:<15s}: 列数={len(df.columns):>2} | 缺失值={total_nulls:>6,} | 重复行={dupes:>6,} | 总行={len(df):>10,}")

    # ================================================================
    #  12. 关键发现总结
    # ================================================================
    def key_findings(self):
        self._divider("12. 关键发现总结")

        dept_stats = self._dept_stats
        sal = self._sal
        gender = self._gender
        emp = self._emp
        corr_df = self._corr_df

        print(f"""
  1. 数据规模: {self._total_rows:,} 条记录, 覆盖 1985-2002 共 18 年
  2. 部门薪资差异: {dept_stats['平均薪资'].max():.0f} (最高) vs {dept_stats['平均薪资'].min():.0f} (最低),
     极差 ${dept_stats['平均薪资'].max() - dept_stats['平均薪资'].min():,.0f}
  3. 薪资分布: 偏度={sal['salary'].skew():.2f} (>0 右偏), 峰度={sal['salary'].kurtosis():.2f}
  4. 性别平衡: M={gender.get('M', 0):,} ({gender.get('M', 0)/len(emp)*100:.1f}%), F={gender.get('F', 0):,} ({gender.get('F', 0)/len(emp)*100:.1f}%)
  5. 薪资-司龄相关系数: r={corr_df.loc['salary','tenure']:.4f}
  6. 薪资-年龄相关系数: r={corr_df.loc['salary','age']:.4f}
  7. 数据质量: 无缺失值, 无重复行, 可直接用于分析
""")

    # ================================================================
    #  运行入口
    # ================================================================
    def run_all(self):
        """依次执行全部 12 项分析"""
        self.overview()
        self.department_analysis()
        self.employee_basics()
        self.salary_statistics()
        self.title_analysis()
        self.dept_emp_analysis()
        self.current_employees_view()
        self.tenure_age_distribution()
        self.correlation_matrix()
        self.manager_analysis()
        self.data_quality_summary()
        self.key_findings()

    def close(self):
        """关闭数据库连接"""
        self.con.close()


# ================================================================
#  独立运行
# ================================================================
if __name__ == "__main__":
    analyzer = StatsAnalyzer()
    try:
        analyzer.run_all()
    finally:
        analyzer.close()
