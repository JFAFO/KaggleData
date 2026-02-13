# Kaggle 站点爬取目标与策略

## 1. 概述
- **网站地址**: [https://www.kaggle.com](https://www.kaggle.com)
- **登录状态**: 网站需要登录访问。
- **核心数据**:
    - 竞赛题目 (Description)
    - 分析过程 (Notebooks)
    - 解答方案 (Discussions/Solutions)
- **训练价值**: 覆盖从问题定义 -> 数据探索 -> 代码实现 -> 结果解释的全流程。

---

## 2. 爬取建议与清洗逻辑

### 2.1 优先 Meta Kaggle 数据集
> **建议**: 优先利用 [Meta Kaggle 数据集](https://www.kaggle.com/datasets/kaggle/meta-kaggle)。
> Kaggle 官方提供了一个每日更新的 CSV 格式数据集，包含了几乎所有的竞赛元数据、用户、帖子、代码版本记录。先分析此数据集可极大减少直接爬取网页的压力。

### 2.2 长文本处理 (Notebooks)
- **存储格式**: 建议存储为 **JSONL** 格式。
- **结构保留**: 必须保留 `cell_type` (code/markdown) 的原始顺序，这对模型理解上下文逻辑至关至关。
- **质量控制**: 仅爬取获得勋章 (**Medal Winners**) 的 Notebook，确保数据质量。

### 2.3 数据清洗逻辑
- **有效性过滤**: 过滤掉纯代码、文字极少或全是重复模板的 Notebook。
- **标签转换**: 将 HTML 标签 (如 `<div>`, `<a>`) 转换为标准 Markdown。
- **图片处理**: 移除 Base64 编码，改为引用本地路径。
- **数学公式**: 保留 LaTeX 原始格式。
- **干扰剔除**: 剔除 HTML 广告、弹窗、冗余 UI 导航等。
- **语言标明**: 代码块必须标明语言类型 (`python`, `r`, `sql`)。

---

## 3. 详细爬取需求

### 3.1 竞赛题目类 (Competition Metadata)
- **页面**: `kaggle.com/competitions/[competition-name]/...`
- **采集内容**:
    - **Overview**: 标题、副标题、完整背景描述 (Description)、评估标准 (Evaluation)、奖金/奖牌设置。
    - **Data**: 数据集目录结构、字段描述 (Dictionary)。
    - **Leaderboard**: 前 100 名团队名、分数、提交次数。
- **核心字段**:
    - `CompetitionID`: 唯一标识
    - `Title`: 竞赛标题
    - `Description`: 背景问题 (HTML 转 Markdown)
    - `Evaluation`: 评价指标
    - `Data_Description`: 数据集字段含义说明

### 3.2 数据集 (Datasets)
- **范围**: 热门 (Hot) 及高评分 (Usability > 8.0) 的数据集。
- **页面**: `kaggle.com/datasets/[user]/[dataset-name]/...`
- **采集字段**:
    - **Metadata**: 名称、分类标签 (Tags)、更新频率、许可证 (License)。
    - **Content**: README 介绍文档 (Markdown)。
    - **File Explorer**: 文件列表、大小。
    - **Dataset 内容**: CSV/JSON/SQLite 等源文件。

### 3.3 代码与分析 (Code/Notebooks/Kernels) - SFT 核心
- **范围**: 所有获得勋章 (Medal) 的 Notebooks，script也要的
- **页面**: `kaggle.com/code/[user]/[slug]`
- **采集内容**:
    - **Notebook Structure**: 严格保留 Code 单元格和 Markdown 单元格的交替顺序。
    - **Outputs**: 执行后的文本输出、表格摘要、报错信息，`.log`
- **核心字段**:
    - `KernelID`: 唯一标识
    - `Source_Code`: 原始代码
    - `Library_Imports`: 统计使用的库列表
- **多模态增强**:
    - 先不弄了

### 3.4 模型库 (Models)
- **范围**: 官方及高获赞 (Most Upvoted) 模型。
- **页面**: `kaggle.com/models/[provider]/[model-name]`
- **采集字段**:
    - **Model Card**: 架构描述、训练数据、限制与偏差说明。
    - **Usage**: 官方示例代码。
    - **Frameworks**: PyTorch / TensorFlow / Jax。

### 3.5 问答与讨论 (Discussions/Q&A)
- **页面**: `kaggle.com/discussions/[topic-id]`
- **采集字段**:
    - **Thread**: 主帖标题、正文、发布时间。
    - **Comments**: 回复内容 (按层级序)。
    - **Voted Score**: 点赞数 (用于质量筛选)。
- **核心字段**:
    - `Topic_Title`: 讨论主题
    - `Thread_Context`: 完整的问答链
    - `Is_Accepted_Answer`: 是否为高赞/官方采纳

### 3.6 课程 (Learn)
- **范围**: 所有官方自研课程。
- **内容**: Tutorials (教学正文) 与 Exercises (练习题与答案)。

---

## 4. 多模态 SFT 特殊需求
*为增强模型“看图分析”能力，需额外提取:*
- **图片-文字关联**: 提取图表及其前后的“分析说明文字” (如：“如图所示，特征 A 与 B 正相关”)。
- **Schema 信息**: CSV/JSON 文件的列名与 Data Types 预览。
- **图像元数据**: 图像类数据集的标签 (Label) 与描述 (Caption)。
