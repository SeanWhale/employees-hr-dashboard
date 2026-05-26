# File: etl/extract.py
"""
数据提取层 — MySQL dump 文件行级解析

================================================================================
这个文件是做什么的？
================================================================================
把 MySQL 的 .dump 文件（本质是包含 SQL INSERT 语句的纯文本）解析成
Pandas 的 DataFrame（二维表格），供后续的清洗步骤使用。

举个例子，假设 dump 文件里有这样的内容：

    INSERT INTO `employees` VALUES (10001,'1953-09-02','Georgi','Facello','M','1986-06-26');

本文件的 parse_mysql_dump() 函数会把它解析成：

    员工编号  出生日期      名      姓      性别  入职日期
    10001    1953-09-02  Georgi  Facello  M    1986-06-26

================================================================================
依赖说明
================================================================================
- re  (正则表达式): 用来做文本模式匹配，比如把 NULL 替换成 Python 的 None
- ast (抽象语法树): 用来安全地解析 Python 字面量，比如把 "(1, 'hello')" 转成元组
- pandas: 数据分析核心库，提供 DataFrame 这个"超级表格"数据结构
================================================================================
"""
import re
import ast
import pandas as pd


def parse_mysql_dump(file_path: str, columns: list) -> pd.DataFrame:
    """解析 MySQL dump 文件，返回原始 DataFrame（未经类型转换）。

    兼容 test_db 数据集的多行 INSERT 格式（一行一条记录）。

    ------------------------------------------------------------------
    参数说明：
      file_path (str): dump 文件的完整路径，如 "data/employees.dump"
      columns  (list): 数据库表的列名列表，如 ["emp_no", "birth_date", ...]

    返回值：
      pd.DataFrame: 解析出的表格数据，所有列默认为字符串类型（不转换类型）

    ------------------------------------------------------------------
    工作原理（逐行状态机）：
      这个函数逐行读取 dump 文件，用一个"状态标记"in_insert 来追踪当前
      是否处于 INSERT INTO 语句内部：

        文件中读到 "INSERT INTO" → in_insert = True（进入数据区）
        文件中读到 ");" 结尾    → in_insert = False（退出数据区）

      在数据区中，每一行都是一条记录的括号内容，用 ast.literal_eval
      安全地解析成 Python 元组，收集起来，最后全部拼成 DataFrame。
    ------------------------------------------------------------------
    """
    # data 是一个列表（list），用来收集每一条解析出的记录
    # 每条记录是一个元组（tuple），比如 (10001, '1953-09-02', 'Georgi', ...)
    # 所有记录收集完后，一次性构建成 DataFrame
    data = []

    # in_insert 是状态标记（布尔值 bool）：
    #   False = 当前不在 INSERT 语句内部（还在找 INSERT 的开头）
    #   True  = 当前正在 INSERT 语句内部（正在读取数据行）
    in_insert = False

    # ------------------------------------------------------------------
    # 打开文件，逐行读取
    # ------------------------------------------------------------------
    # open(file_path, "r", encoding="utf-8") 以"只读模式"、UTF-8 编码打开文件
    # with ... as f: 是 Python 的"上下文管理器"语法——
    #   无论后面代码是否出错，文件都会被自动关闭，不需要手动 f.close()
    with open(file_path, "r", encoding="utf-8") as f:

        # for line in f: 逐行遍历文件
        # 文件对象可以直接被 for 循环遍历，每次取出一行（包含末尾的换行符）
        for line in f:

            # .strip() 去除行首行尾的空白字符（空格、制表符、换行符等）
            line = line.strip()

            # 如果这一行是空行（去掉空白后什么都不剩），直接跳过
            if not line:
                continue  # continue = 跳过本轮循环，读取下一行

            # ==============================================================
            # 状态切换：检测 INSERT INTO 语句的起始位置
            # ==============================================================
            # line.startswith("INSERT INTO") 检查行是否以 "INSERT INTO" 开头
            # 同时兼容大小写（有些 dump 文件用 INSERT INTO，有些用 insert into）
            if line.startswith("INSERT INTO") or line.startswith("insert into"):
                # 找到了 INSERT 语句的开头，切换到"数据区"模式
                in_insert = True

                # 转换为全大写，方便统一查找关键字位置
                # 因为 SQL 不区分大小写——"VALUES"、"values"、"Values" 都是合法写法
                upper = line.upper()

                # 检查 VALUES 关键字是否和 INSERT 在同一行
                # （有些 dump 文件把 INSERT INTO 和 VALUES 分成两行写）
                if "VALUES" in upper:

                    # .find("VALUES") 返回 "VALUES" 这个子串在字符串中的起始位置（索引）
                    # + 6 是因为 "VALUES" 本身有 6 个字符，跳过它，得到数据部分的起始位置
                    val_idx = upper.find("VALUES") + 6

                    # 截取 VALUES 之后的内容（可能包含括号和数据）
                    # rest 可能是 "(10001,'1953-09-02',...);" 这样的字符串
                    rest = line[val_idx:].strip()

                    # 如果紧接着就是左括号 "("，说明数据直接跟在 VALUES 后面
                    if rest.startswith("("):
                        # 把 line 替换为数据部分，这样下面统一处理数据行的代码就能复用了
                        line = rest
                    else:
                        # 如果 VALUES 后面不是 "("（可能是空行或其他情况），
                        # 就跳过，等下一行——数据从下一行开始
                        continue
                else:
                    # INSERT INTO 和 VALUES 不在同一行，
                    # 说明数据行在后面（从下一行开始），跳过本轮
                    continue

            # ==============================================================
            # 数据区：解析括号内的字段值
            # ==============================================================
            # 只有当 in_insert == True 时才尝试解析数据行
            if in_insert:

                # 数据行以左括号 "(" 开头，例：(10001,'1953-09-02','Georgi',...
                if line.startswith("("):

                    # --- 判断这一行是不是 INSERT 语句的最后一行 ---
                    # 如果行尾有分号 ";"，说明这是最后一条记录（SQL 语句结束的标志）
                    # 例：(499999,'1999-01-01','John','Doe','M','2019-01-01');
                    is_last = line.endswith(";")

                    # --- 清理括号和分号，提取纯数据 ---
                    content = line

                    # 去掉开头的 "("
                    if content.startswith("("):
                        content = content[1:]    # [1:] 表示"从第 2 个字符开始到末尾"

                    # 如果以 ";" 结尾，去掉末尾的 ";"
                    if content.endswith(";"):
                        content = content[:-1]   # [:-1] 表示"从开头到倒数第 2 个字符"

                    # 如果以 ")" 结尾，去掉末尾的 ")"
                    # 这处理的是最后一条记录: ...'2019-01-01');
                    if content.endswith(")"):
                        content = content[:-1]

                    # 如果以 ")," 结尾，去掉末尾的 "),"（两个字符）
                    # 这处理的是中间记录:  ...'1986-06-26'),
                    elif content.endswith("),"):
                        content = content[:-2]   # [:-2] 表示"去掉最后 2 个字符"

                    # --- 安全解析 ---
                    # 现在的 content 是类似这样的纯数据：
                    #   10001,'1953-09-02','Georgi','Facello','M','1986-06-26'
                    #
                    # 步骤 A：把 SQL 的 NULL 替换成 Python 的 None
                    #   re.sub(r"\bNULL\b", "None", content) 的作用：
                    #   - \b 是正则中的"单词边界"，确保只匹配完整的 NULL 单词
                    #   - 不会错误地把 "NOTNULL" 或 "NULLABLE" 中的 NULL 替换掉
                    #   - NULL 在 SQL 中表示"空值/未知"，对应 Python 的 None
                    try:
                        safe = re.sub(r"\bNULL\b", "None", content)

                        # 步骤 B：用 ast.literal_eval 安全解析
                        #   把字符串 "(10001, '1953-09-02', 'Georgi', ...)" 转成 Python 元组
                        #
                        #   为什么用 ast.literal_eval 而不是 eval()？
                        #     eval()   —— 会执行任意 Python 代码，非常危险！
                        #     literal_eval() —— 只解析字面量（数字、字符串、列表、元组等），
                        #                      不执行任何代码，安全得多。
                        #
                        #   我们手动补上括号 f"({safe})"，因为 content 现在没有括号了
                        row = ast.literal_eval(f"({safe})")

                        # 步骤 C：把解析出的元组添加到 data 列表中
                        #   data.append(row) 把这一行数据加到列表末尾
                        data.append(row)

                    except (ValueError, SyntaxError):
                        # 如果解析失败（比如数据格式异常），静默跳过这一行
                        # 不中断整个流程，保证程序的鲁棒性（健壮性）
                        pass

                    # --- 如果这是最后一条记录，退出数据区模式 ---
                    if is_last:
                        in_insert = False

    # =========================================================================
    # 所有行读取完毕，构建 DataFrame
    # =========================================================================

    # 如果 data 列表为空（一个有效记录都没解析到），
    # 就创建一个空的 DataFrame，但保留列名——
    # 这样程序不会崩溃，后续步骤也能正常处理（只是表格为空）
    if not data:
        df = pd.DataFrame(columns=columns)

    else:
        # 用收集到的所有数据行和列名，构建 DataFrame
        # data 是一个包含很多元组的列表，如 [(10001,...), (10002,...), ...]
        # columns 告诉 DataFrame 每列叫什么名字
        df = pd.DataFrame(data, columns=columns)

    # ------------------------------------------------------------------
    # 去重：删除完全重复的行，只保留第一次出现的
    # ------------------------------------------------------------------
    # drop_duplicates() 会比较每一行的所有列，如果某两行完全相同，
    # 只保留第一次出现的那行。这是防止 dump 文件中有重复 INSERT 的兜底措施。
    return df.drop_duplicates()
