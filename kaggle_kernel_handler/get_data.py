import os
import json
import time
import random
import logging
import subprocess
import re
import csv
from pathlib import Path
from io import StringIO

# 获取 main.py 定义的子 Logger
logger = logging.getLogger("main.downloader")

# 基础路径
WORKSPACE_DIR = Path("./local_workspace/output")
# 代码存储目录
CODE_DIR = WORKSPACE_DIR / "code"
# 信息记录目录
INFO_DIR = WORKSPACE_DIR / "info"
# 正则表达式预编译
# Python: import numpy / from math import sqrt
PY_IMPORT_RE = re.compile(r'^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)')
# R: library(dplyr) / require(ggplot2)
R_LIBRARY_RE = re.compile(r'(?:library|require)\s*\(\s*["\']?([a-zA-Z0-9_\.]+)["\']?\s*\)')

def run_cmd_with_retry(cmd, max_retries=3):
    """
    执行 Shell 命令，带有随机等待的重试机制
    """
    for attempt in range(1, max_retries + 1):
        try:
            # capture_output=True 在 Python 3.7+ 可用
            result = subprocess.run(
                cmd, 
                shell=True, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8' # 强制 utf-8
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.warning(f"命令执行失败 (尝试 {attempt}/{max_retries}): {cmd}")
            logger.warning(f"错误信息: {e.stderr.strip() if e.stderr else '无 stderr'}")
            
            if attempt < max_retries:
                wait_time = random.uniform(2, 5) * attempt
                logger.info(f"等待 {wait_time:.2f} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"命令最终失败: {cmd}")
                raise e
        except Exception as e:
            logger.error(f"未知错误: {e}")
            if attempt < max_retries:
                time.sleep(2)
            else:
                raise e

def extract_libs(content, language):
    """
    从代码文本中提取导入的库
    """
    libs = set()
    lines = content.split('\n')
    
    if language.lower() == 'python':
        for line in lines:
            match = PY_IMPORT_RE.match(line)
            if match:
                # 提取顶级包名 (例如 'sklearn.metrics' -> 'sklearn')
                full_pkg = match.group(1)
                root_pkg = full_pkg.split('.')[0]
                libs.add(root_pkg)
                
    elif language.lower() == 'r':
        for line in lines:
            # R 可以在一行中有多个代码，这里简化处理，主要匹配 library(...)
            matches = R_LIBRARY_RE.findall(line)
            for lib in matches:
                libs.add(lib)
    
    return list(libs)

def parse_notebook_content(file_path):
    """
    解析 .ipynb (JSON) 文件，合并所有 Code Cell 的内容
    """
    code_content = ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
            
        if 'cells' in notebook:
            for cell in notebook['cells']:
                if cell.get('cell_type') == 'code':
                    # source 可能是列表也可能是字符串
                    source = cell.get('source', [])
                    if isinstance(source, list):
                        code_content += "".join(source) + "\n"
                    else:
                        code_content += str(source) + "\n"
    except Exception as e:
        logger.error(f"解析 Notebook 失败 {file_path}: {e}")
    
    return code_content

def process_single_kernel(ref:str, code_dir:Path, page_records):
    """
    处理单个 Kernel：下载、解析、提取信息
    """
    # ref 格式通常为 "username/slug"
    # 将 ref 转换成合法的本地目录名
    slug = ref.split('/')[-1]
    dir_name = ref.replace('/', '_')
    kernel_dir = code_dir / dir_name
    
    if not kernel_dir.exists():
        kernel_dir.mkdir(parents=True)
    else:
        logger.info(f"目录已存在，跳过下载: {kernel_dir}")
        return
        
    try:
        # 1. 获取 Metadata 和 Source
        # -m: metadata, -p: path
        run_cmd_with_retry(f"kaggle kernels pull {ref} -p \"{kernel_dir}\" -m")
        
        # 2. 获取 Output (主要是为了 Log)
        # 注意：有些 Kernel output 很大，如果只想要 log，后续可能需要清理
        try:
            run_cmd_with_retry(f"kaggle kernels output {ref} -p \"{kernel_dir}\"")
        except Exception:
            logger.warning(f"获取 Output 失败或无 Output: {ref}，继续处理源文件")

        # 3. 解析 kernel-metadata.json
        meta_file = kernel_dir / "kernel-metadata.json"
        if not meta_file.exists():
            logger.error(f"元数据文件缺失: {ref}")
            return

        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        # 4. 寻找源文件
        # 源文件通常不是 kernel-metadata.json，也不是 .log 文件
        # 简单策略：遍历目录，排除特定文件
        source_file = None
        log_file = None
        for p in kernel_dir.iterdir():
            if p.name == "kernel-metadata.json":
                continue

            
            # 假设剩下的那个主要文件就是源码 (通常只有一个源码文件)
            # 如果有多个，优先取与 slug 同名或 main 的
            if p.suffix == '.log':
                log_file = p
                continue
            if p.is_file() and p.stem == slug and p.suffix != '.log':
                source_file = p
                continue

        if not source_file:
            logger.warning(f"未找到源文件: {ref}")
            return

        # 5. 提取内容和库
        language = meta.get('language', 'unknown')
        kernel_type = meta.get('kernel_type', 'unknown')
        imported_libs = []
        
        content = ""
        
        # 如果是 Notebook，需要解析 JSON
        if kernel_type == 'notebook' or source_file.suffix == '.ipynb':
            content = parse_notebook_content(source_file)
            # 统一将 notebook 后缀重命名/确保识别为 json (按 Prompt 要求)
            # 这里我们不改文件名，但在记录中标记，内容解析已完成
        else:
            # Script 脚本
            try:
                with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"读取源文件失败 {source_file}: {e}")

        # 提取库 (仅限 Python 和 R)
        if language in ['python', 'r']:
            imported_libs = extract_libs(content, language)
        else:
            logger.warning(f"非 Python/R 语言 ({language})，跳过库提取: {ref}")

        # 6. 构建记录
        record = {
            "id": meta.get("id"),
            "title": meta.get("title"),
            "kernel_type": kernel_type,
            "language": language,
            "log_file": log_file.name if log_file else "",
            "imported_libs": imported_libs
        }
        
        page_records.append(record)
        logger.info(f"成功处理: {ref} (Libs: {len(imported_libs)})")

    except Exception as e:
        logger.error(f"处理 Kernel {ref} 时发生严重错误: {e}")

def process_page(page_num):
    """
    处理单个页面的主入口
    """
    logger.info(f"正在获取第 {page_num} 页的列表...")
    
    if not CODE_DIR.exists():
        CODE_DIR.mkdir(parents=True)
    if not INFO_DIR.exists():
        INFO_DIR.mkdir(parents=True)

    page_records = []
    
    try:
        # 获取列表，使用 CSV 格式便于解析
        # --page-size 默认为 20，可以根据需要调整
        cmd = f"kaggle kernels list -p {page_num} --page-size 20 --csv"
        stdout = run_cmd_with_retry(cmd)
        
        if not stdout:
            logger.warning(f"第 {page_num} 页没有返回数据。")
            return False

        # 解析 CSV
        f = StringIO(stdout)
        reader = csv.DictReader(f)
        kernels = list(reader)
        
        if not kernels:
            logger.warning(f"第 {page_num} 页解析为空。")
            return False

        logger.info(f"第 {page_num} 页共找到 {len(kernels)} 个 Kernels，开始下载...")

        for row in kernels:
            # ref 通常是 CSV 中的 'ref' 字段 (格式 user/slug)
            ref = row.get('ref')
            if ref:
                process_single_kernel(ref, CODE_DIR, page_records)
            else:
                logger.warning("无法从 CSV 行中解析 ref")

        # 保存本页的汇总信息
        if page_records:
            output_jsonl = INFO_DIR / f"page_{page_num}.jsonl"
            with open(output_jsonl, 'w', encoding='utf-8') as f:
                for record in page_records:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            logger.info(f"第 {page_num} 页处理完成，记录已保存至 {output_jsonl}")
            return True
        else:
            output_jsonl = INFO_DIR / f"page_{page_num}.jsonl"
            print("Debug: output_jsonl path is exist:", output_jsonl.exists())
            if output_jsonl.exists():
                logger.info(f"第 {page_num} 页无有效记录，但已存在旧记录，保留原文件: {output_jsonl}")
                return True
            logger.warning(f"第 {page_num} 页未生成有效记录。")
            return False

    except Exception as e:
        logger.error(f"处理第 {page_num} 页时发生全局错误: {e}")
        return False

# 测试用
if __name__ == "__main__":
    # 简单配置 logging 用于单独测试
    logging.basicConfig(level=logging.INFO)
    process_page(1)