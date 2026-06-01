# PathFy-Uni 冒烟测试清单

发布或合并前在本地执行以下步骤。

**前置：** 后端 `python run.py`（5000）、前端 `pnpm dev`（4321），MySQL / Neo4j 可用。

| # | 步骤 | 预期 |
|---|------|------|
| 1 | `GET http://127.0.0.1:5000/api/health` | `{"ok": true, ...}` |
| 2 | 注册或登录，取得 Token | 跳转或本地存 Token |
| 3 | `GET /api/auth/me`（带 Bearer） | 返回当前用户 |
| 4 | `/profile` 上传简历 | 返回八维分数与 resume_id |
| 5 | `/personality` 完成测试 | 返回 MBTI 结果 |
| 6 | `/jobs` 列表与详情 | 岗位卡片可打开 |
| 7 | `/match` 人岗匹配 | 返回排序岗位列表 |
| 8 | `/report` 生成报告或复盘 | 无 500；报告可查看 |

**自动化：** `cd backend && pytest tests/ -q`

**记录：** 日期、执行人、失败步骤（如有）。
