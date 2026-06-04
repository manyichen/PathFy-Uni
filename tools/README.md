# 项目工具脚本（`tools/`）

仓库根目录下的运维与数据脚本，按职责分子目录。**均在项目根目录执行**（读取 `backend/.env` 或各自子目录配置）。

## 目录结构

```
tools/
├── README.md                 # 本说明
├── csv/                      # 数据集 CSV：生成、校验、统计
│   ├── build_competitions_csv.py
│   ├── build_promotion_recommendations_csv.py
│   ├── validate_learning_resource_urls.py
│   ├── validate_competition_urls.py
│   └── analyze_job_title_counts.py
├── neo4j/                    # 知识图谱：同步、回填、检查
│   ├── sync_neo4j_job_titles.py
│   ├── sync_neo4j_learning_resources.py
│   ├── sync_neo4j_competitions.py
│   ├── sync_neo4j_job_promotions.py
│   ├── sync_neo4j_promotion_recommendations.py
│   ├── backfill_job_salary_norm.py
│   ├── cleanup_neo4j_inferred_jobs.py
│   └── check_neo4j_duplicates.py
└── job_eval/                 # 岗位八维能力 LLM 批量评估（独立依赖）
    ├── README.md
    ├── requirements.txt
    ├── run_job_eval_batch.py
    ├── import_job_eval_jsonl.py
    ├── make_qc_report.py
    └── debug.sh
```

### 相关目录（不在 `tools/` 根下）

| 路径 | 用途 |
|------|------|
| `backend/tools/` | MySQL 迁移 `run_migration_00x.py`、图谱分析 `analyze_neo4j_graph.py` |
| `generate_graph/` | 从招聘数据批量生成/导入 `Job` 节点 |
| `datasets/` | CSV 源数据：`master/`、`promotion/`、`snapshots/` |

`job_eval/` 内可能含 `.venv`、`job_eval_results_*.jsonl`、`.env` 等本地产物，勿提交仓库。

---

## `csv/` — 数据集流水线

| 脚本 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `build_competitions_csv.py` | 竞赛 Excel（可配置路径） | `datasets/master/competitions.csv` | 竞赛主表 |
| `build_promotion_recommendations_csv.py` | `promotion/` + `master/` CSV | `promotion/promotion_*.csv` | 晋升推荐关联 |
| `validate_learning_resource_urls.py` | `master/learning_resources.csv` | 终端报告 | HTTP 校验慕课/文档链接 |
| `validate_competition_urls.py` | `master/competitions.csv` | 终端报告 | 校验竞赛链接 |
| `analyze_job_title_counts.py` | 图谱或 CSV | 统计输出 | 岗位记录数分析 |
| `build_job_title_lateral_similarity.py` | master + promotion CSV、Neo4j cap | `master/job_title_lateral_transfer.csv` | JobTitle 水平换岗相似边 |

```bash
python tools/csv/build_promotion_recommendations_csv.py
python tools/csv/validate_learning_resource_urls.py
```

详见：`datasets/promotion/job_title_promotion_recommendations_schema.md`、`datasets/promotion/job_title_promotions_schema.md`。

---

## `neo4j/` — 知识图谱同步

依赖 `backend/.env` 中的 `NEO4J_*`。建议 **`--dry-run` 先预览**，再正式写入。

### 推荐导入顺序

```mermaid
flowchart LR
  A[job_titles / jobs] --> B[learning_resources]
  A --> C[competitions]
  B --> D[job_promotions]
  C --> D
  D --> E[promotion_recommendations]
```

| 顺序 | 脚本 | 图谱效果 |
|------|------|----------|
| 1 | `sync_neo4j_job_titles.py` | `Job` —`HAS_TITLE`→ `JobTitle` |
| 2 | `sync_neo4j_learning_resources.py` | `LearningResource` —`FOR_JOB_TITLE`→ `JobTitle` |
| 3 | `sync_neo4j_competitions.py` | `Competition` —`FOR_JOB_TITLE`→ `JobTitle` |
| 4 | `sync_neo4j_job_promotions.py` | `JobPromotion` 节点及 —`FOR_JOB_TITLE`→ `JobTitle` |
| 5 | `sync_neo4j_promotion_recommendations.py` | `RECOMMENDS_RESOURCE` / `RECOMMENDS_COMPETITION` |
| 可选 | `backfill_job_salary_norm.py` | 回填 `Job.salary_norm` 等字段 |
| 可选 | `cleanup_neo4j_inferred_jobs.py` | 清理推断岗位 |
| 检查 | `check_neo4j_duplicates.py` | 节点/关系重复与数量核对 |
| 6b | `sync_neo4j_job_title_lateral.py` | `SIMILAR_FOR_LATERAL`：JobTitle 水平换岗相似 |

```bash
python tools/neo4j/sync_neo4j_learning_resources.py --dry-run
python tools/neo4j/sync_neo4j_learning_resources.py

python tools/csv/build_promotion_recommendations_csv.py
python tools/neo4j/sync_neo4j_promotion_recommendations.py
```

**说明：** `RECOMMENDS_*` 关系按 `(JobPromotion, LearningResource|Competition)` 做 `MERGE`，同一资源在 CSV 多 `stage` 会合并为一条边；详见 `check_neo4j_duplicates.py` 输出。

---

## `job_eval/` — 岗位能力评估

从 Neo4j 抽 `Job` 证据，调用 LLM 生成八维分数，可选写回图谱。配置与用法见 **`job_eval/README.md`**。

```bash
cd tools/job_eval
pip install -r requirements.txt
# 配置 .env 后
python run_job_eval_batch.py --dry-run
```

---

## `backend/tools/` — 后端与数据库

```bash
cd backend
python tools/run_migration_002.py
# … 003、004、005
python tools/analyze_neo4j_graph.py
```

部署文档若写 `python tools/run_migration_*.py`，请改为 **`python backend/tools/run_migration_*.py`**（或在 `backend/` 目录下执行）。

---

## 环境变量

| 作用域 | 文件 |
|--------|------|
| Neo4j 同步、`csv` 部分脚本 | `backend/.env` |
| 岗位评估 | `tools/job_eval/.env`（可复制 `.env.example`） |
