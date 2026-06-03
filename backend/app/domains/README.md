# domains 业务域

| 域 | 路径 | 说明 |
|----|------|------|
| **auth** | `auth/router.py` | 注册、登录、me |
| **jobs** | `jobs/router.py`、`jobs/assistant.py` | 岗位探索与 AI 助手 |
| **match** | `match/router.py`、`services.py`、`llm_refine.py`、`snapshots.py` | 人岗匹配 |
| **profile** | `profile/router.py` | 简历上传与能力画像 |
| **personality** | `personality/router.py`、`services.py`、`data/mbti_static.json` | MBTI 测评 |
| **report** | `report/router.py`、`services.py` + 子模块 | 生涯报告 |

典型结构：

```
domains/<name>/
├── router.py      # Flask Blueprint + 路由（薄）
└── services.py    # 业务编排（可选）
```

**report 域**（较复杂，平铺子模块，无子文件夹）：

```
domains/report/
├── router.py       # HTTP 入口
├── services.py     # 生成报告、导入目标、复盘编排
├── repository.py   # MySQL + Neo4j 查询
├── export.py       # PDF / HTML 导出
├── utils.py        # 小工具（truthy、json_dumps 等）
├── growth.py       # 成长计划与发展线
├── trends.py       # 趋势分析
├── review.py       # 周期复盘与重规划
├── llm.py          # 报告文案 LLM
├── targets.py      # 目标岗位粗排
├── constants.py
└── helpers.py      # 兼容转发（新代码请用 utils / export）
```

`create_app()` 从 `domains.*.router`（及 `jobs.assistant`）注册 Blueprint。
