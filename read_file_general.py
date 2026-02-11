# view_data.py
import pandas as pd
import json
import sys
import os
from pathlib import Path

TRUNCATE_LEN = 20

def truncate(value, length=TRUNCATE_LEN):
    """长数据截断显示"""
    if isinstance(value, str) and len(value) > length:
        return value[:length] + "..."
    return value

def view_csv(file_path, n=5):
    df = pd.read_csv(file_path)
    print(f"CSV 文件: {file_path}，显示前 {n} 条记录，共 {len(df)} 条")
    for i, row in df.head(n).iterrows():
        print(f"\n行 {i}:")
        for col in df.columns:
            print(f"  {col}: {truncate(row[col])}")

def view_jsonl(file_path, n=5):
    print(f"JSONL 文件: {file_path}，显示前 {n} 条记录")
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"[WARN] 第 {i} 行不是有效 JSON")
                continue
            print(f"\n记录 {i}:")
            for key, value in record.items():
                print(f"  {key}: {truncate(value)}")

def main():
    if len(sys.argv) < 2:
        print("用法: python view_data.py <文件名或子目录/文件名> [显示条数]")
        sys.exit(1)

    file_input = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    # 使用当前工作目录为根路径
    file_path = Path(os.getcwd()) / file_input

    if not file_path.exists():
        print(f"[ERROR] 文件不存在: {file_path}")
        sys.exit(1)

    if file_path.suffix.lower() == ".csv":
        view_csv(file_path, n)
    elif file_path.suffix.lower() == ".jsonl":
        view_jsonl(file_path, n)
    else:
        print(f"[ERROR] 不支持的文件类型: {file_path.suffix}")
        sys.exit(1)

if __name__ == "__main__":
    main()
