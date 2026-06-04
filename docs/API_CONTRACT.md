# PathFy-Uni API 响应契约

现有前端依赖两种 JSON 包络，**新接口不得混用**，**不得擅自改字段名**。

---

## 包络 A：`ok` 域（auth / jobs / match / report）

| 场景 | 形状 | HTTP |
|------|------|------|
| 成功 | `{ "ok": true, "message"?: string, "data"?: T }` | 200/201 |
| 失败 | `{ "ok": false, "message": string }` | 4xx/5xx |

示例：

```json
{"ok": true, "data": {"token": "...", "user": {"id": 1}}}
{"ok": false, "message": "账号或密码错误"}
```

---

## 包络 B：`code` 域（profile / personality）

| 场景 | 形状 | HTTP |
|------|------|------|
| 成功 | `{ "code": 200, "msg"?: "success", "data"?: T }` | 200 |
| 失败 | `{ "code": <4xx>, "msg": string }` | 与 code 一致或 500 |

示例：

```json
{"code": 200, "msg": "success", "data": [...]}
{"code": 401, "msg": "需要登录（Authorization: Bearer）"}
```

---

## 后端 helper

| 模块 | 用途 |
|------|------|
| `app.core.errors.ApiError` | 抛出后由全局 handler 转为对应包络 |
| `app.core.errors.fail_ok` / `ok_response` | 包络 A |
| `app.core.errors.fail_code` | 包络 B |
| `app.schemas.contract` | TypedDict 参考 |

---

## 前端对应

| 后端域 | 前端模块 |
|--------|----------|
| auth, jobs, match, report | `@/lib/api/*` 使用 `apiJson`，读 `ok` / `message` |
| profile, personality | 读 `code` / `msg` |

详见 [`auth-audit.md`](./auth-audit.md) 与各域 router。
