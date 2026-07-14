# PathFy-Uni · Flask 后端

> 项目总览与文档索引见仓库根目录 [`README.md`](../README.md)。

## 模块一览

| 目录 | 路由前缀 | 职责 |
|------|----------|------|
| `domains/auth/` | `/api/auth` | 注册、登录、JWT |
| `domains/profile/` | `/api/profile` | 简历上传、OCR、八维画像 |
| `domains/personality/` | `/api/personality` | MBTI 题库与结果 |
| `domains/jobs/` | `/api/jobs` | Neo4j 岗位列表/详情 |
| `domains/jobs/assistant.py` | `/api/jobs/assistant` | 自然语言筛岗对话 |
| `domains/match/` | `/api/match` | 人岗匹配粗排 + 可选 LLM 精排 |
| `domains/report/` | `/api/report` | 生涯报告、复盘、PDF 导出 |
| `core/` | — | 配置、安全、统一错误 |
| `infrastructure/` | — | Neo4j、LLM、OCR、薪资解析 |
| `db/` | — | MySQL 连接 |

## 1) 安装依赖

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2) 初始化数据库

新数据库先导入当前完整 schema，再登记 Alembic 基线：

```bash
alembic upgrade head
```

新数据库只需运行 `alembic upgrade head`，迁移会自动发布系统设置 revision 1。已有数据库先运行 `python tools/verify_alembic_baseline.py`，通过后执行 `alembic stamp 20260712_0001`。此后部署只运行 `alembic upgrade head`。历史 `002_*.sql`–`007_*.sql` 和 `run_migration_00x.py` 仅供审计，不再作为迁移入口；详见 [`migrations/README.md`](migrations/README.md)。

## 3) 配置环境变量

复制 `.env.example` 为 `.env`，至少确认：

- `MYSQL_*` — MySQL 连接
- `NEO4J_*` — 岗位图谱（需先导入数据，见 `generate_graph/`）
- `FRONTEND_ORIGIN` — CORS 允许的前端地址
- `OCR_*` / `DASHSCOPE_API_KEY` — 简历 OCR（按需）
- `DEEPSEEK_API_KEY`、`ARK_API_KEY` — 匹配精排、岗位助手、报告（按需）

可选：`RESUME_UPLOAD_DIR` — 简历 OCR 临时目录（OCR 后自动删除）。

## 4) 启动服务

```bash
python run.py

# 另开终端启动图谱更新队列
python -m app.domains.graph.worker

# 查看当前生效的非敏感配置及 revision
python -m app.domains.settings.cli show-effective
```

默认地址：`http://127.0.0.1:5000`

## 4.1) 自动化测试

无需 MySQL/Neo4j，覆盖健康检查、JWT、infrastructure 纯函数与粗排逻辑：

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

虚拟环境包含创建时解释器的绝对路径。Python 安装位置改变后请删除并重建 `.venv`，不要复制或提交虚拟环境。重构前后可用以下命令比较完整路由清单：

```bash
PYTHONPATH=. python tools/list_routes.py
```

生产环境见 [`deploy/DEPLOY.md`](../deploy/DEPLOY.md)（Gunicorn + 独立 graph worker + Supervisor）。图谱管理员在 `/graph-admin` 创建更新任务，必须审查确认后才写入 Neo4j。

## 5) 常用 API

- `POST /api/auth/register` — `{ "username", "email", "password" }`
- `POST /api/auth/login` — `{ "account", "password" }`
- `GET /api/auth/me` — Header: `Authorization: Bearer <token>`
- `GET /api/health` — 健康检查
- `POST /api/profile/upload` — 表单：简历文件 + `name` + `major`（需登录）
- `POST /api/match/preview` — 人岗匹配（需登录）
- `POST /api/report/generate` — 生成生涯报告（需登录）

完整接口说明见 [`PathFy-Uni项目总体设计文档.md`](../docs/project/PathFy-Uni项目总体设计文档.md) 附录 A。
