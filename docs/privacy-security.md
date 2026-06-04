# PathFy-Uni 隐私与安全加固变更说明

更新时间：2026-06-03

## 变更目标

本轮变更主要围绕用户数据权限与隐私安全，重点解决两类风险：

- 用户数据访问权限过宽，可能通过传入 `user_id` 访问非本人数据。
- 简历、复盘、聊天等用户文本在发送给大模型或长期保存时，存在个人敏感信息暴露风险。

## 用户数据权限收紧

### 后端接口鉴权

鉴权由 `backend/app/core/security.py` 提供 `get_bearer_user_id()`、`assert_self_user_id()`。完整路由见 [`auth-audit.md`](./auth-audit.md)。

- `backend/app/domains/personality/router.py`
  - 性格测试提交、结果详情、历史记录接口必须携带 `Authorization: Bearer <token>`。
  - 不再信任前端传入的 `user_id`，统一使用 token 中的当前用户。
  - 访问 `/history/<user_id>` 时，校验路径用户是否等于当前登录用户。

- `backend/app/domains/profile/router.py`
  - 简历上传、结果查看、历史记录、趋势接口改为必须登录。
  - `/history/<user_id>`、`/trend/<user_id>` 增加用户归属校验。
  - 简历上传使用当前 token 用户，不接受表单里的 `user_id`。

- `backend/app/domains/auth/router.py`
  - 登录接口只保留 `POST`，减少误用和凭据暴露风险。

- `backend/app/domains/match/router.py`
  - 使用 `resume_id` 做匹配预览时必须登录，且简历属于当前用户。
  - `GET /api/match/history` 仅返回当前用户的匹配快照。

- `backend/app/domains/report/router.py`
  - 报告生成、详情、复盘、PDF 导出等接口均需登录，并按 `user_id` 校验报告归属。

### 前端配合

- `frontend/src/components/personality/PersonalityTest.svelte`
  - 性格测试提交走 `@/lib/api/personality`，自动携带 token。
  - 无硬编码 `user_id`。

- `frontend/src/pages/profile/index.astro`
  - 简历上传表单仅含姓名、专业与文件，无 `user_id` 字段。

- `frontend/src/lib/api/*` 与 `frontend/src/lib/features/auth/session`
  - 统一通过 Bearer 访问需登录接口，不在请求体传递 `user_id`。

## 大模型调用隐私保护

### 新增统一脱敏模块

- 新增 `backend/app/infrastructure/privacy.py`
  - 提供 `redact_text`、`redact_payload`、`privacy_student_profile`、`storage_safe_text` 等工具。
  - 脱敏范围包括：
    - 邮箱
    - 手机号
    - 身份证号
    - 银行卡号
    - URL 与 token 查询参数
    - 微信/QQ/联系方式字段
    - 密钥、token、cookie、authorization 等敏感键
  - 对发往大模型的数据默认执行递归脱敏（受 `LLM_PRIVACY_MODE` 控制）。

### 简历评分保护

- `backend/app/utils.py`
  - `score_resume()` 在调用通义 Qwen 前先对简历 OCR 文本脱敏。
  - 增加文本长度限制，默认最多发送 `LLM_MAX_RESUME_CHARS` 字符。
  - prompt 中加入隐私提示，要求模型不要复述个人身份信息。

### 人岗匹配精排保护

- `backend/app/domains/match/llm_refine.py`
  - DeepSeek 精排只接收 `privacy_student_profile()` 匿名化学生画像。
  - 不再向模型发送 `display_name`、用户 id、简历摘录等字段。
  - 默认不返回模型原始 `raw_snippet`；调试时可经 `LLM_STORE_RAW_SNIPPETS` 开启，且片段经脱敏。

- `backend/app/domains/match/services.py`
  - 匹配预览按 `resume_id` 加载画像时不再查询 `resume_text`。
  - 返回结果中移除 `resume_excerpt`。
  - 前端仍可展示 `display_name`、八维分等必要信息，但不把简历原文或摘录放进 LLM payload。

- `backend/app/domains/match/snapshots.py`
  - 匹配历史快照 `student_json` 与 preview 响应一致，不含简历摘录。

### 岗位助手保护

- `backend/app/infrastructure/llm.py`
  - `call_ark_json()` 在调用豆包/Ark 前对 `payload` 执行 `redact_payload()`，system 追加隐私提示。

- `backend/app/domains/jobs/assistant.py`
  - 岗位助手意图解析、回答生成等均经 `call_ark_json`，上下文传入模型前已清洗敏感字段。

- `backend/app/domains/jobs/router.py`
  - 转岗分析类 LLM 调用经同一 `call_ark_json` 接入 payload 脱敏。

### 职业报告保护

- `backend/app/domains/report/review.py`
  - 复盘文本 `review_text` 发往 DeepSeek 抽取指标前先脱敏。
  - 自动重规划等请求的 user payload 经 `redact_payload()` 处理。

- `backend/app/domains/report/llm.py`、`backend/app/domains/report/trends.py`
  - 报告总结、趋势增强等 LLM payload 均接入脱敏。
  - 报告总结中 `student_name` 统一使用「候选人」，不发送真实姓名。
  - DeepSeek 兼容调用的 system prompt 含隐私提示。

- `backend/app/domains/report/services.py`、`backend/app/domains/report/sanitize.py`
  - 新提交复盘默认存脱敏文本；读取报告/复盘列表时递归清洗 `review_text` 字段。

## 本地存储隐私保护

### 简历文件与 OCR 文本

- `backend/app/domains/profile/router.py`
  - 上传的简历文件保存到 `RESUME_UPLOAD_DIR`（默认 `backend/private_uploads/resumes`，已在 `.gitignore` 忽略）。
  - OCR 完成后默认删除上传的原文件和 PDF 转图文件（`DELETE_UPLOADED_RESUME_AFTER_OCR`）。
  - `student_resume.resume_text` 默认保存脱敏后的文本，而不是完整 OCR 原文。
  - 查询简历结果时，即使历史数据里存在原文，也会在返回前再次脱敏。

### AI 聊天记录

- `backend/app/domains/jobs/assistant.py`
  - 用户消息、助手回复、会话标题默认保存脱敏版本。
  - 读取历史会话时再次执行存储级脱敏。

### 职业复盘文本

- `backend/app/domains/report/services.py`
  - 新提交的 `review_text` 默认保存脱敏版本。
  - 读取旧报告或旧复盘时，经 `sanitize_review_text_fields()` 清洗后再返回给前端。

### API 响应缓存控制

- `backend/app/__init__.py`
  - 所有 `/api/*` 响应默认添加：
    - `Cache-Control: no-store, max-age=0`
    - `Pragma: no-cache`
    - `X-Content-Type-Options: nosniff`
    - `Referrer-Policy: no-referrer`
    - `Permissions-Policy: geolocation=(), microphone=(), camera=()`

## 新增配置项

已写入 `backend/.env.example` 与 `deploy/env.production.example`：

```env
LLM_PRIVACY_MODE=true
LLM_MAX_TEXT_CHARS=4000
LLM_MAX_RESUME_CHARS=6000
LLM_MAX_FIELD_CHARS=1200
LLM_STORE_RAW_SNIPPETS=false

LOCAL_STORE_RAW_RESUME_TEXT=false
LOCAL_STORE_RAW_REVIEW_TEXT=false
LOCAL_STORE_RAW_CHAT_MESSAGES=false
LOCAL_MAX_STORED_TEXT_CHARS=4000
DELETE_UPLOADED_RESUME_AFTER_OCR=true
API_CACHE_NO_STORE=true
```

默认策略是「外发脱敏、本地少存、响应不缓存」。如果确实需要保留原文用于调试或业务回看，需要在 `.env` 中显式开启对应开关。

## 依赖与环境处理

- 隐私相关配置项已并入 `backend/app/core/config.py`。
- 简历私有上传目录 `backend/private_uploads/` 已列入 `.gitignore`，避免临时文件进入版本库。
- 生产环境变量模板已同步：`deploy/env.production.example`。
- 发布前请将上述隐私项写入服务器 `backend/.env`，勿提交 `.env` 本身。

## 验证结果

已通过以下检查：

```powershell
cd backend
python -m pytest tests/test_privacy.py tests/test_app.py -q
python -m pytest tests/ -q
```

```powershell
cd frontend
pnpm run check
```

检查结果：

- `tests/test_privacy.py`：邮箱、手机、身份证、URL token、payload 剥离等用例通过。
- `tests/test_app.py`：`GET /api/health` 响应含 `Cache-Control: no-store`、`X-Content-Type-Options: nosniff`。
- 全量 `pytest tests/` 通过。
- 手动冒烟要点见 [`smoke-test.md`](./smoke-test.md)（含鉴权与隐私响应头）。

## 运行方式

后端：

```powershell
cd backend
python run.py
```

前端：

```powershell
cd frontend
pnpm dev
```

浏览器访问：

```text
http://localhost:4321
```

## 后续建议

- 增加数据库清洗脚本，批量处理历史 `resume_text`、`review_text`、聊天内容（读取接口已对历史明文再脱敏）。
- 对敏感数据表增加字段级加密或单独密钥管理。
- 增加审计日志，记录谁在何时访问了个人画像、报告、聊天历史。
- 在前端增加隐私提示，告知用户简历和复盘文本会经过脱敏处理后再用于 AI 分析。
- 新增或变更 API 时同步更新 [`auth-audit.md`](./auth-audit.md) 与本说明中的模块路径。
