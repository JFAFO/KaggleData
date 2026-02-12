import os
import json
import csv
import shutil
import logging
import subprocess
import argparse
import kagglehub
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= 模块 1: 基础配置与工具 =================
# 配置区域
BASE_DIR = Path("./local_workspace")
UPLOAD_DIR = BASE_DIR / "output"
DATASET_DIR = UPLOAD_DIR / "datasets"          # 存放下载的具体数据

JSONL_DIR = UPLOAD_DIR / "meta_data"        # 存放生成的 jsonl 记录


METADATA_DIR = BASE_DIR / "metadata_temp"    # 临时存放元数据
# 确保目录存在
for p in [DATASET_DIR, METADATA_DIR, JSONL_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# 日志配置
logger = logging.getLogger("main.downloader")

def run_cmd(cmd):
    try:
        # 使用 check=True 配合捕获
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        
        # 核心改进：识别网络中止的关键词
        error_keywords = ["Connection aborted.", "RemoteDisconnected", "BrokenPipeError", "connection reset"]
        output = result.stdout + result.stderr
        
        if any(key in output for key in error_keywords):
            logger.error(f"检测到网络链接中止: {output}")
            raise ConnectionError(f"Kaggle 链接已断开: {output}") # 抛出异常触发装饰器
            
        if result.returncode != 0:
            raise RuntimeError(f"命令执行失败 (Code {result.returncode}): {output}")
            
        return result.stdout
    except Exception as e:
        # 让异常向上传递给 @retry_on_failure
        raise e
# ================= 模块 2: Kaggle 核心逻辑 (获取信息与下载) =================

def retry_on_failure(max_retries=3, base_delay=5, backoff_factor=2):
    """
    重试装饰器
    :param max_retries: 最大重试次数
    :param base_delay: 基础等待秒数
    :param backoff_factor: 指数倍数 (例如 5, 10, 20...)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 如果重试次数耗尽，抛出异常
                    if retries == max_retries:
                        logger.error(f"方法 {func.__name__} 在重试 {max_retries} 次后依然失败: {e}")
                        raise e
                    
                    # 计算等待时间：base_delay * (backoff_factor ^ retries) + 随机抖动
                    wait_time = (base_delay * (backoff_factor ** retries)) + random.uniform(1, 3)
                    logger.warning(f"[{func.__name__}] 触发限流或错误: {e}。 "
                                   f"{wait_time:.1f}秒后进行第 {retries + 1} 次重试...")
                    
                    time.sleep(wait_time)
                    retries += 1
            return None
        return wrapper
    return decorator




class KaggleProcessor:
    def __init__(self):
        pass
    
    
    @retry_on_failure(max_retries=3, base_delay=3)
    def get_metadata(self, ref):
        """获取数据集的 Licenses 和 Tags"""
        temp_path = METADATA_DIR / ref.replace("/", "_")
        temp_path.mkdir(exist_ok=True)
        
        # 调用 Kaggle CLI 下载元数据
        run_cmd(f"kaggle datasets metadata {ref} -p {temp_path}")
        
        meta_file = temp_path / "dataset-metadata.json"
        data = {"Licenses": [], "Tags": []}
        
        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    info = content.get("info", {})  # 取 info 层
                    licenses = info.get("licenses", [])
                    keywords = info.get("keywords", [])
                    description = info.get("description", "")
                    # licenses 是对象列表，提取 name 字段
                    licenses_list = [l.get("name") for l in licenses if "name" in l]

                    # print(f"[{ref}] Licenses: {licenses_list}, Tags: {keywords}")
                    data["Licenses"] = licenses_list
                    data["Tags"] = keywords
                    data["Content"] = description
            except Exception as e:
                logger.warning(f"[{ref}] 读取元数据 JSON 失败: {e}")
        
        # 清理元数据临时文件
        shutil.rmtree(temp_path, ignore_errors=True)
        return data
    
    
    @retry_on_failure(max_retries=3, base_delay=3)
    def get_file_explorer(self, ref):
        """获取数据集的文件列表"""
        csv_out = run_cmd(f"kaggle datasets files {ref} --csv")
        if not csv_out or "429 - Too Many Requests" in csv_out:
            raise RuntimeError(f"Kaggle API 拒绝请求或返回为空: {ref}")
        files = []
        if csv_out:
            reader = csv.DictReader(csv_out.splitlines())
            for row in reader:
                files.append({
                    "FileName": row.get("name"),
                    "Size": row.get("size")
                })
        return files

    @retry_on_failure(max_retries=3, base_delay=3)
    def download_dataset(self, ref):
        """下载数据集文件到本地指定目录"""
        target_dir = DATASET_DIR / ref.split("/")[-1]
        
        if target_dir.exists():
            logger.info(f"[{ref}] 本地已存在，跳过下载")
            return str(target_dir)

        logger.info(f"[{ref}] 开始下载...")
        
        # 使用 kagglehub 下载到缓存
        cached_path = kagglehub.dataset_download(ref)
        if not cached_path:
            raise RuntimeError(f"kagglehub 下载返回路径为空: {ref}")
        # 将文件从缓存移动到我们的测试目录，方便查看
        shutil.copytree(cached_path, target_dir, dirs_exist_ok=True)
        logger.info(f"[{ref}] 下载并移动完成 -> {target_dir}")
        return str(target_dir)


    def process_single_item(self, row):
        """处理单条数据的完整流程"""
        ref = row['ref']
        
        # 1. 基础字段重命名
        item = {
            "Ref": row['ref'],
            "Title": row['title'],
            "lastUpdated": row['lastUpdated'],
            "DatasetSize": row['size'],
            "usabilityRating": row['usabilityRating']
        }

        # 2. 注入元数据
        meta = self.get_metadata(ref)
        item.update(meta)

        # 3. 注入文件列表
        files = self.get_file_explorer(ref)
        item["File Explorer"] = files

        # 4. 执行下载
        local_path = self.download_dataset(ref)
        
        if local_path:
            return item
        else:
            return None

# ================= 模块 3: 流程控制 (按页处理) =================

def process_page(page_num, max_workers=4) -> bool :
    processor = KaggleProcessor()
    logger.info(f"========== 正在获取第 {page_num} 页列表 ==========")
    
    # 1. 获取列表
    csv_data = run_cmd(f"kaggle datasets list --page {page_num} --csv")
    if not csv_data:
        logger.warning("未获取到数据，可能已到达末尾。")
        return False

    rows = list(csv.DictReader(csv_data.splitlines()))
    
    # 2. 筛选
    targets = [r for r in rows if float(r.get('usabilityRating', 0)) >= 0.8]
    logger.info(f"本页原始数据: {len(rows)} 条，筛选后(>=0.8): {len(targets)} 条")

    processed_results = []

    # 3. 并发处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(processor.process_single_item, row): row['ref'] for row in targets}
        
        for future in as_completed(futures):
            ref = futures[future]
            try:
                result = future.result()
                if result:
                    processed_results.append(result)

            except Exception as e:
                logger.error(f"处理 {ref} 时发生未知错误: {e}")

    # 4. 保存本页的 JSONL 结果
    if processed_results:
        output_file = JSONL_DIR / f"page_{page_num}.jsonl"
        with open(output_file, 'w', encoding='utf-8') as f:
            for obj in processed_results:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        logger.info(f"第 {page_num} 页处理完成！JSONL 已保存至: {output_file}")
        logger.info(f"文件已下载至: {DATASET_DIR}")
        return True
    else:
        logger.info(f"第 {page_num} 页没有成功处理的数据。")
        return False

# ================= 主程序入口 =================

if __name__ == "__main__":
    # 可以在这里修改你要测试的页码
    TEST_PAGE = 1 
    
    print(f"开始本地测试，将处理第 {TEST_PAGE} 页的数据...")
    print(f"结果将保存在: {BASE_DIR.absolute()}")
    
    process_page(TEST_PAGE)
    
    print(f"\n测试结束。请检查 {BASE_DIR.name} 文件夹。")