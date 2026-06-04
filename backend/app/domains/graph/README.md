# Graph 域 — 图谱 ETL 与岗位数据管理

从招聘 Excel 数据构建职业发展知识图谱，支持增量更新、质检报告和岗位名称统计。

## 目录

1. [架构概览](#架构概览)
2. [数据模型](#数据模型)
3. [API 端点](#api-端点)
4. [配置项](#配置项)
5. [ETL 流程详解](#etl-流程详解)
6. [增量更新机制](#增量更新机制)
7. [质检报告](#质检报告)
8. [job_titles 表维护](#job_titles-表维护)
9. [使用示例](#使用示例)

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

**关系类型（3 种）：**

| 关系 | 方向 | 属性 |
|------|------|------|
| `BELONGS_TO` | `(:Job) → (:Company)` / `(:Job) → (:CareerLevel)` | 无 |
| `REQUIRES` | `(:Job) → (:Skill)` / `(:Job) → (:Certificate)` / `(:Job) → (:SoftSkill)` | 无 |
| `VERTICAL_UP` | `(:Job) → (:Job)` | `source`、`reason`、`company`、`confidence`、`updated_at` |

**与后端业务域的共存关系：**

后端的 `cap_req_*`（八维能力分）和 `cap_conf_*`（置信度）属性由其他域（jobs/match）写入，与 graph 域的 `hard_skills`/`is_core_template` 等属性共存于同一 `:Job` 节点。查询时通过 `coalesce()` 兼容。`PROMOTION_EDGE_SOURCES = ["openai_lmstudio"]` 在 `infrastructure/neo4j.py` 中引用。

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

### `POST /api/graph/generate-promotions` — 晋升边生成

通过 LLM 推断同公司内部的晋升路径（VERTICAL_UP 关系）。

**请求（JSON）：**
```json
{
  "dry_run": false,
  "min_confidence": 0.55,
  "min_company_jobs": 2,
  "clear_existing": false
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dry_run` | bool | false | true 时只预览，不写库 |
| `min_confidence` | float | 0.55 | 最低置信度阈值（0~1） |
| `min_company_jobs` | int | 2 | 每公司最少岗位数，低于此值跳过 |
| `clear_existing` | bool | false | 是否先删除已有 source=openai_lmstudio 的边 |

**dry_run 响应：**
```json
{
  "ok": true,
  "data": {
    "checked_companies": 24,
    "candidate_edges": 128,
    "preview": [
      {"company": "博岳通信", "from_title": "Java开发", "to_title": "高级Java", "confidence": 0.78, "reason": "经验年限递进"}
    ],
    "backup_file": "promotion_backups/promotion_edges_backup_20260604_200000.json",
    "dry_run": true
  }
}
```

**正式执行响应：**`dry_run: false`，额外包含 `created_edges` 字段。

### `POST /api/graph/clear` — 清空图谱

**请求：**`{"confirmed": true}`（必须显式确认）

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

### 晋升边生成（generate-promotions）

```
Neo4j :Job 节点
  │
  ├─ 1. fetch_all_jobs()：查询所有 Job（排除 source='inferred'）
  ├─ 2. 按 company 分组到 defaultdict(list)
  │
  ├─ 3. 逐公司（按岗位数降序）：
  │     ├─ dedupe_titles()：同标题保留 career_score 最高的
  │     ├─ 按 career_score 升序排列
  │     ├─ build_company_prompt()：构造 Prompt
  │     ├─ 调用 LLM（OpenAI 兼容，temperature=0.1）
  │     │     推断：from_title → to_title + reason + confidence
  │     └─ build_edges_with_validation()：
  │           ├─ 过滤 confidence < min_confidence
  │           ├─ 过滤未找到源/目标岗位
  │           ├─ 过滤自环
  │           ├─ 过滤逆方向（dst.career_score <= src.career_score）
  │           └─ 去重（pair_key）
  │
  ├─ 4. 备份：所有候选边写入 JSON（promotion_backups/ 目录）
  ├─ 5. dry_run=true → 返回预览，不写入
  └─ 6. dry_run=false → 可选 clear_existing → persist_promotion_edges()
```

**career_score 计算：**`(experience_years * 10.0) + calc_seniority_boost(title)`

职级关键词权重（SENIORITY_WEIGHTS）：
- 实习 -2.0、助理 -1.5、初级 -1.0
- 高级 +2.0、资深 +2.5、专家 +3.0
- 经理 +3.5、总监 +5.0、VP/Chief +6.0

**校验规则保证晋升边的方向性：**目标岗位的 career_score 必须严格大于源岗位。

---

## 增量更新机制

1. **岗位导入幂等性**：`MERGE` 使用 `job_key` 作为业务主键。同一 Excel 重复导入 → 更新属性，不创建重复节点。新数据追加 → 新 job_key 的节点被创建，已有 job_key 的节点属性被覆盖
2. **晋升边可选重建**：`clear_existing=true` 时先删除 `source="openai_lmstudio"` 的所有边再重新生成；默认不清除，已有边保持不变
3. **备份审计**：晋升边每次生成都备份为带时间戳的 JSON，即使 dry_run 模式也备份，可追溯每次变更

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

### 预览晋升边（不写入）

```bash
curl -X POST http://localhost:5000/api/graph/generate-promotions \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "min_confidence": 0.6}'
```

### 正式生成晋升边

```bash
curl -X POST http://localhost:5000/api/graph/generate-promotions \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false, "min_confidence": 0.55, "clear_existing": true}'
```

### 增量更新：导入新一期数据

```bash
# 不清空已有图谱，新数据以 MERGE 方式追加
curl -X POST http://localhost:5000/api/graph/import-jobs \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@datasets/20260701_new_jobs.xls"

# 重新生成晋升边（覆盖旧边）
curl -X POST http://localhost:5000/api/graph/generate-promotions \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"clear_existing": true}'
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

登录后访问 `/graph-admin/`，提供图形化界面：图谱统计卡片、文件上传导入、晋升边参数调节与预览。
