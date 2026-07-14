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
├── neo4j/                    # 知识图谱只读诊断
│   └── check_neo4j_duplicates.py
├── repository/               # 仓库卫生检查
│   └── check_repo_hygiene.py
└── job_eval/                 # 历史能力结果的本地只读质检
    ├── README.md
    └── make_qc_report.py
```

### 相关目录（不在 `tools/` 根下）

| 路径 | 用途 |
|------|------|
| `backend/tools/` | Alembic 基线校验、历史迁移工具、图谱分析 |
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

## `neo4j/` — 知识图谱只读诊断

`tools/neo4j/` 只保留重复项检查。岗位、学习资源、竞赛、晋升、换岗、推荐、能力评估、薪资回填和清理操作统一进入后端 MySQL 任务队列，在管理端审阅变更集后确认。

自动化场景使用 `cd backend && python -m app.domains.graph.cli enqueue ...`，该命令同样只入队。

---

## `job_eval/` — 岗位能力评估

这里只保留对历史 JSONL 生成本地报告的只读工具。评估和导入使用图谱管理后台。

```bash
python tools/job_eval/make_qc_report.py --input path/to/results.jsonl
```

---

## `backend/tools/` — 后端与数据库

```bash
cd backend
python tools/verify_alembic_baseline.py
alembic stamp 20260712_0001  # 仅首次接入
alembic upgrade head
python tools/analyze_neo4j_graph.py
```

`run_migration_00x.py` 与根级历史 SQL 只供旧环境审计，新的数据库变更必须创建 `backend/migrations/versions/` 下的 Alembic revision。

---

## 环境变量

| 作用域 | 文件 |
|--------|------|
| Neo4j 同步、`csv` 部分脚本 | `backend/.env` |
| 图谱任务与岗位评估 | `backend/.env` |
