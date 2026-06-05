# Graph 域 — 图谱 ETL 与岗位数据管理

从招聘 Excel 数据构建职业发展知识图谱，支持增量更新、质检报告和岗位名称统计。

## 目录

1. [架构概览](#架构概览)
2. [核心原理](#核心原理)
3. [数据模型](#数据模型)
4. [API 端点](#api-端点)
5. [配置项](#配置项)
6. [ETL 流程详解](#etl-流程详解)
7. [增量更新机制](#增量更新机制)
8. [质检报告](#质检报告)
9. [job_titles 表维护](#job_titles-表维护)
10. [使用示例](#使用示例)

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                     domains/graph/                       │
│                                                          │
│  router.py         services.py        repository.py      │
│  (HTTP API)  ──→  (业务编排)  ──→  (Neo4j 查询)         │
│   4 端点            ETL 流程           Cypher MERGE       │
│   admin JWT         LLM 调用            官方 neo4j 驱动    │
│                     QC 报告                               │
│                     job_titles 同步    constants.py        │
│                                       (Prompt/权重/工具)   │
│                                                          │
│  外部依赖:                                                │
│  ├── infrastructure/neo4j.py  (driver、DIM_KEYS)          │
│  ├── infrastructure/llm.py    (OpenAI 客户端参考)          │
│  ├── infrastructure/privacy.py (LLM 外发脱敏)             │
│  └── core/security.py         (JWT 鉴权)                 │
└─────────────────────────────────────────────────────────┘
```

**设计原则：**

- Router 薄层，只做参数解析和认证，业务逻辑全在 services
- Repository 纯 Neo4j 交互，不依赖 Flask 上下文（接受 driver + database 参数）
- LLM 统一使用 OpenAI 兼容接口，通过配置切换 provider（豆包/DeepSeek/其他）
- 所有 LLM 外发数据穿透 `privacy.redact_payload()` 脱敏

---

## 核心原理

Graph 域的目标不是单纯把 Excel 搬进 Neo4j，而是把招聘文本变成可查询、可推断、可复用的职业知识图谱。它把“岗位记录”拆成岗位、公司、技能、证书、经验层级、岗位名称等实体，再用关系表达“岗位属于哪个公司”“岗位需要哪些能力”“岗位之间可能如何晋升或横向转岗”。

整体思路分三层：

1. **事实层**：来自 Excel 的岗位、公司、薪资、地区、岗位详情等字段，尽量保持原始证据可追溯。
2. **结构化层**：由规则和 LLM 从文本中抽取硬技能、证书、经验要求、实习要求、软技能倾向。
3. **推断层**：在已有节点基础上生成晋升边、横向转岗边、学习资源、竞赛推荐等“可解释建议”。

### 建图原则

Neo4j 中的节点和关系围绕“职业决策”建模，而不是围绕 Excel 表结构建模。

- `:Job` 是核心事实节点，使用 `job_key = normalize_title(title) + "::" + company.lower()` 作为业务主键。同一公司同一岗位名称会合并，重复导入只更新属性。
- `:Company`、`:Skill`、`:Certificate`、`:CareerLevel` 是可复用实体。多个岗位指向同一个技能或公司，方便后续统计、搜索和路径分析。
- `:JobTitle` 是岗位名称聚合节点，用于跨公司、跨记录推荐学习资源和竞赛。它不是 Excel 原始记录，而是从 `:Job.title` 聚合出来的职业概念层。
- 关系方向统一从岗位或资源指向其语义对象，例如 `(:Job)-[:REQUIRES]->(:Skill)`、`(:Job)-[:BELONGS_TO]->(:Company)`、`(:LearningResource)-[:FOR_JOB_TITLE]->(:JobTitle)`。
- 生成类结果必须落在职业概念层并带可解释属性。晋升推荐写入 `:JobPromotion`，记录 `from_title`、`to_title`、阶段说明、`confidence`、`rationale`，再通过 `FOR_JOB_TITLE` 挂到 `:JobTitle`。

这种设计让图谱既能回答“某个岗位需要什么”，也能回答“哪些岗位共享技能”“某个岗位名称有哪些学习资源”“某类岗位名称通常如何向上发展”。

### LLM 抽取原则

LLM 只负责处理规则难以稳定覆盖的自然语言字段，例如岗位详情、公司详情、经验要求和证书描述。代码侧仍负责输入裁剪、隐私脱敏、JSON 格式校验和失败兜底。

- 输入由 `build_ai_payload()` 生成，只包含当前批次的岗位摘要。
- 隐私模式开启时，`redact_payload()` 会脱敏联系人、邮箱、手机号、URL token 等敏感信息。
- 输出必须是 JSON object，核心字段是 `records` 数组；每条记录通过 `idx` 与批次内行号对应。
- LLM 失败不会让整个导入中断。单批最终失败时返回空结构，Neo4j 仍写入岗位事实字段，只是技能、证书等抽取字段为空或未知。
- LLM 结果不直接决定所有图结构。写库前仍会做类型检查、去空值、归一化和去重。

这套约束的核心是：LLM 提供语义增强，系统代码保留最终数据边界。

### 晋升路径推断原则

晋升路径不再写到具体 `:Job` 节点之间，而是统一在 `:JobTitle` 概念层查询和生成。旧的 `(:Job)-[:VERTICAL_UP {source:"openai_lmstudio"}]->(:Job)` 来源已废弃，不再作为前端管理或用户侧路径查询的数据来源。

- 第一步执行 `sync_job_titles()`：按 `:Job.title` 聚合创建 `:JobTitle`，并建立 `(:Job)-[:HAS_TITLE]->(:JobTitle)`。
- 第二步执行 `generate_promotion_paths()`：把岗位名称批量交给 LLM，要求输出 `from_title`、`to_title`、`promotion_name`、`stage1`、`stage2`、`stage3`、`confidence`、`rationale`。
- 正式执行时写入 `(:JobPromotion)-[:FOR_JOB_TITLE]->(:JobTitle)`。查询某个岗位的晋升路径时，先定位它的 `JobTitle`，再读取关联的 `JobPromotion`。
- `dry_run=true` 只返回候选路径预览，不写 Neo4j；`dry_run=false` 创建或更新 `JobPromotion` 节点。

这保证晋升推荐不会被单个公司、单条招聘记录或已废弃的 Job 层边污染；用户看到的是岗位名称层的通用职业发展路径。

### 数据一致性原则

Graph 域同时写 Neo4j 和 MySQL，它们职责不同：

- Neo4j 保存职业图谱主体，包括节点、关系、路径和资源推荐。
- MySQL `job_titles` 保存岗位名称的轻量统计，服务管理后台快速列表展示。
- `import-jobs` 先写 Neo4j，再同步 MySQL 统计；MySQL 同步失败会记录到 `errors`，但不会回滚已完成的 Neo4j 导入批次。
- 增量导入依赖 `MERGE` 幂等更新。除非显式 `clear_all=true`，导入不会清空图谱。
- 清图接口要求 `confirmed: true`，避免误触发 destructive 操作。

一致性目标是“管理侧可观察、导入可恢复、重复执行不制造重复节点”，不是跨库强事务。

### 管理权限原则

所有 Graph API 都通过 `_require_admin()` 校验 JWT 中的用户身份，并重新查询 MySQL `users.is_admin`。前端隐藏入口只是体验优化，不能替代后端权限控制。

---

## 数据模型

### Neo4j 图模型

`import-jobs` 从 Excel 创建以下节点和关系：

**节点标签（6 种）：**

| 标签 | 关键属性 | 说明 |
|------|---------|------|
| `:Job` | `job_key`（唯一）、`title`、`company`、`location`、`salary`、`industry`、`experience_years`、`hard_skills[]`、`soft_skills{}`、`is_core_template` | 岗位节点，与后端 `cap_req_*` 八维能力属性共存 |
| `:Company` | `name`（唯一） | 公司 |
| `:Skill` | `name`（唯一） | 硬技能（如 Python、Kubernetes） |
| `:Certificate` | `name`（唯一） | 证书（如 AWS SAA） |
| `:SoftSkill` | `name`（唯一）、`level` | 软技能四维度：innovation/learning/stress/comm |
| `:CareerLevel` | `name`（唯一） | 经验级别（如 1-3年、3-5年） |

**关系类型：**

| 关系 | 方向 | 属性 |
|------|------|------|
| `BELONGS_TO` | `(:Job) → (:Company)` / `(:Job) → (:CareerLevel)` | 无 |
| `REQUIRES` | `(:Job) → (:Skill)` / `(:Job) → (:Certificate)` / `(:Job) → (:SoftSkill)` | 无 |
| `HAS_TITLE` | `(:Job) → (:JobTitle)` | 无 |
| `FOR_JOB_TITLE` | `(:JobPromotion)` / `(:LearningResource)` / `(:Competition)` → `(:JobTitle)` | 由源节点承载解释属性 |
| `SIMILAR_FOR_LATERAL` | `(:JobTitle) → (:JobTitle)` | `reason`、`confidence`、`updated_at` |

旧的 `VERTICAL_UP` Job 层边只作为历史兼容存在，不再由管理页生成，也不再用于用户侧晋升路径查询。

**与后端业务域的共存关系：**

后端的 `cap_req_*`（八维能力分）和 `cap_conf_*`（置信度）属性由其他域（jobs/match）写入，与 graph 域的 `hard_skills`/`is_core_template` 等属性共存于同一 `:Job` 节点。查询时通过 `coalesce()` 兼容。晋升查询会先从 `:Job` 找到 `:JobTitle`，再读取 `:JobPromotion`。

### MySQL job_titles 表

每次 `import-jobs` 完成后自动同步：

```sql
CREATE TABLE job_titles (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title         VARCHAR(191) NOT NULL UNIQUE,   -- 岗位名称（如"前端工程师"）
  record_count  INT NOT NULL DEFAULT 0,          -- 该名称在 Excel 中出现的次数
  company_count INT NOT NULL DEFAULT 0,          -- 涉及公司数
  job_code_count INT NOT NULL DEFAULT 0,         -- 涉及岗位编码数
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

## API 端点

所有端点需要 **admin JWT 认证**（即 `users.is_admin = 1`）。未登录返回 401，非管理员返回 403。

### `GET /api/graph/stats` — 图谱统计

返回 Neo4j 中各节点标签和关系类型的计数。

**响应：**
```json
{
  "ok": true,
  "data": {
    "job_count": 457,
    "company_count": 128,
    "skill_count": 302,
    "certificate_count": 45,
    "softskill_count": 4,
    "careerlevel_count": 8,
    "belongs_to_count": 465,
    "requires_count": 1240,
    "vertical_up_count": 88
  }
}
```

### `POST /api/graph/import-jobs` — 岗位导入

从 Excel 导入招聘数据到 Neo4j。

**请求（multipart/form-data）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | .xls 或 .xlsx 文件，需包含 12 个指定中文列 |
| `batch_size` | int | 否 | 每批处理条数，默认 128 |
| `clear_all` | bool | 否 | 是否先清空图谱再导入，默认 false |

请求亦支持 JSON body 模式：`{"file_path": "/path/to/data.xls", "batch_size": 128, "clear_all": false}`

**响应：**
```json
{
  "ok": true,
  "data": {
    "total_jobs": 457,
    "batches_completed": 4,
    "batches_failed": 0,
    "core_templates": ["前端工程师", "Java开发", "数据分析师", ...],
    "errors": []
  }
}
```

### `POST /api/graph/generate-promotions` 已废弃

旧接口曾用于生成具体 `:Job` 节点之间的晋升边。该写入路径已废弃，调用时只返回 `410 Gone`，不会写 Neo4j。请改用 `POST /api/graph/sync/job-titles` 和 `POST /api/graph/generate/promotion-paths`。

**响应：**
```json
{
  "ok": false,
  "message": "generate-promotions 已废弃，不再写入 Job 层晋升边；请先调用 /api/graph/sync/job-titles，再调用 /api/graph/generate/promotion-paths 生成 JobTitle 层晋升路径。"
}
```

### `POST /api/graph/clear` — 清空图谱

**请求：**`{"confirmed": true}`（必须显式确认）

**响应：**
```json
{
  "ok": true,
  "message": "已清空图谱（删除 457 个节点）",
  "data": {"deleted_nodes": 457}
}
```

### `GET /api/graph/job-titles` — 岗位名称统计

返回 MySQL `job_titles` 表数据，按 `record_count` 降序排列。

**响应：**
```json
{
  "ok": true,
  "data": {
    "total": 156,
    "titles": [
      {"id": 1, "title": "前端工程师", "record_count": 35, "company_count": 12, "job_code_count": 8, "updated_at": "..."}
    ]
  }
}
```

### `POST /api/graph/sync/job-titles` — 同步 JobTitle 节点

从 Neo4j `:Job.title` 聚合生成 `:JobTitle` 节点，并建立 `(:Job)-[:HAS_TITLE]->(:JobTitle)` 关系。

**请求：**
```json
{"dry_run": true}
```

**响应：**
```json
{
  "ok": true,
  "data": {
    "dry_run": true,
    "title_count": 156,
    "sample": [{"name": "前端工程师", "count": 35}]
  }
}
```

正式执行时 `dry_run=false`，返回 `created_jobtitle_nodes` 和 `has_title_relationships`。

### `POST /api/graph/generate/promotion-paths` — 生成岗位名称晋升路径

基于 `:JobTitle` 列表，让 LLM 推断岗位名称之间的晋升路径，并写入 `:JobPromotion` 节点。用户侧查询也读取这一层：`Job -> HAS_TITLE -> JobTitle <- FOR_JOB_TITLE <- JobPromotion`。

**请求：**
```json
{"dry_run": true}
```

**响应字段：**

| 字段 | 说明 |
|------|------|
| `titles_scanned` | 输入 LLM 的岗位名称数量 |
| `candidate_paths` | LLM 返回的候选路径数 |
| `preview` | dry-run 模式下的前 20 条候选路径 |
| `created_promotions` | 正式执行时创建或更新的 `JobPromotion` 数量 |

### `POST /api/graph/generate/lateral-transfers` — 生成横向转岗关系

基于高频 `:JobTitle`，让 LLM 判断岗位名称之间的横向转岗可行性，并写入 `(:JobTitle)-[:SIMILAR_FOR_LATERAL]->(:JobTitle)`。

**请求：**
```json
{"dry_run": false}
```

**响应字段：**

| 字段 | 说明 |
|------|------|
| `titles_considered` | 参与配对的高频岗位名称数量 |
| `candidate_pairs` | LLM 返回的候选转岗关系数 |
| `preview` | dry-run 模式下的前 20 条候选关系 |
| `created_relationships` | 正式执行时写入的横向关系数量 |

### `POST /api/graph/generate/learning-resources` — 生成学习资源

为岗位记录数不少于 2 的高频 `:JobTitle` 推荐学习资源，并写入 `:LearningResource` 节点，通过 `FOR_JOB_TITLE` 关联到岗位名称。

**请求：**
```json
{"dry_run": true}
```

**响应字段：**

| 字段 | 说明 |
|------|------|
| `titles_processed` | 被处理的岗位名称数量 |
| `candidate_resources` | LLM 返回的资源数量 |
| `preview` | dry-run 模式下的资源摘要 |
| `created_resources` | 正式执行时写入的资源数量 |

### `POST /api/graph/generate/competitions` — 生成竞赛推荐

为高频 `:JobTitle` 推荐相关学科竞赛，并写入 `:Competition` 节点，通过 `FOR_JOB_TITLE` 关联到岗位名称。

**请求：**
```json
{"dry_run": true}
```

**响应字段：**

| 字段 | 说明 |
|------|------|
| `titles_processed` | 被处理的岗位名称数量 |
| `candidate_competitions` | LLM 返回的竞赛数量 |
| `preview` | dry-run 模式下的竞赛摘要 |
| `created_competitions` | 正式执行时写入的竞赛数量 |

### `POST /api/graph/qc-report` — 质检报告

从 `job_eval_results_*.jsonl` 文件生成质量分析报告。

**请求：**
```json
{
  "input_file": "job_eval_results_20260604.jsonl",
  "threshold": 0.60
}
```

`input_file` 留空则自动查找当前目录下最新的匹配文件。

**响应：**
```json
{
  "ok": true,
  "data": {
    "total": 457, "success": 450, "failed": 7,
    "success_rate": 98.47,
    "low_confidence_count": 23,
    "avg_scores": {"cap_req_theory": 62.5, ...},
    "distribution": {"cap_req_theory": {"0-39": 10, "40-59": 80, ...}, ...},
    "top_low_confidence": [{"job_id": "xxx", "min_conf_key": "cap_conf_digital", "min_conf_value": 0.12, ...}],
    "top_failures": [{"reason": "LLM timeout", "count": 5}],
    "report_path": "qc_report_20260604_200000.md",
    "csv_path": "low_confidence_20260604_200000.csv"
  }
}
```

---

## 配置项

所有配置在 `core/config.py` 中，通过环境变量设置（默认值兜底到 ARK/豆包）：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `GRAPH_LLM_BASE_URL` | `$ARK_BASE_URL` | LLM API 地址（OpenAI 兼容） |
| `GRAPH_LLM_API_KEY` | `$ARK_API_KEY` | LLM API Key |
| `GRAPH_LLM_MODEL` | `doubao-seed-2-0-mini-260215` | 模型名 |
| `GRAPH_BATCH_SIZE` | `128` | 每批处理条数 |
| `GRAPH_MAX_RETRIES` | `5` | LLM 调用最大重试次数 |
| `GRAPH_LLM_TIMEOUT_SECONDS` | `120` | 单次 LLM 请求超时秒数 |
| `GRAPH_PROMOTION_MIN_CONFIDENCE` | `0.55` | 晋升边默认置信度阈值 |
| `GRAPH_PROMOTION_BACKUP_DIR` | `promotion_backups` | 晋升边 JSON 备份目录 |

---

## ETL 流程详解

### 岗位导入（import-jobs）

```
Excel .xls
  │
  ├─ 1. pd.read_excel() 加载，校验 12 个中文列名
  ├─ 2. 列名映射（COLUMN_ALIASES）：岗位名称→name，公司名称→company...
  ├─ 3. compute_core_templates()：按归一化标题频率取 top 10
  │
  ├─ 4. 分批循环（batch_size=128）：
  │     ├─ build_ai_payload()：DataFrame → JSON 数组
  │     ├─ 调用 LLM（OpenAI 兼容，temperature=0.1，response_format=json_object）
  │     │     提取：hard_skills[], soft_skills{innovation/learning/stress/comm},
  │     │           certificates[], experience_req, internship_req
  │     ├─ 重试最多 5 次，指数退避（2s/4s/6s/8s/10s）
  │     └─ 最终失败 → 返回空结构兜底（不阻塞其他批次）
  │
  ├─ 5. merge_batch_to_neo4j()：单事务内 MERGE 所有节点+关系
  │     ├─ MERGE (:Job {job_key}) → 设置 title/company/location/salary...
  │     ├─ MERGE (:Company) → BELONGS_TO
  │     ├─ MERGE (:Skill) → REQUIRES（每个 hard_skill）
  │     ├─ MERGE (:Certificate) → REQUIRES
  │     ├─ MERGE (:SoftSkill) → REQUIRES（4 维软技能）
  │     └─ MERGE (:CareerLevel) → BELONGS_TO
  │
  ├─ 6. _sync_job_titles()：按岗位名称分组统计 → INSERT ON DUPLICATE KEY UPDATE
  └─ 返回统计
```

**job_key 计算：**`normalize_title(title) + "::" + company.lower()`
- `normalize_title`：去空白 + 小写（如 "Python 工程师" → "python工程师"）
- 同一公司同一标题的岗位会合并为一个 Job 节点

### JobTitle 晋升路径生成（generate/promotion-paths）

```
Neo4j :Job 节点
  │
  ├─ 1. sync_job_titles()
  │     ├─ 按 trim(j.title) 聚合岗位名称和出现次数
  │     ├─ MERGE (:JobTitle {name})，更新 job_count
  │     └─ MERGE (:Job)-[:HAS_TITLE]->(:JobTitle)
  │
  ├─ 2. generate_promotion_paths()
  │     ├─ fetch_all_job_titles()：读取 JobTitle 名称列表
  │     ├─ 每 30 个名称构造一个 LLM 请求
  │     ├─ LLM 输出 paths：
  │     │     from_title、to_title、promotion_name
  │     │     stage1、stage2、stage3、stage3_job_title
  │     │     confidence、rationale
  │     └─ dry_run=true → 返回 candidate_paths 与 preview，不写库
  │
  └─ 3. dry_run=false → MERGE (:JobPromotion {promotion_id})
        └─ MERGE (:JobPromotion)-[:FOR_JOB_TITLE]->(:JobTitle)
```

**查询路径：**用户侧 `/api/jobs/{job_id}/promotion-path` 先定位起始 `:Job`，通过 `HAS_TITLE` 或标题名称找到 `:JobTitle`，然后返回该标题关联的 `:JobPromotion`。返回结构继续包含 `paths` 和 `next_steps`，但边属性以 `confidence`、`rationale`、`stage1/2/3` 为主。

---

## 增量更新机制

1. **岗位导入幂等性**：`MERGE` 使用 `job_key` 作为业务主键。同一 Excel 重复导入 → 更新属性，不创建重复节点。新数据追加 → 新 job_key 的节点被创建，已有 job_key 的节点属性被覆盖
2. **JobTitle 同步幂等性**：`sync/job-titles` 通过 `MERGE (:JobTitle {name})` 和 `MERGE (:Job)-[:HAS_TITLE]->(:JobTitle)` 重复执行不会创建重复标题节点
3. **晋升路径更新幂等性**：`generate/promotion-paths` 通过 `promotion_id` 合并 `JobPromotion`，重复生成会更新阶段说明、置信度和 rationale

---

## 质检报告

`POST /api/graph/qc-report` 读取 `job_eval_results_*.jsonl`（每行一个 `{job_id, scores, confidence, evidence, risk_flags}` 或 `{job_id, error}`），生成：

- **Markdown 报告**（`qc_report_YYYYMMDD_HHMMSS.md`）：总体统计、八维平均分、分数分布表、低置信度 Top 30、失败原因 Top 20
- **低置信度 CSV**（`low_confidence_YYYYMMDD_HHMMSS.csv`）：供人工抽检或 Qwen 复核

JSONL 文件由外部评估工具（`tools/job_eval/run_job_eval_batch.py`）生成，质检报告作为评估结果的统计分析层。

---

## 使用示例

### 初次部署：导入全部岗位数据

```bash
# API 方式（推荐，通过前端图谱管理页面或 curl）
curl -X POST http://localhost:5000/api/graph/import-jobs \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@datasets/20260226105856_457.xls" \
  -F "batch_size=128"

# 或上传到服务器后指定路径
curl -X POST http://localhost:5000/api/graph/import-jobs \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/data/20260226105856_457.xls", "batch_size": 256}'
```

### 同步 JobTitle（不写入）

```bash
curl -X POST http://localhost:5000/api/graph/sync/job-titles \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

### 生成 JobTitle 晋升路径

```bash
# 先正式同步 JobTitle
curl -X POST http://localhost:5000/api/graph/sync/job-titles \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'

# 再预览或正式生成 JobPromotion
curl -X POST http://localhost:5000/api/graph/generate/promotion-paths \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

### 增量更新：导入新一期数据

```bash
# 不清空已有图谱，新数据以 MERGE 方式追加
curl -X POST http://localhost:5000/api/graph/import-jobs \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@datasets/20260701_new_jobs.xls"

# 刷新 JobTitle 和晋升路径
curl -X POST http://localhost:5000/api/graph/sync/job-titles \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

### Docker Compose 环境

```bash
# 本地开发 / 测试
docker compose up -d
# 创建管理员（首次）
docker compose exec mysql mysql -u root -p -e \
  "UPDATE suilli_mizi.users SET is_admin=1 WHERE id=1"
# 导入
docker compose exec backend curl -X POST http://localhost:5000/api/graph/stats \
  -H "Authorization: Bearer $(获取token)"
```

### 前端管理页面

登录后访问 `/graph-admin/`，提供图形化界面：图谱统计卡片、文件上传导入、JobTitle 同步与晋升路径生成。
