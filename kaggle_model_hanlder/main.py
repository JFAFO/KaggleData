import argparse
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

import get_data
import upload

SETTING_DIR = Path("setting")
TOKEN_RECORD_FILE = SETTING_DIR / "page_now.json"
LOG_DIR = Path("logs")
DATASET_INFO_DIR = Path("./local_workspace/output")


def setup_logging(token_info):
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"run_{timestamp}_token_{token_info}.log"
    log_path = LOG_DIR / log_filename

    root_logger = logging.getLogger("main")
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    print(f"日志已初始化: {log_path}")
    return root_logger


def load_token_record():
    if not TOKEN_RECORD_FILE.exists():
        return None
    try:
        with open(TOKEN_RECORD_FILE, 'r') as f:
            data = json.load(f)
            return data.get("last_token")
    except:
        return None


def update_token_record(token):
    if not SETTING_DIR.exists():
        SETTING_DIR.mkdir()
    with open(TOKEN_RECORD_FILE, 'w') as f:
        json.dump({"last_token": token}, f)


def run_workflow(start_token, count, do_upload):
    logger = logging.getLogger("main")

    current_token = start_token

    for i in range(count):
        logger.info(f"====== 处理批次 {i+1} ======")
        logger.info(f"当前 token: {current_token}")

        result = get_data.process_one_page(current_token)

        if not result:
            logger.error("本页处理失败")
            return

        next_token = result["next_token"]

        if do_upload:
            logger.info("开始上传当前批次数据")
            upload.upload_files_from_folder(str(DATASET_INFO_DIR))

        update_token_record(next_token)
        current_token = next_token


def main():
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument('--local', type=int,
                       help='从头开始抓取 N 批')

    group.add_argument('--upload', type=int, nargs='?',
                       help='抓取并上传 N 批')

    parser.add_argument('-c', type=int,
                        help='接续模式，仅配合 --upload')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.local:
        count = args.local
        start_token = None

    elif args.upload is not None:

        if args.c:
            start_token = load_token_record()
            count = args.c
        else:
            start_token = None
            count = args.upload

    else:
        print("参数错误")
        return

    setup_logging(start_token if start_token else "start")
    run_workflow(start_token, count, do_upload=(args.upload is not None))


if __name__ == "__main__":
    main()
