import boto3
from botocore.exceptions import NoCredentialsError
import os
import json
from pathlib import Path
import threading
import atexit
import sys
import logging
# ACCESS_KEY = ''
# SECRET_KEY = ''

logger = logging.getLogger("main.uploader")
def get_oss_config():
    config_path = Path("setting/cloud.json")
    if not config_path.exists():
        logger.error("配置文件 setting/cloud.json 不存在")
        raise FileNotFoundError("setting/cloud.json not found")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    

# 修复 Python 3.13 的线程清理问题
def cleanup_threads():
    """清理所有非守护线程以避免 Python 3.13 的异常"""
    try:
        for thread in threading.enumerate():
            if thread != threading.main_thread() and not thread.daemon:
                thread.join(timeout=0.1)
    except:
        pass

# 注册退出时的清理函数
atexit.register(cleanup_threads)


def oss_client():
    config = get_oss_config()
    s3 = boto3.client(
        's3',
        aws_access_key_id=config["ACCESS_KEY"],
        aws_secret_access_key=config["SECRET_KEY"],
        endpoint_url = config["ENDPOINT_URL"],
    )
    # 列出现有桶
    logger.info(s3.list_buckets())
    return s3

def upload(bucket_name,object_key, file_name):
    s3 = oss_client()

    resp = s3.upload_file(file_name, bucket_name, object_key)
    print(resp)

def download(bucket_name,object_key, file_name):
    s3 = oss_client()
    s3.download_file(bucket_name, object_key, file_name)

def delete():
    s3 = oss_client()  # 创建OSS客户端连接对象，用于与阿里云对象存储服务进行交互
    resp = s3.delete_object(Bucket="您的已经存在的 bucket 名", Key="您要删除的文件名")  # 调用删除对象方法，从指定的存储桶中删除指定的文件对象

def upload_files_from_folder(folder_path, bucket_name=None, oss_prefix=None):
    """
    递归遍历指定文件夹及其所有子文件夹中的所有文件并上传到 OSS

    Args:
        folder_path (str): 本地文件夹路径
        bucket_name (str): OSS 存储桶名称
        oss_prefix (str): OSS 文件前缀，默认为空
    """
    config = get_oss_config()
    if not bucket_name:
        bucket_name = config['BUCKET_NAME']
    if oss_prefix is None:
        oss_prefix = config['OSS_PREFIX']

    s3 = oss_client()
    folder_path = Path(folder_path)

    if not folder_path.exists():
        print(f"错误：文件夹 {folder_path} 不存在")
        return

    if not folder_path.is_dir():
        print(f"错误：{folder_path} 不是一个文件夹")
        return

    # 递归遍历所有子文件夹中的所有文件
    dir_and_files = sorted(folder_path.rglob("*"), key=lambda x: x)
    # 过滤掉目录，只保留文件
    all_files = [f for f in dir_and_files if f.is_file()]

    # 只取 part-00101_split_0000.json 之后的文件
    # cutoff_file = "part-00201_split_0000.json"
    # cutoff_index = next((i for i, f in enumerate(json_files) if f.name == cutoff_file), -1)
    # if cutoff_index >= 0:
    #     json_files = json_files[cutoff_index + 1:]
    #     print(f"从 {cutoff_file} 之后开始上传，共 {len(json_files)} 个文件")
    # else:
    #     print(f"未找到 {cutoff_file}，将上传所有文件")

    # if not json_files:
    #     print(f"在文件夹 {folder_path} 中没有找到符合条件的 JSON 文件")
    #     return

    logger.info(f"OSS上传准备: 找到 {len(all_files)} 个文件")

    success_count = 0
    error_count = 0

    for file in all_files:
        try:
            # 获取相对于根文件夹的路径，保持目录结构
            relative_path = file.relative_to(folder_path)
            oss_path = relative_path.as_posix()
            # 构建 OSS 对象键，保持原有的目录结构
            if oss_prefix:
                object_key = f"{oss_prefix.rstrip('/')}/{oss_path}"
            else:
                object_key = str(relative_path)

            # 上传文件
            logger.info(f"正在上传: {relative_path} -> {object_key}")
            s3.upload_file(str(file), bucket_name, object_key)
            logger.info(f"✓ 成功上传: {relative_path}")

            # 上传成功后永久删除本地文件（不放到废纸篓）
            try:
                os.remove(str(file))
                logger.info(f"  已删除: {relative_path}")
            except Exception as delete_error:
                logger.warning(f"  警告: 删除文件失败 {relative_path}: {delete_error}")

            success_count += 1

        except Exception as e:
            logger.error(f"✗ 上传失败 {file.name}: {e}")
            error_count += 1

    logger.info(f"\n上传完成！成功: {success_count}, 失败: {error_count}")

    # 手动清理线程以避免 Python 3.13 的异常
    cleanup_threads()

def generate_presigned_url(bucket_name, object_key, expiration=3600):
    try:
        s3 = oss_client()

        response = s3.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name, 'Key': object_key},
                                                    ExpiresIn=expiration)
        return response
    except NoCredentialsError:
        print("Error: AWS凭证未找到。请配置您的AWS凭证。")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


# 使用示例
if __name__ == "__main__":
    # 配置参数
    bucket_name = "aisec"
    folder_path = "/Users/pengshuo.10/Downloads/ossutil-v1.7.19-mac-arm64/" # 这个是本地的文件夹
    oss_prefix = "kaggle_data"  # 在OSS中的文件夹前缀，可根据需要修改

    # 这里实际上并没有过滤文件，直接上传整个文件夹中的所有文件
    upload_files_from_folder(folder_path, bucket_name, oss_prefix)
    

