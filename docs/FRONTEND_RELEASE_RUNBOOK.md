# PathFy-Uni 前端发布与回滚手册

更新日期：2026-08-19  
适用里程碑：`frontend-r4-experience`（Iteration 5～7）及生涯报告 Phase 0～4

## 1. 发布准入

发布候选必须满足以下条件：

- `frontend-type-unit`、`frontend-build-budget`、`frontend-e2e`、`backend-test` 全部通过；
- 当天或最近一次 `integration-nightly` 已通过；
- `python backend/tools/check_runtime_schema.py` 未报告阻断问题；
- 预发布环境完成 `docs/smoke-test.md` 的 P0 链路；
- 已记录 Git SHA、数据库迁移版本、构建时间和执行人；
- `frontend.old` 未被修改、构建或复制到发布目录。

本地等价命令：

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm generate
pnpm bundle:check
pnpm experiment:ssr
pnpm experiment:ssr:test
pnpm test:e2e
pnpm test:integration

cd ..\backend
python -m pytest tests/ -q
python tools/check_runtime_schema.py
```

## 2. 版本化产物与原子切换

生产机约定：

```text
/www/wwwroot/pathfy-uni/
├─ releases/frontend/<release-id>/
├─ frontend-current -> releases/frontend/<release-id>/
└─ frontend-previous -> releases/frontend/<previous-id>/
```

`release-id` 推荐使用 `YYYYMMDD-HHMM-<short-sha>`。构建完成后把 `.output/public` 的内容复制到全新的版本目录，先验证目录包含 `200.html`、`index.html` 和 `_nuxt/`，再更新软链接。不要在 Nginx 当前读取的目录中原地覆盖文件。

切换顺序：

1. 将当前 `frontend-current` 的真实目标记录为上一版本；
2. 创建新版本目录并写入完整构建产物；
3. 用临时软链接指向新版本；
4. 原子重命名临时链接为 `frontend-current`；
5. 执行 `nginx -t`，成功后 reload；
6. 将旧目标写入 `frontend-previous`；
7. 完成线上冒烟后再宣布发布成功。

## 3. 上线后五分钟检查

- `/api/health` 返回成功并带安全响应头；
- 首页、登录、画像、岗位、匹配、报告静态资源无 404；
- 注册或登录后认证状态可恢复；
- 画像列表、匹配历史、报告历史能读取；
- 生涯报告规则版可在 AI 增强期间使用，四工作区可以切换；
- 使用测试报告完成行动勾选、复盘事实确认和计划提案决定；
- 个人 JSON 与 PDF 可以导出；永久删除只在专用测试报告上验证；
- schema doctor 显示报告 7 条级联外键、6 个关键索引和 Alembic `20260819_0008` 均正常；
- 浏览器控制台无 CSP 阻断核心脚本、样式和 API；
- Nginx、Gunicorn 日志无持续 4xx/5xx 峰值；
- 桌面端和移动端各完成一次关键链路。

## 4. 回滚判定与操作

出现以下任一情况应立即回滚：核心页面白屏、认证普遍失败、静态资源批量 404、API 契约导致核心链路中断、CSP 阻断应用启动，或错误率持续超过发布前基线。

回滚只切换静态产物：

1. 确认 `frontend-previous` 指向已验证的上一版 Nuxt 产物；
2. 原子切换 `frontend-current` 到该目标；
3. `nginx -t` 后 reload；
4. 重跑 `/api/health`、首页、登录、画像、匹配和报告；
5. 记录回滚时间、触发指标和失败版本；
6. 保留失败产物和日志用于复盘，不立即删除。

禁止将 `frontend.old` 作为回滚目标。数据库迁移必须向前兼容上一版前端，本地缓存的新格式必须保留旧读取路径至少两个发布版本。

## 5. 产物保留

- 至少保留当前版、上一版和最近一个稳定版；
- 建议保留 14 天，清理前确认目录不是 `frontend-current` 或 `frontend-previous` 的真实目标；
- 删除历史产物属于生产维护操作，应先解析并核对绝对路径，不使用宽泛通配符；
- 发布记录和 bundle report 至少保留一个迭代周期。

## 6. JWT 与后续安全专项

当前 Bearer JWT 仍保存在 `localStorage`，前端已经限制缓存清理范围并避免在工作区持久化敏感材料，但这不能消除 XSS 读取 Token 的风险。迁移 HttpOnly、Secure、SameSite Cookie 需要后端登录/注销、CSRF、防跨域配置和前端请求策略协同修改，作为独立跨端事项推进，不能只改前端存储位置。
