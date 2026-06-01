# 鉴权审计清单

Bearer JWT：`Authorization: Bearer <token>`，由 `app.core.security.get_bearer_user_id()` 解析。

与 `domains/*/router.py` 路由定义同步维护。

---

## 公开（无需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/jobs` | 岗位列表 |
| GET | `/api/jobs/options` | 岗位轻量选项 |
| GET | `/api/jobs/<job_id>` | 岗位详情 |
| POST | `/api/jobs/transition-analysis` | 转岗分析 |
| GET | `/api/jobs/<job_id>/promotion-path` | 升职路径 |
| GET | `/api/personality/questions` | MBTI 题目 |
| POST | `/api/report/targets/manual-search` | 报告用手动搜岗（无 uid 校验） |
| POST | `/api/match/preview` | 匹配预览（无 token 时不可用 `resume_id`） |

---

## 必须登录（无 token → 401）

| 方法 | 路径 | 域 |
|------|------|-----|
| GET | `/api/auth/me` | auth |
| POST | `/api/jobs/assistant/chat` | jobs |
| GET | `/api/jobs/assistant/sessions` | jobs |
| GET | `/api/jobs/assistant/sessions/<id>` | jobs |
| POST | `/api/jobs/assistant/messages/<id>/save` | jobs |
| GET | `/api/profile/resumes` | profile |
| POST | `/api/profile/upload` | profile |
| GET | `/api/profile/result/<resume_id>` | profile |
| GET | `/api/profile/history/<user_id>` | profile + **路径 uid 须与 JWT 一致** |
| GET | `/api/profile/trend/<user_id>` | profile + **路径 uid 须与 JWT 一致** |
| POST | `/api/personality/submit` | personality |
| GET | `/api/personality/profile/<profile_id>` | personality |
| GET | `/api/personality/history/<user_id>` | personality + **路径 uid 须与 JWT 一致** |
| POST | `/api/report/targets/import-from-match` | report |
| POST | `/api/report/generate` | report |
| GET | `/api/report/<report_id>` | report + **须属当前用户** |
| GET | `/api/report/<report_id>/export/pdf` | report |
| GET | `/api/report/my/list` | report |
| GET | `/api/report/<report_id>/reviews` | report |
| POST | `/api/report/review-cycle` | report |

---

## 条件鉴权

| 场景 | 行为 |
|------|------|
| `POST /api/match/preview` + `resume_id` | 必须 Bearer，且 resume 属于当前用户 |
| `POST /api/match/preview` 仅内联 `scores` | 可不登录（测试/降级） |

---

## 资源归属校验

使用 `assert_self_user_id(path_user_id, jwt_uid)` 的接口：

- `GET /api/profile/history/<user_id>`
- `GET /api/profile/trend/<user_id>`
- `GET /api/personality/history/<user_id>`

报告类接口在 SQL 层使用 `user_id = %s` 过滤。

---

## 后续建议（未实现）

- 报告生成异步化（Redis + RQ）
- 统一 `@require_auth` 装饰器，减少 router 内重复判断
