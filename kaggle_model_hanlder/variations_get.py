import subprocess
import json
import logging
import time

logger = logging.getLogger("main.variation")


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
            logger.warning(f"执行失败，第 {i+1} 次重试: {e}")
            time.sleep(2 ** i)

    logger.error("命令执行最终失败")
    return None


def get_all_variation_version_slugs(model_ref):
    """
    遍历单个 model 的所有 variation
    返回所有 version slug 列表
    """

    cmd = [
        "kaggle",
        "models",
        "variations",
        "list",
        model_ref,
        "-v"
    ]

    output = safe_run(cmd)
    # 需要补全
    
    return ""
