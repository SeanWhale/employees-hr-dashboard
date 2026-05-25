"""数据提取层 — MySQL dump 文件行级解析"""
import re
import ast
import pandas as pd


def parse_mysql_dump(file_path: str, columns: list) -> pd.DataFrame:
    """解析 MySQL dump 文件，返回原始 DataFrame（未经类型转换）。

    兼容 test_db 数据集的多行 INSERT 格式（一行一条记录）。
    """
    data = []
    in_insert = False

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith("INSERT INTO") or line.startswith("insert into"):
                in_insert = True
                upper = line.upper()
                if "VALUES" in upper:
                    val_idx = upper.find("VALUES") + 6
                    rest = line[val_idx:].strip()
                    if rest.startswith("("):
                        line = rest
                    else:
                        continue
                else:
                    continue

            if in_insert:
                if line.startswith("("):
                    is_last = line.endswith(";")

                    content = line
                    if content.startswith("("):
                        content = content[1:]
                    if content.endswith(";"):
                        content = content[:-1]
                    if content.endswith(")"):
                        content = content[:-1]
                    elif content.endswith("),"):
                        content = content[:-2]

                    try:
                        safe = re.sub(r"\bNULL\b", "None", content)
                        row = ast.literal_eval(f"({safe})")
                        data.append(row)
                    except (ValueError, SyntaxError):
                        pass

                    if is_last:
                        in_insert = False

    if not data:
        df = pd.DataFrame(columns=columns)
    else:
        df = pd.DataFrame(data, columns=columns)

    return df.drop_duplicates()
