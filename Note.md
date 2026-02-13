# Note

#### 数据来源

* 官方api  >  kaggle-cli ：https://github.com/Kaggle/kaggle-cli/tree/main/docs

* 官方api  >  kagglehub ：https://github.com/Kaggle/kagglehub/blob/main/README.md

* 官方维护的数据库meta-kaggle：https://www.kaggle.com/datasets/kaggle/meta-kaggle

  > https://www.kaggle.com/docs/api#authentication
  >
  > 需要按照官网要求配置好`kaggle.json`
  >
  > 1. 去 Kaggle 官网 -> Settings -> API -> Create New Token。
  > 2. 下载 `kaggle.json` 文件。
  > 3. 将其放置在系统指定目录：
  >    - **Linux/Mac**: `~/.kaggle/kaggle.json` (并执行 `chmod 600 ~/.kaggle/kaggle.json`)
  >    - **Windows**: `C:\Users\<用户名>\.kaggle\kaggle.json`
  >
  > 要确保kaggle的版本等，防止使用cli时出现提示信息，导致脚本解析格式失败

#### 竞赛题目

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

因为数据集较大，为了实现更持续的下载，设计了以页为单位的上传模块，基于AWS的s3协议

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

**最终格式**

* 上传后指定路径下（对应本地的`./local_workspace/output`）有`meta_data`和`dataset`两个文件夹

* `meta_data`中存储着以页为单位的jsonl信息，名称为`page_[num].jsonl`，其中字段如下：

  ```json
  {
      "Ref": "",
      "Title": "",
      "lastUpdated": "[time]",
      "DatasetSize": 100,
      "usabilityRating": 0.1,
      "File Explorer":[],
      "Licenses":[],
      "Tags":[],
      "Content":"...",
  	"File Explorer":[]
  }
  ```

* `dataset`文件夹中，每个数据集都有自己的子文件夹，名称为Ref中的`/`被替换成了`_`，其中报存的是数据集的所有文件

#### 代码数据

**资源获取**

* 获取列表：

  ```bash
  kaggle kernels list
  ```

* 获取meta data和源文件

  ```bash
  kaggle kernels pull [slug/id 这次是一样的] -p [dir] -m

* 获取output

  ```bash
  kaggle kernels [同上] -p [同上]
  ```

**操作思路**

* 获取list，然后根据ref依次请求metadata和源文件和log，存储在对应slug为名字的文件夹

  > log文件的结尾为`.log`，metadata的同一命名方式为`kernel-metadata.json`，剩下的源文件不一定

* 根据metadata提取重要信息，id，title，kernel_type、language，放到这页的同一记录的jsonl文件

* 寻找源文件中所有导入的库，识别出来（默认只有python和R语言），同样放到以页为单位的记录文件中

  > 注：
  >
  > 1. kernel_type有script和notebook两种，前者就是直接的代码
  > 2. 对于notebook，是`.ipynb`格式的，但文件后缀不一定，统一改为json存储（可通过cell_type为code搜索代码块）
  > 3. 若出现不是python或R的情况，则导入库记录为空，并抛出log warning 

**上传功能**

因为数据集较大，为了实现更持续的下载，设计了以页为单位的上传模块，基于AWS的s3协议

**使用说明、项目配置：**与数据集的相同

**最终格式**

* 上传后指定路径下（对应本地的`./local_workspace/output`）有`info`和`code`两个文件夹

* `info`中存储着以页为单位的json信息，名称为`page_[num].json`，其中字段如下：

  ```json
  {
      "id": "",
      "title": "",
      "kernel_type": "",
      "language": "",
      "log_file": "[name]",
      "imported_libs": []
  }
  ```

* `dataset`文件夹中，每kernel都有自己的子文件夹，名称为id中的`/`被替换成了`_`，其中报存的是kernel的metadata、源文件、log文件

#### 模型获取

> ## 注意：
>
> 这里没有最终实现完成，因为kaggle cli的bug，导致无法获取variation的list，故不知道格式，等到恢复后若想使用可自行补齐`variations_get.py`，其中的函数是用来遍历指定model所有的variations，并返回其列表
>
> **因此项目也没通过调试，可能会有bug**

**获取资源**

- 获取列表

  ```bash
  kaggle models list [options]
  ```

  * 要使用 `-v`获取`csv`
  * 使用`--sort-by voteCount`

* 获取模型metadata

  ```shell
  kaggle models get [list中得到的ref字段] -p [path]
  ```

* 获取模型的variation

  ```bash
  kaggle models variations list [options]
  ```

* 获取variation的metadata

  ```bash
  kaggle models variations get [] -p [path]
  ```

* 下载对应版本的模型文件

  ```bash
  kaggle models variations versions download <MODEL_VARIATION_VERSION> [options]
  ```
  
  - `-p, --path <PATH>`: Folder to download files to (defaults to current directory).
  - `--untar`: Untar the downloaded file if it's a `.tar` archive (deletes the `.tar` file afterwards).
  - `--unzip`: Unzip the downloaded file if it's a `.zip` archive (deletes the `.zip` file afterwards).

**具体流程**

* 获取list的一页，

  分别获取model的所有metadata下载到`./local_workspace/temp_meta`，记录字段ownerSlug不变、字段slug改名为modelSlug，description字段改名modelCard，将三者记录并删除文件，

  按照这种方式处理完页的所有model，创建文件`./local_workspace/output/info/page_[page token的前6位].json`，将记录的内容保存其中

* 对所有model重复以下内容

  * 一个单独的模块遍历单个model的所有variation，返回所有版本的slug
  * 对每个variation
    * 按照slug，依次下载它的metadata（json文件），保存framework为framework，instanceSlug为instanceSlug，usage为usage
    * 将其记录到`./local_workspace/output/info/page_[page token的前6位].json`中的对应model下
    * 创建文件夹`./local_workspace/output/model/[ownerSlug]_[modelSlug]/[framework]/[instanceSlug]`，将这个metadata放进去，并依据其中的versionNumber字段下载，将模型文件下载在其中（要解压）

* 通过main函数控制整体循环，并集成上传功能

**使用说明、配置方法：**与数据集类似，但只支持`-c`和从头开始若干页的爬取，具体可见`-h`

**项目结构**

```css
local_workspace/
│
├── temp_meta/                  # 临时metadata缓存
│   └── *.json
│
├── output/
│   ├── info/
│   │   ├── page_CfDJ8E.json
│   │   └── page_xxxxxx.json
│   │
│   └── model/
│       └── google_gemma/
│           ├── README.txt                # 可选说明文件
│           └── tensorflow/
│               └── gemma-2b/
│                   ├── metadata.json
│                   ├── model.bin
│                   ├── config.json
│                   ├── tokenizer.json
│                   └── version.txt
│
├── logs/
│   └── run_20260213_token_xxxx.log
│
└── setting/
    ├── page_now.json
    └── cloud.json

```

**最终数据格式**

```json
// info文件夹中的记录
[
  {
    "ownerSlug": "google",
    "modelSlug": "gemma",
    "ref": "google/gemma",
    "variations": [
      {
        "framework": "tensorflow",
        "instanceSlug": "gemma-2b",
        "usage": "inference",
        "versionNumber": 3
      }
    ]
  }
]
```

#### 问答与讨论

没有api，对于动态网页，实现比较困难，这里没有做

#### 课程

同样的，没有api且为动态网页，并且教案就是kernel，即代码部分已实现，同时作业总体量较小，这里也没有做
