import subprocess
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("main.variation")
from variations_get import get_all_variation_version_slugs
TEMP_META_DIR = Path("./local_workspace/temp_meta")
MODEL_OUTPUT_DIR = Path("./local_workspace/output/model")


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
            logger.warning(f"失败重试 {i+1}/{retry}: {e}")
            time.sleep(2 ** i)
    logger.error("命令最终失败")
    return None


def process_variations(model_info, page_token_prefix):
    """
    处理单个 model 的所有 variation
    """

    owner = model_info["ownerSlug"]
    model_slug = model_info["modelSlug"]
    model_ref = model_info["ref"]

    # 1️⃣ 获取 variation 列表
    variation_slugs = get_all_variation_version_slugs(model_ref)


    # 2️⃣ 遍历 variation
    for variation_ref in variation_slugs:

        # 下载 metadata
        TEMP_META_DIR.mkdir(parents=True, exist_ok=True)

        meta_cmd = [
            "kaggle",
            "models",
            "variations",
            "get",
            f"{model_ref}/{variation_ref}",
            "-p",
            str(TEMP_META_DIR)
        ]

        safe_run(meta_cmd)

        # metadata 文件名就是 slug.json
        json_files= list(TEMP_META_DIR.glob("*.json"))
    
        count = len(json_files)
    
        if count == 1:
            meta_file = json_files[0]
        elif count == 0:
            logger.error(f"错误：在 {TEMP_META_DIR} 中未找到任何 .json 文件。")
        else:
            logger.error(f"错误：在 {TEMP_META_DIR} 中找到了 {count} 个 .json 文件，预期仅有 1 个。")

        with open(meta_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        framework = metadata.get("framework", "unknown")
        instance_slug = metadata.get("instanceSlug", "unknown")
        usage = metadata.get("usage", "")
        version_number = metadata.get("versionNumber")

        # 记录到 model_info
        model_info["variations"].append({
            "framework": framework,
            "instanceSlug": instance_slug,
            "usage": usage,
            "versionNumber": version_number
        })

        # 创建目录
        target_dir = (
            MODEL_OUTPUT_DIR
            / f"{owner}_{model_slug}"
            / framework
            / instance_slug
        )

        target_dir.mkdir(parents=True, exist_ok=True)

        # 移动 metadata
        meta_target = target_dir / "metadata.json"
        meta_file.replace(meta_target)

        # 下载模型文件
        if version_number is not None:

            download_cmd = [
                "kaggle",
                "models",
                "variations",
                "versions",
                "download",
                f"{model_ref}/{variation_ref}/{version_number}",
                "-p",
                str(target_dir),
                "--untar",
                "--unzip"
            ]

            safe_run(download_cmd)

    return model_info["variations"]
