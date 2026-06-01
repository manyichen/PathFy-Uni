# domains 业务域

| 域 | 路径 | 说明 |
|----|------|------|
| **auth** | `auth/router.py` | 注册、登录、me |
| **jobs** | `jobs/router.py`、`jobs/assistant.py` | 岗位探索与 AI 助手 |
| **match** | `match/router.py`、`services.py`、`llm_refine.py`、`snapshots.py` | 人岗匹配 |
| **profile** | `profile/router.py` | 简历上传与能力画像 |
| **personality** | `personality/router.py`、`services.py`、`data/mbti_static.json` | MBTI 测评 |
| **report** | `report/router.py` + 子模块 | 生涯报告 |

典型结构：

```
domains/<name>/
├── router.py      # Flask Blueprint + 路由
└── services.py    # 业务逻辑（可选）
```

`create_app()` 从 `domains.*.router`（及 `jobs.assistant`）注册 Blueprint。
