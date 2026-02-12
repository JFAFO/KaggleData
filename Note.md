# Note

#### 数据来源

* 官方api：https://github.com/Kaggle/kaggle-cli/tree/main/docs

* 官方维护的数据库meta-kaggle：https://www.kaggle.com/datasets/kaggle/meta-kaggle

  > 需要按照官网要求配置好`kaggle.json`
  >
  > 1. 去 Kaggle 官网 -> Settings -> API -> Create New Token。
  > 2. 下载 `kaggle.json` 文件。
  > 3. 将其放置在系统指定目录：
  >    - **Linux/Mac**: `~/.kaggle/kaggle.json` (并执行 `chmod 600 ~/.kaggle/kaggle.json`)
  >    - **Windows**: `C:\Users\<用户名>\.kaggle\kaggle.json`

#### 竞赛题目类

**来源：**除learderborad以外的利用meta kaggle中的数据Competitions.csv，leaderborad利用kaggle-cli的命令

**处理：**

* Compititions.csv：选取其中title为

  * ID  >  CompetitionID
  * Title  >  Title
  * Subtitle  >  SubTitle
  * "HasLeaderboard"  >  "HasLeaderboard"
  * DatasetDescription (html转化为md）> DatasetDescription 
  * Slug > Slug
  *  Overview (html转化为md，并提取其中标题Description下的内容)  >  Description
  *  Overview (html转化为md，并提取其中标题Evaluation下的内容)  >  Evaluation

  将其生成不带leaderborad的中间文件

* 再使用kaggle的命令行获取leaderborad
  ```bash
  kaggle competitions leaderboard <COMPETITION> [options]
  ```

  其中的`<COMPETITION>`即为slug

  读取之前生成的文件，再一一找到slug并查询leaderborad，添加再写如新的jsonl文件

**最终格式：**

*  CompetitionID: 2442
* Title: World Cup 2010 - Con...
* SubTitle: The Confidence Chall...
* Slug: worldcupconf
* HasLeaderboard: False
* DatasetDescription: # Dataset Descriptio...
* Description: We are also running ...
* Evaluation: The Confidence Chall...
* LeaderboardTop100: [{'Rank': 1, 'Team': 'Nan Zhou', 'Score': 0.98567, 'SubmissionCount': 63} ...]

**使用方法**

* `pip install requirements.txt`
* 下载Competitions.csv到文件夹中
* 启动`get_data_excp_ldrborad.py`
* 再运行`fetch_leaderborad.py`

> `generate_test_csv.py`用于基于Competitions.csv生成一个测试用的小的csv文件

#### 数据集

**来源：**

* 所有数据集列表：利用kaggle-cli的命令`kaggle datasets list --csv > datasetslist.csv`，保存到本地

* metadata：利用kaggle-cli的命令`kaggle datasets metadata <DATASET> -p [路径]`，需要下载到本地

* Content：`metadeta.json`中的description字段

* File Explorer：`kaggle datasets files <DATASET> --csv `

*   下载dataset：使用kagglehub的python库

  ```python
  import kagglehub
  # Download a dataset to a custom output directory.
  kagglehub.dataset_download('bricevergnou/spotify-recommendation', output_dir='./data')
  ```

**具体操作**

* 首先获取列表，保存在`./list`目录下
* 读取其中数据，若其中的usabilityRating小于0.8则不做处理，反之，保存ref字段新命名为Ref，title字段新命名为Title，LastUpdated字段新命名为lastUpdated，size字段新命名为DatasetSize，并保存到为jsonl文件
* 读取jsonl文件，按照其中的Ref字段作为`<DATASET>`获取metadata，并且保存到`./metadata_temp`，目录下
* 重新打开jsonl文件，按照`[Ref].json`到文件夹中搜索对应的metadata，读出内容，将licienses字段新命名为Licenses，keywords字段新命名为Tags，存到对应的jsonl对象内
* 依据Ref查询对应的文件描述，从终端输出读出，在jsonl中的每个数据集下创建File Explorer字段，其中存储着所有来自查询结果文件的文件名和对应的文件大小
* 最后下载dataset，为每个数据集在`./dataset`下创建同名文件夹，并将其下载到其中

**上传功能**

因为数据集较大，为了实现更持续的下载，设计了以也为单位的上传模块，基于AWS的s3协议

**使用说明**

* **核心功能模块**：

  1. **爬取与下载 (`get_data.py`)**：
     - **元数据获取**：通过 Kaggle CLI 获取数据集的列表、License、标签（Tags）和文件结构。
     - **过滤机制**：自动筛选 `usabilityRating >= 0.8` 的高质量数据集。
     - **并发下载**：使用 `kagglehub` 和线程池（ThreadPoolExecutor）并发下载数据集文件。
     - **数据落地**：将元数据保存为 JSONL 格式，数据集文件保存在 `local_workspace/output/datasets`。
  2. **云端上传 (`upload.py`)**：
     - **S3 兼容上传**：使用 `boto3` 连接对象存储（支持自定义 Endpoint）。
     - **递归上传**：保持数据集原有的文件夹结构上传至云端 `bucket`。
     - **空间管理**：实现“阅后即焚”机制，文件上传成功后立即删除本地文件，防止本地磁盘爆满。
     - **稳定性**：包含针对 Python 3.13 线程清理的兼容性修复。
  3. **流程编排 (`main.py`)**：
     - **命令行接口**：支持 `--local`（仅下载）和 `--upload`（下载并上传）两种模式。
     - **断点续传**：通过 `-c` 参数和 `setting/page_now.json` 记录，支持从上次中断的页码继续爬取。
     - **日志系统**：统一管理日志，生成包含时间戳和页码信息的详细运行日志。

  **项目文件结构**：

  ```
  .
  ├── main.py              # 程序入口
  ├── get_data.py          # Kaggle 爬虫与下载器
  ├── upload.py            # OSS 上传器
  ├── setting/             # 配置文件目录
  │   ├── cloud.json       # OSS 密钥配置
  │   └── page_now.json    # 进度记录
  └── local_workspace/     # (自动生成) 数据下载与日志目录
  ```


**配置项目 **

- 在项目根目录下手动创建 `setting` 文件夹和 `cloud.json` 文件，即`setting/cloud.json`

   ```
   {
       "ACCESS_KEY": "你的AccessKey",
       "SECRET_KEY": "你的SecretKey",
       "ENDPOINT_URL": "http://s3.cn-north-1.jdcloud-oss.com",
       "BUCKET_NAME": "aisec",
       "OSS_PREFIX": "kaggle_data"
   }
   ```

* `pip install -r requirements.txt`