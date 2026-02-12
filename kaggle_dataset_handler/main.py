import argparse
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# 导入模块
import get_data
import upload

# 配置路径
SETTING_DIR = Path("setting")
PAGE_RECORD_FILE = SETTING_DIR / "page_now.json"
CLOUD_CONFIG_FILE = SETTING_DIR / "cloud.json"
LOG_DIR = Path("logs")
DATASET_INFO_DIR = Path("./local_workspace/output") # 对应 get_data 中的下载路径

def setup_logging(page_info):
    """
    配置日志：包含时间戳和页码信息
    同时捕获 upload.py 和 get_data.py 的日志
    """
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"run_{timestamp}_pages_{page_info}.log"
    log_path = LOG_DIR / log_filename

    # 配置 Root Logger
    root_logger = logging.getLogger("main")
    root_logger.setLevel(logging.INFO)
    
    # 清除旧的 handlers (防止重复打印)
    root_logger.handlers = []

    # File Handler
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Stream Handler (控制台输出)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(file_formatter)
    root_logger.addHandler(console_handler)

    print(f"日志已初始化: {log_path}")
    return root_logger

def load_page_record():
    if not PAGE_RECORD_FILE.exists():
        return 0
    try:
        with open(PAGE_RECORD_FILE, 'r') as f:
            data = json.load(f)
            return data.get("last_page", 0)
    except:
        return 0

def update_page_record(page_num):
    if not SETTING_DIR.exists():
        SETTING_DIR.mkdir()
    with open(PAGE_RECORD_FILE, 'w') as f:
        json.dump({"last_page": page_num}, f)

def get_target_pages(args, mode):
    """
    解析命令行参数，返回要处理的页码列表
    """
    pages = []
    
    # 处理 -c 模式 (仅限 --upload)
    if mode == 'upload' and args.c is not None:
        start_page = load_page_record() + 1
        count = args.c[0] # args.c 是一个列表
        end_page = start_page + count - 1
        return list(range(start_page, end_page + 1)), f"{start_page}_to_{end_page}"

    # 获取对应的参数列表
    vals = args.local if mode == 'local' else args.upload
    
    if not vals:
        return [], ""

    if len(vals) == 1:
        # 单个数字：只抓取该页
        p = vals[0]
        if p < 1:
            print("错误：页数必须大于 0")
            sys.exit(1)
        return [p], f"{p}"
    
    elif len(vals) == 2:
        # 两个数字：区间 [start, end]
        start, end = vals[0], vals[1]
        if start < 1 or end < start:
            print(f"错误：无效的区间 {start} - {end}")
            sys.exit(1)
        return list(range(start, end + 1)), f"{start}_to_{end}"
    
    else:
        print("错误：参数数量不正确，请输入 1 个数字(指定页) 或 2 个数字(区间)")
        sys.exit(1)

def run_workflow(pages, do_upload):
    logger = logging.getLogger("main")
    
    for page in pages:
        logger.info(f" >>>>>> 开始处理第 {page} 页 <<<<<<")
        
        # 1. 爬取数据
        success = get_data.process_page(page)
        
        if success:
            # 2. 如果需要上传
            if do_upload:
                logger.info(f"开始上传第 {page} 页的数据...")
                # 从 get_data 的输出目录上传
                # 注意：get_data 把所有下载内容放在 output/datasets 下
                # 理想情况下，我们应该只上传当前页下载的文件夹
                # 但由于 upload.py 逻辑是扫全文件夹，这里直接调用
                
                # 读取云配置
                try:
                    upload.upload_files_from_folder(str(DATASET_INFO_DIR))
                    
                    # 3. 更新进度 (仅在 -c 模式或连续上传模式下有意义，这里每次成功都更新以防中断)
                    # 为了简单起见，如果当前页大于记录页，则更新
                    current_record = load_page_record()
                    if page > current_record:
                        update_page_record(page)
                        logger.info(f"进度已更新: last_page = {page}")
                        
                except Exception as e:
                    logger.error(f"上传第 {page} 页时发生错误: {e}")
        else:
            logger.warning(f"第 {page} 页爬取失败或无数据，跳过上传。")

def main():
    parser = argparse.ArgumentParser(description="Kaggle 数据爬取与上传工具")
    
    # 互斥组：只能选 local 或 upload
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument('--local', type=int, nargs='+', 
                       help='仅本地爬取。用法: --local 5 (第5页) 或 --local 1 5 (1-5页)')
    
    group.add_argument('--upload', type=int, nargs='*', 
                       help='爬取并上传。用法: --upload 5 或 --upload 1 5。如果是 -c 模式可不填数字')

    parser.add_argument('-c', type=int, nargs=1,
                        help='接续模式 (仅配合 --upload)。用法: --upload -c 5 (从记录页开始往后爬5页)')

    # 解析参数
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # 逻辑验证
    mode = 'local' if args.local else 'upload'
    
    # 验证 -c 只能用于 upload
    if args.c and mode == 'local':
        print("错误：参数 -c 只能配合 --upload 使用")
        sys.exit(1)

    # 验证 --upload 如果没有 -c，必须有参数
    if mode == 'upload' and not args.c and not args.upload:
        print("错误：--upload 模式下，如果不使用 -c，必须指定页码或区间")
        sys.exit(1)

    # 获取要处理的页码
    target_pages, page_info_str = get_target_pages(args, mode)

    if not target_pages:
        print("没有需要处理的页码。")
        return

    # 初始化日志
    setup_logging(page_info_str)
    
    # 执行主流程
    run_workflow(target_pages, do_upload=(mode == 'upload'))

if __name__ == "__main__":
    main()