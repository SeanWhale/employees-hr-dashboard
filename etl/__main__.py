# File: etl/__main__.py
"""
ETL 清洗任务启动入口 — 调用 extract → transform → load 并生成质量报告

================================================================================
什么是 ETL？
================================================================================
ETL 是三个英文单词的缩写：
    - E = Extract  （提取）：从原始数据源（这里是 MySQL 的 .dump 导出文件）中读取数据
    - T = Transform（转换/清洗）：把"脏数据"变成"干净数据"——修正错误、统一格式、去除重复等
    - L = Load     （加载）：将处理好的数据保存到新的文件（这里是 Parquet 格式）

你可以把 ETL 想象成一个工厂流水线：
    原料（dump 文件）→ 清洗加工（本文件做的事情）→ 成品（Parquet 文件）

================================================================================
什么是 Parquet 格式？
================================================================================
Parquet（发音：帕凯）是一种列式存储的数据文件格式，和 CSV/Excel 类似都用于存表格数据。
它的优势是：读取速度快、占用空间小、能被 Pandas/大数据工具直接读取。
类比：如果说 CSV 是 .txt 纯文本，Parquet 就像 .zip 压缩包——更高效。

================================================================================
用法: python -m etl
================================================================================
"""

# ================================================================================
# 导入依赖模块
# ================================================================================
# Python 的 import 就像"借用别人的工具包"——
# 你不需要自己造轮子，直接拿别人写好的功能来用。

# from .config import ...
#   从同目录下的 config.py 文件中导入以下"常量"（不会变的值）和工具函数：
#   - DUMP_DIR:      原始 dump 文件所在的文件夹路径
#   - RAW_DIR:       存放"原始快照"的文件夹路径（未清洗，仅转换格式）
#   - CLEAN_DIR:     存放"清洗完成"数据的文件夹路径
#   - REPORT_DIR:    存放"质量报告"的文件夹路径
#   - SCHEMAS:       一个字典，记录了每张表有哪些列（字段）
#   - DUMP_FILES:    需要处理的所有 dump 文件名列表
#   - filename_to_tablename: 一个工具函数，把文件名转成对应的数据库表名
from .config import DUMP_DIR, RAW_DIR, CLEAN_DIR, REPORT_DIR, SCHEMAS, DUMP_FILES, filename_to_tablename

# from .extract import parse_mysql_dump
#   从 extract.py 中导入 parse_mysql_dump 函数——
#   它的工作是：读取 MySQL 的 dump 文本文件，解析成 Pandas 的 DataFrame（二维表格）
from .extract import parse_mysql_dump

# from .transform import (...)
#   从 transform.py 中导入多个"数据清洗"函数，每个函数做一种特定的清洗工作：
#   - coerce_columns:            把字符串列转成正确的数据类型（如 "100" → 数字 100）
#   - clean_employees:           标准化员工表中的数据（如姓名格式、日期格式）
#   - set_default_to_date:       给"结束日期"为空的行填上默认值（表示"至今"）
#   - merge_adjacent_same_dept:  合并相邻时间段内同一部门的重复记录
#   - fix_overlaps_by_shifting:  修复时间区间重叠的问题（让时间段首尾相连而不是互相覆盖）
#   - apply_quality_rules:       根据质量规则过滤掉不合规的数据行
#   - filter_by_employees:       过滤掉"孤儿数据"——引用了不存在的员工的记录
from .transform import (
    coerce_columns, clean_employees, set_default_to_date,
    merge_adjacent_same_dept, fix_overlaps_by_shifting,
    apply_quality_rules, filter_by_employees
)

# from .load import (...)
#   从 load.py 中导入三个"保存"函数：
#   - save_raw_parquet:    保存原始数据为 Parquet 格式
#   - save_clean_parquet:  保存清洗后的数据为 Parquet 格式
#   - save_quality_report: 保存数据质量报告为 JSON 格式
from .load import save_raw_parquet, save_clean_parquet, save_quality_report


def run_etl():
    """
    主 ETL 流水线（Pipeline）
    ============================
    这个函数是整个 ETL 流程的"总指挥"——
    它会遍历每一个 dump 文件，对每个文件依次执行：
        Extract（提取）→ Transform（清洗）→ Load（保存）

    同时还会生成一份"数据质量报告"，记录：
      - 每个表进来了多少行、出去了多少行
      - 有多少行因为质量问题被丢弃
      - 有多少时间重叠被修复
      - 等等...
    """

    # =========================================================================
    # 第零步：确保输出目录存在
    # =========================================================================
    # mkdir(parents=True, exist_ok=True) 的作用：
    #   - parents=True: 如果父目录也不存在，就一并创建（类似 mkdir -p）
    #   - exist_ok=True: 如果目录已经存在，不要报错（没这个参数的话重复创建会出错）
    # 简单说就是："不管这些文件夹在不在，执行完这一行后它们一定存在"
    RAW_DIR.mkdir(parents=True, exist_ok=True)      # 存放原始 Parquet 快照的文件夹
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)    # 存放清洗后 Parquet 的文件夹
    REPORT_DIR.mkdir(parents=True, exist_ok=True)   # 存放质量报告的文件夹

    # =========================================================================
    # 初始化"状态变量"——在循环开始前先准备好容器
    # =========================================================================
    # employees_df = None
    #   员工表的数据会存到这里，后面用来检查"孤儿数据"——
    #   比如工资表里有一条记录说"员工编号 99999 的工资是 5000"，
    #   但如果 employees 表中根本没有编号 99999 的员工，这条工资记录就是"孤儿"。
    #   初始值是 None（空），因为此时还没读到 employees 表。
    employees_df = None

    # quality_report = {}
    #   一个空字典（dict），用来收集每个文件的清洗统计指标。
    #   字典是 Python 里非常常用的数据结构，格式是 {键: 值}，
    #   比如 {"employees": {"rows_in": 300000, "rows_out": 299500}, ...}
    quality_report = {}

    # total_stats = {}
    #   另一个空字典，用来汇总每个数据库表的最终行数。
    #   格式如 {"employees": 299500, "salaries": 2844047, ...}
    total_stats = {}

    # =========================================================================
    # 主循环：逐个处理每个 dump 文件
    # =========================================================================
    # DUMP_FILES 是一个列表（list），比如 ["employees.dump", "salaries.dump", ...]
    # for filename in DUMP_FILES: 的意思就是"挨个取出列表中的文件名，每次循环处理一个"
    for filename in DUMP_FILES:

        # --- 拼接文件完整路径，并检查文件是否存在 ---
        # DUMP_DIR / filename 使用了 Python 的 pathlib 语法，
        # 效果等同于 DUMP_DIR + "/" + filename（但更安全，跨平台都能用）
        file_path = DUMP_DIR / filename

        # 如果文件不存在（比如你忘了把某个 dump 文件放到目录里），
        # 就打印一条 [SKIP] 信息，然后用 continue 跳过后面的代码，直接处理下一个文件
        if not file_path.exists():
            print(f"[SKIP] File not found: {file_path}")
            continue  # continue = "跳过本轮循环的剩余部分，开始下一轮"

        # --- 把文件名转成数据库表名 ---
        # 比如 "employees.dump" → "employees"
        #       "salaries.dump" → "salaries"
        table_name = filename_to_tablename(filename)

        # --- 打印分隔线和当前处理进度 ---
        # '='*60 是 Python 的字符串乘法：把 "=" 重复 60 次，形成一条分隔线
        print(f"\n{'='*60}")
        print(f"Processing: {filename} -> table '{table_name}'")

        # =====================================================================
        # 第 1 步：Extract（提取）—— 把 dump 文本文件解析成表格数据
        # =====================================================================
        # parse_mysql_dump() 读取 MySQL dump 文件（.dump 本质是 SQL INSERT 语句的文本），
        # 解析后返回一个 DataFrame（可以理解为 Excel 里的一个 Sheet / 一张二维表）
        #
        # SCHEMAS[table_name] 告诉解析器"这张表应该有哪些列"，
        # 因为 dump 文件里的 INSERT 语句可能不包含列名，需要用 schema 来对齐。
        #
        # 什么是 DataFrame？
        #   它是 Pandas 库的核心数据结构，你可以把它理解为一个"超级 Excel 表格"：
        #     - 有行（row）和列（column）
        #     - 每列有一个名字（列名）
        #     - 每行有一个索引（行号，从 0 开始）
        #     - 可以对整列做数学运算（如求平均值、求和），非常强大
        df = parse_mysql_dump(str(file_path), SCHEMAS[table_name])
        print(f"  Parsed: {len(df):,} rows")
        # len(df) 返回 DataFrame 的行数
        # :, 是 Python 的格式化语法——在数字中每三位加一个逗号，如 300024 → "300,024"


        # =====================================================================
        # 第 2 步：保存原始 Parquet 快照
        # =====================================================================
        # 为什么要保存一份"原始快照"？
        #   - 如果后面的清洗步骤出了问题，你不需要重新解析 dump 文件
        #   - 可以对比清洗前后的数据，看看清洗步骤到底改了什么
        #
        # df.copy() 创建一个完整副本，确保后续修改 df 时不会影响 raw_df
        raw_df = df.copy()

        # 把文件名从 "xxx.dump" 改成 "xxx.parquet"，作为输出文件名
        raw_name = filename.replace(".dump", ".parquet")

        # 保存原始数据到 raw/ 目录下
        save_raw_parquet(raw_df, RAW_DIR / raw_name)
        print(f"  Raw saved: {RAW_DIR / raw_name} ({len(raw_df):,} rows)")


        # =====================================================================
        # 第 3 步：Transform（转换）—— 类型转换
        # =====================================================================
        # dump 文件解析出来所有列默认都是"字符串"（文本）类型，
        # 但实际数据中"工资"应该是数字、"日期"应该是日期类型……
        # coerce_columns() 会根据 table_name 对应的规则，把每列转成正确的数据类型。
        # 比如 "50000"（字符串） → 50000（整数）
        df = coerce_columns(df, table_name)


        # =====================================================================
        # 第 4 步：Transform（转换）—— 质量规则过滤
        # =====================================================================
        # apply_quality_rules() 检查数据是否符合质量规则，比如：
        #   - 必填列是否有空值？（如 emp_no 员工编号不能为空）
        #   - 数值是否在合理范围内？（如工资不能为负数）
        #   - 日期格式是否正确？
        #
        # 返回值有四个：
        #   - df:              过滤后的"干净"数据（不合规的行已被删除）
        #   - missing_counts:  一个字典，记录每列有多少行是空值
        #   - invalid_counts:  一个字典，记录每列有多少行值不合法
        #   - dropped:         总共被删除的行数
        #
        # 注意：这一步必须在类型转换（第 3 步）之后执行！
        #   因为如果还是字符串格式，"100" 和 100 的比较会出问题。
        df, missing_counts, invalid_counts, dropped = apply_quality_rules(df, table_name)

        # 如果有行被删除，打印一条信息告知用户
        if dropped:
            print(f"  Quality: dropped {dropped:,} rows (missing: {missing_counts}, invalid: {invalid_counts})")


        # =====================================================================
        # 第 5 步：Transform（转换）—— 属性标准化 / 去重
        # =====================================================================
        # --- 5a. 如果是员工表（employees），做专门的数据清洗 ---
        # clean_employees() 做的事情可能包括：
        #   - 统一姓名格式（去除前后空格、首字母大写等）
        #   - 修正不合法的日期（如出生日期在未来）
        #   - 标准化性别字段（"M"/"F" 统一）
        if table_name == "employees":
            df = clean_employees(df)
            # 把清洗后的员工表存到 employees_df 中——
            # 后面过滤"孤儿数据"时会用到它（检查其他表中的 emp_no 是否在员工表中存在）
            employees_df = df

        # --- 5b. 如果是部门-员工关联表（dept_emp），去除完全重复的行 ---
        # drop_duplicates() 删除完全重复的行（指定的四列都一模一样才算重复）
        # 比如同一个人在同一部门、同一时间段被记录了两次，就只保留一条
        if table_name == "dept_emp":
            df = df.drop_duplicates(subset=["emp_no", "dept_no", "from_date", "to_date"])


        # =====================================================================
        # 第 6 步：Transform（转换）—— 时态清洗（Temporal Cleaning）
        # =====================================================================
        # 时态数据：带有时间属性的数据（如"从哪一天开始、到哪一天结束"）
        # 这里处理三种常见的时态问题：

        # --- 6a. 去除"零时长幽灵记录" ---
        # 幽灵记录（Phantom Record）：from_date == to_date，开始和结束是同一天
        # 这种记录在现实中是没有意义的（一个持续 0 天的职位/工资？不可能）
        # 只对 dept_emp（部门分配）、salaries（工资）、titles（职称）这三张表做检查
        zero_dropped = 0  # 初始化计数器：记录被删除了多少行
        if table_name in {"dept_emp", "salaries", "titles"}:
            before = len(df)                                # 删除前的行数
            df = df[df["from_date"] != df["to_date"]]      # 只保留 from_date ≠ to_date 的行
            zero_dropped = before - len(df)                 # 计算被删了多少行
            if zero_dropped:
                print(f"  Temporal: dropped {zero_dropped:,} zero-duration phantom records")

        # --- 6b. 填充默认的"结束日期" ---
        # 有些记录的 to_date 可能是空的，或者是一个特殊值（如 "9999-01-01" 表示"至今"）
        # set_default_to_date() 会统一处理这些情况
        df = set_default_to_date(df)

        # --- 6c. 合并相邻的同部门记录 ---
        # 场景：员工 A 在 1998-01-01 ~ 1998-06-30 在研发部 (Development)，
        #      紧接着 1998-07-01 ~ 1998-12-31 也在研发部（中间没有换部门）
        #      这种情况可以合并成 1998-01-01 ~ 1998-12-31 一条记录
        # merge_adjacent_same_dept() 就是做这个合并的
        merges = 0  # 初始化合并计数器
        if table_name == "dept_emp":
            df, merges = merge_adjacent_same_dept(df)
            if merges:
                print(f"  Temporal: merged {merges:,} adjacent department periods")

        # --- 6d. 修复时间区间重叠 ---
        # 场景：员工 A 有两条职称记录：
        #       1996-01-01 ~ 1996-12-31: 工程师 (Engineer)
        #       1996-06-01 ~ 1999-06-30: 高级工程师 (Senior Engineer)
        #      有 6 个月是重叠的！这在逻辑上不合理（可能由于数据录入错误导致）
        #      有 6 个月是重叠的！这在逻辑上不合理（一个人不能同时有两个职称）
        # fix_overlaps_by_shifting() 通过调整 from_date 来消除重叠
        overlaps_fixed = 0  # 初始化修复计数器
        if table_name in {"dept_emp", "titles", "salaries"}:
            df, overlaps_fixed = fix_overlaps_by_shifting(df)
            if overlaps_fixed:
                print(f"  Temporal: fixed {overlaps_fixed:,} overlapping intervals")


        # =====================================================================
        # 第 7 步：过滤孤儿数据（Orphan Data）
        # =====================================================================
        # 什么是孤儿数据？
        #   比如 salaries 表里有一条"员工编号 99999 的工资记录"，
        #   但 employees 表中根本没有编号 99999 的员工——
        #   这条工资记录就变成了"孤儿"（没有"父母"的数据）。
        #
        # 孤儿数据通常是数据不完整导致的，留着它们会在做关联查询时出现问题。
        # filter_by_employees() 会根据 employees_df 中的员工编号，
        # 把当前表中引用了不存在员工的记录删掉。
        #
        # 注意：这里只检查"有外键关联到 employees 表"的子表
        orphan_drop = 0
        if table_name in {"salaries", "titles", "dept_emp", "dept_manager"}:
            df, orphan_drop = filter_by_employees(df, employees_df)
            if orphan_drop:
                print(f"  Orphans: removed {orphan_drop:,} records referencing non-existent employees")


        # =====================================================================
        # 第 8 步：Load（加载）—— 把清洗干净的数据保存为 Parquet 文件
        # =====================================================================
        clean_name = filename.replace(".dump", ".parquet")
        save_clean_parquet(df, CLEAN_DIR / clean_name)
        print(f"  Clean saved: {CLEAN_DIR / clean_name} ({len(df):,} rows)")


        # =====================================================================
        # 第 9 步：记录本文件的清洗指标（供最终质量报告使用）
        # =====================================================================
        # report_key 是报告中的键名，比如 "employees"、"salaries"
        report_key = filename.replace(".dump", "")

        # 构建一个字典，记录这个文件的各种统计数据
        # quality_report 的最终结构会是：
        # {
        #     "employees": {
        #         "rows_in": 300024,         # 进来了多少行
        #         "rows_out": 299500,        # 出去了多少行（清洗后的）
        #         "dropped": 524,            # 因质量问题被丢弃的行数
        #         "zero_duration_dropped": 0,# 零时长记录被丢弃的行数
        #         "missing": {"birth_date": 12, ...},  # 各列空值统计
        #         "invalid": {"gender": 3, ...},       # 各列非法值统计
        #         "orphan_emp_no": 0,        # 孤儿数据行数
        #         "merged_adjacent_dept": 0, # 合并的相邻部门记录数
        #         "overlap_fixed": 0,        # 修复的时间重叠数
        #     },
        #     ...（其他表同理）
        # }
        quality_report[report_key] = {
            "rows_in": int(len(raw_df)),                            # 原始行数
            "rows_out": int(len(df)),                               # 最终行数
            "dropped": int(dropped),                                # 质量过滤丢弃
            "zero_duration_dropped": int(zero_dropped),             # 零时长丢弃
            "missing": {k: int(v) for k, v in missing_counts.items()},   # 空值统计
            "invalid": {k: int(v) for k, v in invalid_counts.items()},   # 非法值统计
            "orphan_emp_no": int(orphan_drop),                      # 孤儿数据丢弃
            "merged_adjacent_dept": int(merges),                    # 相邻部门合并
            "overlap_fixed": int(overlaps_fixed),                   # 时间重叠修复
        }

        # total_stats 汇总每个表的最终行数
        # .get(table_name, 0) 的意思是：如果这个 key 已经存在就取它的值，否则返回默认值 0
        total_stats[table_name] = total_stats.get(table_name, 0) + int(len(df))


    # =========================================================================
    # 循环结束！所有文件都处理完毕
    # =========================================================================

    # --- 生成数据质量报告 ---
    # 将 quality_report 这个字典保存为 JSON 文件
    # JSON（JavaScript Object Notation）是一种通用的数据交换格式，人类可读、机器易解析
    report_path = REPORT_DIR / "data_quality_report.json"
    save_quality_report(quality_report, report_path)

    # --- 在终端打印最终汇总 ---
    print(f"\n{'='*60}")
    print("ETL COMPLETE -- Summary")            # ETL 完成！下面是汇总信息
    print(f"{'='*60}")

    # 遍历 total_stats，打印每张表的最终行数
    # {t:<18} 表示：变量 t 左对齐，占 18 个字符宽度（让输出整齐对齐）
    # {n:>10,} 表示：变量 n 右对齐，占 10 个字符宽度，数字加千分位逗号
    for t, n in total_stats.items():
        print(f"  {t:<18} {n:>10,} rows")

    # 打印各个输出目录的位置，方便用户找到生成的文件
    print(f"\n  Raw output:     {RAW_DIR}")       # 原始快照在这里
    print(f"  Clean output:   {CLEAN_DIR}")       # 清洗结果在这里
    print(f"  Quality report: {report_path}")     # 质量报告在这里


# ================================================================================
# Python 程序的"入口"
# ================================================================================
# if __name__ == "__main__": 是 Python 的一个特殊约定：
#
#   当你直接运行这个文件时（如命令行输入 `python -m etl`），
#   Python 会把 __name__ 设为 "__main__"，于是 run_etl() 被执行。
#
#   但当这个文件被其他文件 import（导入）时，
#   __name__ 会是模块名（这里是 "etl.__main__"），run_etl() 就不会自动执行。
#
#   这个机制允许同一个文件既能当脚本独立运行，也能被当成库来导入——
#   是一个很好的解耦设计。
if __name__ == "__main__":
    run_etl()
