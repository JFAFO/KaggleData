import subprocess
import json
import logging
import time
from pathlib import Path
import csv
from io import StringIO
from variation_processor import process_variations

logger = logging.getLogger("main.get_data")

TEMP_DIR = Path("./local_workspace/temp_meta")
OUTPUT_DIR = Path("./local_workspace/output/info")


def safe_run(cmd, retry=3):
    for i in range(retry):
        try:
            logger.info(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except Exception as e:
            logger.warning(f"失败重试 {i+1}: {e}")
            time.sleep(2 ** i)
    return None


def process_one_page(token):
    cmd = [
        "kaggle",
        "models",
        "list",
        "--sort-by",
        "voteCount",
        "-v"
    ]

    if token:
        cmd += ["--page-token", token]

    output = safe_run(cmd)
    if not output:
        return None

    lines = output.strip().split("\n")

    # 第一行是 Next Page Token
    first_line = lines[0].strip()

    if first_line.startswith("Next Page Token"):
        next_token = first_line.split("=", 1)[1].strip()
        header = lines[1].split(",")
        data_lines = lines[2:]
    else:
        logger.error("未检测到 Next Page Token，格式异常")
        return None

    csv_content = "\n".join(data_lines)

    reader = csv.DictReader(StringIO(csv_content))

    models = []

    for row in reader:
        model_ref = row["ref"]
        owner, model_slug = model_ref.split("/", 1)

        models.append({
            "ownerSlug": owner,
            "modelSlug": model_slug,
            "ref": model_ref,
            "title": row["title"],
            "variations":[]
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    token_prefix = token[:6] if token else "start"

    output_file = OUTPUT_DIR / f"page_{token_prefix}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2)

    logger.info(f"保存完成: {output_file}")

    # 遍历 variation
    for m in models:
        logger.info(f"获取模型{m["ref"]}的metadata,并提取description")
        cmd = ["kaggle", "models", "get", m["ref"], "-p", str(TEMP_DIR)]
        output = safe_run(cmd)
        
        if output is None:
            logger.error(f"无法获取模型 {m["ref"]} 的元数据，跳过。")
            continue

        # 2. 定位唯一的 JSON 文件
        json_files = list(TEMP_DIR.glob("*.json"))
        
        if len(json_files) != 1:
            logger.error(f"文件夹状态异常：期望 1 个 JSON，实际找到 {len(json_files)} 个。")
            # 清理残留文件防止影响下一次循环
            for f in json_files: f.unlink()
            continue

        json_path = json_files[0]

        try:
            # 3. 读取并处理数据
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 字段重映射逻辑

            m["modelCard"] = data.get("description","")
            logger.info(f"成功记录模型: {m['modelSlug']}")

        except Exception as e:
            logger.error(f"解析 JSON 出错: {e}")
        finally:
            # 4. 无论成功失败，删除该文件以保证下次循环时文件夹唯一
            if json_path.exists():
                json_path.unlink()
                logger.debug(f"已清理临时文件: {json_path.name}")
        
        logger.info(f"处理 model: {m['ref']} 的所有variations")
        process_variations(m, token_prefix)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2)

    return {"next_token": next_token}
