import json
import subprocess
import tempfile
import os
import pandas as pd
import time
import random
import zipfile

MAX_RETRIES = 3
BASE_SLEEP = 2 

def download_leaderboard(slug: str, out_dir: str) -> bool:
    """
    下载排行榜 CSV，并捕获 stderr 以便调试。
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 使用 capture_output=True 来获取报错内容
            result = subprocess.run(
                ["kaggle", "competitions", "leaderboard", slug, "-d", "-p", out_dir],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"[成功] 已下载: {slug}")
            return True
        
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.lower()
            # 打印详细错误信息，方便你看到是 401(没登录) 还是 404(没榜)
            print(f"[调试] {slug} 第 {attempt} 次尝试失败。")
            print(f"[错误详情]: {e.stderr.strip()}")

            # 如果是 404 或明确找不到，直接跳过
            if "404" in stderr or "not found" in stderr:
                print(f"[跳过] {slug} 确定没有排行榜 (404)。")
                return False
            
            # 其他网络错误进行重试
            if attempt < MAX_RETRIES:
                sleep_time = BASE_SLEEP * attempt + random.uniform(1, 3)
                print(f"[重试] 等待 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)
            else:
                print(f"[失败] {slug} 已达到最大重试次数。")
    return False

def parse_leaderboard_csv(tmpdir: str, top_k: int = 100):
    """
    自动寻找并解压 tmpdir 下的 zip 文件，并解析其中的 CSV。
    """
    try:
        # 1. 查找 zip 文件
        zip_files = [f for f in os.listdir(tmpdir) if f.endswith(".zip")]
        
        # 如果有 zip，先全部解压
        for zf in zip_files:
            with zipfile.ZipFile(os.path.join(tmpdir, zf), 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
        
        # 2. 递归查找所有解压后的 CSV 文件
        all_files = []
        for root, dirs, files in os.walk(tmpdir):
            for file in files:
                if file.endswith(".csv"):
                    all_files.append(os.path.join(root, file))
        
        if not all_files:
            # 调试信息：打印出压缩包里到底有什么文件
            debug_list = []
            for root, dirs, files in os.walk(tmpdir):
                debug_list.extend(files)
            print(f"[调试] 目录下无CSV。现有文件: {debug_list}")
            return []

        # 3. 选取最像排行榜的文件（通常名字里带 leaderboard）
        csv_path = all_files[0]
        for f in all_files:
            if "leaderboard" in f.lower():
                csv_path = f
                break
        
        print(f"[解析] 正在读取: {os.path.basename(csv_path)}")

        # 4. 读取数据
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]
        
        column_mapping = {
            "TeamName": "Team", "Team": "Team",
            "Rank": "Rank", "Score": "Score",
            "Submissions": "Submissions", "Entries": "Submissions",
            "SubmissionCount":"SubmissionCount"
        }
        df = df.rename(columns=column_mapping)
        
        # 检查必要列
        if "Rank" not in df.columns:
            # 如果没有 Rank，尝试根据 Score 自动生成一个
            if "Score" in df.columns:
                df = df.sort_values("Score", ascending=False) # 假设分高者胜，不一定准确
                df['Rank'] = range(1, len(df) + 1)
            else:
                print(f"[警告] CSV 缺少关键列: {df.columns.tolist()}")
                return []

        required = ["Rank", "Team", "Score", "Submissions","SubmissionCount"]
        available = [c for c in required if c in df.columns]
        
        return df[available].sort_values("Rank").head(top_k).to_dict(orient="records")

    except Exception as e:
        print(f"[解析异常] {e}")
        return []
    

def fetch_leaderboards_from_jsonl(input_jsonl: str, output_jsonl: str, top_k: int = 100):
    if not os.path.exists(input_jsonl):
        print(f"[错误] 输入文件 {input_jsonl} 不存在！")
        return

    with open(input_jsonl, "r", encoding="utf-8") as fin, \
         open(output_jsonl, "w", encoding="utf-8") as fout:

        for line in fin:
            if not line.strip(): continue
            record = json.loads(line)
            slug = record.get("Slug")
            
            if not slug:
                continue

            print(f"\n>>> 正在处理比赛: {slug}")
            if record.get("HasLeaderboard", False) is False:
                print(f"[信息] {slug} 标记为没有排行榜，跳过下载。")
                record["LeaderboardTop100"] = []
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                fout.flush()
                continue
            with tempfile.TemporaryDirectory() as tmpdir:
                if download_leaderboard(slug, tmpdir):
                    # 查找解压后的 CSV 文件
                    record["LeaderboardTop100"] = parse_leaderboard_csv(tmpdir, top_k)
                else:
                    record["LeaderboardTop100"] = []

            # 写入结果并强制刷新到磁盘
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            fout.flush() 

if __name__ == "__main__":
    fetch_leaderboards_from_jsonl(
        "competitions_without_lrdbd.jsonl",
        "competitions_with_leaderboard.jsonl",
        top_k=100
    )