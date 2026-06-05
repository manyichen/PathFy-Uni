# domains 业务域

各域按 **Flask Blueprint** 划分；`create_app()` 从 `domains.*.router`（及 `jobs.assistant`）注册路由。

## 域一览

| 域 | 路径 | API 前缀 | 说明 |
|----|------|----------|------|
| **auth** | `auth/router.py` | `/api/auth` | 注册、登录、JWT、`me` |
| **profile** | `profile/router.py` | `/api/profile` | 简历上传、OCR、八维能力画像 |
| **personality** | `personality/router.py`、`services.py`、`data/mbti_static.json` | `/api/personality` | MBTI 测评 |
| **jobs** | `jobs/router.py`、`jobs/assistant.py` | `/api/jobs`、`/api/jobs/assistant` | Neo4j 岗位探索、AI 筛岗对话 |
| **match** | `match/router.py`、`services.py`、`llm_refine.py`、`snapshots.py` | `/api/match` | 人岗匹配粗排 + 可选 LLM 精排 |
| **report** | 见下文 | `/api/report` | 生涯报告生成、复盘、PDF 导出 |

## 典型结构（轻量域）

```
domains/<name>/
├── router.py      # HTTP：鉴权、参数、jsonify（薄）
└── services.py    # 业务编排（可选）
```

跨域调用示例：`report.services` 使用 `match.services` / `match.snapshots` 导入目标岗位。

---

## report 域（平铺模块，无子文件夹）

生涯报告是项目内最大的业务域之一（约 17 个模块、~3600 行）。**刻意保持平铺**：文件名即模块边界，入口固定为 `router.py` → `services.py`，不按子目录拆分，避免网状依赖下的循环导入与路径膨胀。

### 调用关系（简图）

```
router.py
    └── services.py          # 编排：生成 / 列表 / 复盘 / 目标 / 导出
            ├── repository.py          # MySQL 报告表 + Neo4j 岗位批量查询
            ├── graph_repository.py    # JobTitle → 学习资源 / 竞赛
            ├── targets.py             # 目标岗位检索（复用 match 粗排）
            ├── trends.py              # 赛道画像（招聘 CSV + 图谱）
            ├── external_public_info.py # 按需联网公开信息（用户点击）
            ├── growth.py              # 成长计划、发展线、时间轴
            ├── plans_by_target.py     # 分目标分阶段计划
            ├── recommendations.py     # 图谱推荐 + LLM 精选
            ├── review.py              # 周期复盘、指标、自动调计划
            ├── llm.py                 # 报告摘要 / 叙事 LLM
            ├── export.py              # HTML / Playwright PDF
            ├── sanitize.py            # 复盘文本脱敏
            ├── constants.py           # 维度标签、模板文案
            └── utils.py               # truthy、clamp_int、json_dumps 等
```

### 文件说明

| 文件 | 职责 |
|------|------|
| `router.py` | Blueprint `/api/report`：目标导入、生成、详情、列表、复盘、PDF |
| `services.py` | 对外业务 API；`ReportServiceError`；串联各子模块 |
| `repository.py` | 报告/复盘 CRUD；岗位 ID 查询；Neo4j 关系批量拉取 |
| `graph_repository.py` | 按 `JobTitle` 查 `LearningResource` / `Competition` |
| `targets.py` | 手动搜索 / 粗排目标岗位 |
| `trends.py` | 赛道画像：招聘可见度 / 路径宽度 / 资源密度（分位数） |
| `external_public_info.py` | 用户点击后检索公开信息，JobTitle 缓存，摘要≤300 字 |
| `growth.py` | 八维缺口、成长计划、发展线、复盘后时间轴重建 |
| `plans_by_target.py` | 每目标短中长期条目、叙事片段、`plan_line_id` |
| `recommendations.py` | 规则先出 + **batch** DeepSeek 策展（1 次/报告）；`use_llm_curator` 可关 |
| `review.py` | 复盘指标评估、LLM 抽数、自动重规划 |
| `llm.py` | OpenAI 兼容调用；报告摘要；分目标叙事增强 |
| `export.py` | `build_report_export_html`、`render_pdf_with_playwright` |
| `sanitize.py` | 递归清洗 `review_text` 等敏感字段 |
| `constants.py` | `DIM_LABELS`、`SHORT_TERM_ACTIONS` 等 |
| `utils.py` | 无业务语义的小工具函数 |
| `gap_analysis.py` | 能力缺口：仅相对目标 JD、复盘基线、`dimension_raw_delta` 展示用 |

### 导入约定

- **仅从模块公共名导入**，例如：
  - `from app.domains.report.utils import truthy, clamp_int, json_dumps`
  - `from app.domains.report.export import build_report_export_html`
- **不要**使用已移除的 `helpers.py` 或 `_truthy` / `_json_dumps` 等旧别名。
- 域内私有逻辑用模块内 `_prefixed` 函数即可，勿在 `utils` / `export` 再导出一套别名。

### 测试

| 测试文件 | 覆盖 |
|----------|------|
| `backend/tests/test_report_export.py` | `export.build_report_export_html` |
| `backend/tests/test_plans_by_target.py` | `plans_by_target.build_plans_by_target` |
| `backend/tests/test_report_recommendations.py` | `recommendations` 规则与排序 |

### 何时考虑子文件夹

仅在同时满足多条时再拆（如 `persistence/`、`pipeline/`、`review/`）：代码量显著增大、出现第二个 Blueprint、或子域依赖可改为单向。当前规模下平铺更易维护。
