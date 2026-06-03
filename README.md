# PathFy-Uni

面向大学生的**职业规划智能体**：能力画像 → 岗位探索 → 人岗匹配 → 生涯报告 → 周期复盘。

> **本文档以当前仓库代码为准**（单一事实来源）。答辩材料、论文摘要中的 TransR / GNN 等表述属于**研究方向**；**已实现并运行的能力**见下文「技术栈」与「核心链路」。

---

## 文档索引

| 文档 | 用途 |
|------|------|
| **本文件 `README.md`** | 仓库概览、架构、目录结构、本地启动 |
| [`PathFy-Uni项目总体设计文档.md`](./PathFy-Uni项目总体设计文档.md) | 系统设计、模块分析、答辩/软著长文 |
| [`deploy/DEPLOY.md`](./deploy/DEPLOY.md) | 生产部署（Nginx + Gunicorn + 宝塔 ECS） |
| [`backend/README.md`](./backend/README.md) | 后端依赖、数据库初始化、API 入口 |
| [`frontend/README.md`](./frontend/README.md) | 前端开发、构建、环境变量 |
| [`generate_graph/README.md`](./generate_graph/README.md) | 招聘数据 → Neo4j 岗位图谱 ETL |
| [`datasets/README.md`](./datasets/README.md) | 数据集规范、禁止提交的隐私文件 |
| [`docs/REFACTOR_ROADMAP.md`](./docs/REFACTOR_ROADMAP.md) | 后端分层架构说明 |
| [`docs/smoke-test.md`](./docs/smoke-test.md) | 发布或合并前手动冒烟清单 |
| [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) | API 双包络响应契约 |
| [`docs/auth-audit.md`](./docs/auth-audit.md) | 接口鉴权审计清单 |
| [`docs/privacy-security.md`](./docs/privacy-security.md) | 隐私与安全加固变更说明 |
| [`paper-brief/`](./paper-brief/) | 论文/研究背景材料（非运行依赖） |

---

## 技术栈（当前实现）

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | **Astro 5 + Svelte 5 + Tailwind** | 多页工作台，`/api` 开发期 Vite 代理 |
| 后端 | **Flask + Gunicorn** | `domains/` 业务域 + `infrastructure/` 跨域能力 |
| 结构化数据 | **MySQL 8** | 用户、简历画像、匹配快照、生涯报告 |
| 岗位图谱 | **Neo4j** | 岗位检索、能力维度、晋升关系 |
| 简历解析 | **百度 OCR** + 规则评分 | 上传 → OCR → 八维能力分（`domains/profile/`、`utils.py`） |
| 人岗匹配 | **Pearson 形态相关 + 软 surplus 粗排** | 可选 **DeepSeek** 对 Top 候选精排与解释（`domains/match/`） |
| 岗位助手 | **豆包 / Ark** + Cypher 兜底 | 自然语言筛岗（`domains/jobs/assistant.py`） |
| 生涯报告 | **DeepSeek / 通义 / 豆包** 多模型编排 | 计划生成、复盘指标、可选自动重规划（`domains/report/`） |

**未在本仓库主链路中落地**：Vue 前端、TransR/Hetero-GNN/IKGCN 训练与推理、校内资源知识图谱、导师端独立后台。上述内容若出现在早期立项或论文中，请以本表为准区分「已实现 / 规划中」。

---

## 核心产品链路

```
登录 → 上传简历（八维能力画像）→ 性格测试（MBTI）
     → 岗位探索 / 岗位助手 → 人岗匹配
     → 导入目标岗位 → 生成生涯报告 → 周期复盘 → 自动重规划
```

| 环节 | 前端路由 | 后端 API（主要） |
|------|----------|------------------|
| 认证 | `/login`、`/register` | `POST /api/auth/*`、`GET /api/auth/me` |
| 能力画像 | `/profile` | `POST /api/profile/upload`、`GET /api/profile/resumes` |
| 性格测试 | `/personality` | `GET/POST /api/personality/*` |
| 岗位探索 | `/jobs` | `GET /api/jobs`、`GET /api/jobs/<id>` |
| 岗位助手 | `/jobs`（对话） | `POST /api/jobs/assistant/chat` |
| 职业图谱 | `/graph` | `POST /api/jobs/transition-analysis` 等 |
| 人岗匹配 | `/match` | `POST /api/match/preview` |
| 生涯报告 | `/report` | `POST /api/report/generate`、`POST /api/report/review-cycle` |
| 个人中心 | `/account` | `GET /api/auth/me` |

能力框架为**八维**（理论、交叉、实践、数字、创新、协作、社会、成长），与岗位图谱中的 `cap_req_*` 维度对齐。

---

## 架构概览

### 后端（`backend/app/`）

```
core/              配置、JWT 安全、统一错误处理
db/                MySQL 连接与事务
infrastructure/    Neo4j、LLM、OCR、薪资解析
domains/           auth · profile · personality · jobs · match · report
schemas/           响应契约 TypedDict
utils.py           简历评分、雷达图（待迁入 profile 域）
```

各业务域以 Flask Blueprint 注册路由；域间通过 services 或 infrastructure 协作，避免 router 互相引用。详见 [`docs/REFACTOR_ROADMAP.md`](./docs/REFACTOR_ROADMAP.md)。

### 前端（`frontend/src/`）

```
pages/             Astro 路由（profile、jobs、match、report…）
components/        Svelte 业务组件
lib/
├── api/           HTTP 与各域 API（auth、jobs、match、report…）
├── features/      非 HTTP 逻辑（如 auth/session）
├── radar-geometry.ts、profile-portrait-ui.ts 等 UI 辅助
└── personality-test-cache.ts 等页面级缓存
```

组件 import 约定：

- API 调用 → `@/lib/api/<domain>`（如 `@/lib/api/jobs`）
- 登录态 → `@/lib/features/auth/session`（`getToken`、`saveAuth` 等）
- 登录 API → `@/lib/api/auth`（`login`、`register`、`fetchMe`）

---

## 仓库结构

```
suilli_mizi/
├── frontend/
│   └── src/
│       ├── pages/           # 路由页面
│       ├── components/      # Svelte 组件
│       └── lib/
│           ├── api/         # 按域 API 封装
│           └── features/    # session 等客户端逻辑
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── db/
│   │   ├── domains/
│   │   ├── infrastructure/
│   │   ├── schemas/
│   │   └── utils.py
│   ├── migrations/
│   ├── schema.sql
│   ├── tests/               # pytest（无需 MySQL/Neo4j）
│   └── tools/                 # 数据库迁移脚本 run_migration_*.py
├── docs/
├── generate_graph/
├── deploy/
├── datasets/
└── tools/job_eval/
```

---

## 本地开发

### 前置条件

- Python 3.11+、Node.js 18+、pnpm
- MySQL（执行 `backend/schema.sql` 及 `migrations/002`–`005`）
- Neo4j（需先跑 `generate_graph/` 导入岗位，或使用已有图库）
- 复制 `backend/.env.example` → `backend/.env`，填写数据库与 API Key

### 启动

```bash
# 终端 1：后端
cd backend
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python run.py                   # http://127.0.0.1:5000

# 终端 2：前端
cd frontend
pnpm install
pnpm dev                        # http://localhost:4321，/api 代理到 Flask
```

健康检查：`GET http://127.0.0.1:5000/api/health`

### 测试与构建

```bash
# 后端单元测试（无需外部服务）
cd backend
pip install -r requirements-dev.txt
pytest tests/ -q

# 前端静态构建
cd frontend
pnpm build
```

发布或合并前可按 [`docs/smoke-test.md`](./docs/smoke-test.md) 做端到端冒烟。CI 见 [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)（backend pytest + frontend build）。

---

## 生产部署

见 [`deploy/DEPLOY.md`](./deploy/DEPLOY.md)。典型拓扑：

- Nginx：静态托管 `frontend/dist`，`/api` 反代 Gunicorn
- Supervisor：守护 Flask 进程
- MySQL + Neo4j 同机或内网可达
- 简历 OCR 临时目录：`RESUME_UPLOAD_DIR`（默认 `backend/private_uploads/resumes`，生产建议 `/var/private/pathfy/resumes`，OCR 后自动删除）

---

## 数据与隐私

- **勿提交**：MySQL 全库 dump（含用户/简历）、`.env`、SSH 私钥 — 见 [`.gitignore`](./.gitignore) 与 [`datasets/README.md`](./datasets/README.md)
- **初始化库表**：只用 `backend/schema.sql` + migrations，不要用含真实用户的 Navicat 导出灌库
- **简历文件**：上传至 Web 不可访问的私有目录，OCR 入库后删除原文件

---

## 研究与答辩说明

- **工程实现**：本 README 与 [`PathFy-Uni项目总体设计文档.md`](./PathFy-Uni项目总体设计文档.md) 描述的是**当前可运行系统**；总体设计文档中部分旧路径（如根级 `auth.py`、`src/lib/auth.ts`）以本 README 为准。
- **研究叙事**：立项/论文中「知识图谱嵌入、动态 GNN 画像、学习排序」等可作为**方法展望或后续版本**；答辩时建议明确：**V1 采用 Neo4j 图谱检索 + 可解释规则/统计匹配 + 多模型 LLM 增强**，而非端到端深度学习推荐。
- **创新点（与代码一致）**：八维能力—岗位需求—发展规划三位一体；匹配可解释（维度差距 + 可选 LLM 说明）；报告支持复盘闭环与自动重规划。

---

## 许可证与协作

内部课程/竞赛项目。协作时请优先更新**本 README** 与 [`docs/REFACTOR_ROADMAP.md`](./docs/REFACTOR_ROADMAP.md)，避免根目录再出现与代码不一致的技术描述。
