# PathFy-Uni 后端架构

后端采用 **domains + infrastructure + core/db** 分层；前端为 **Astro + Svelte 多页**。API URL 与响应字段保持稳定。

相关文档：[`smoke-test.md`](./smoke-test.md)、[`API_CONTRACT.md`](./API_CONTRACT.md)、[`auth-audit.md`](./auth-audit.md)、[`privacy-security.md`](./privacy-security.md)。

---

## 目录结构

```
backend/app/
├── __init__.py              # create_app，注册 Blueprint
├── core/
│   ├── config.py            # 环境变量与 Config
│   ├── security.py          # JWT 鉴权
│   └── errors.py            # ApiError 与全局 handler
├── db/
│   └── session.py           # db_cursor, get_connection
├── infrastructure/
│   ├── neo4j.py
│   ├── llm.py
│   ├── salary.py
│   └── ocr.py
├── domains/
│   ├── auth/
│   ├── profile/
│   ├── personality/
│   ├── jobs/
│   ├── match/
│   └── report/
├── schemas/                 # 响应契约 TypedDict
└── utils.py                 # 简历评分、雷达图
```

---

## 分层职责

| 层 | 职责 |
|----|------|
| **domains/** | 业务 Blueprint、路由与服务 |
| **infrastructure/** | Neo4j、LLM、OCR、薪资解析等跨域能力 |
| **core/** | 配置、安全、统一错误 |
| **db/** | MySQL 连接与事务 |

domains 之间通过 services 或 infrastructure 协作，避免 router 互相引用。

---

## 前端 API 层

```
frontend/src/lib/
├── api/           # HTTP 与按域 API（auth、jobs、match…）
└── features/      # 会话等非 HTTP 逻辑（如 auth/session）
```

## report 域（示例）

```
domains/report/
├── router.py      # 薄路由
├── services.py    # 业务编排
├── repository.py  # 持久化与 Neo4j
├── export.py      # PDF 导出
├── utils.py       # 通用小工具
└── growth / trends / review / llm / targets …
```

---

## 质量保障

- 手动冒烟：见 [`smoke-test.md`](./smoke-test.md)
- 自动化：`cd backend && pytest tests/ -q`
- CI：`.github/workflows/ci.yml`（backend pytest + frontend build）
