# 图谱更新域

图谱读取继续直接访问 Neo4j；所有常规写入通过 MySQL 任务队列生成可审阅变更集，管理员确认后才提交。

## 更新生命周期

1. 管理员向 `POST /api/graph/tasks` 上传岗位 Excel、学习资源 CSV 或竞赛 CSV。
2. API 将文件保存到 `GRAPH_TASK_UPLOAD_DIR`，计算 SHA-256，并创建 `queued` 任务。
3. 独立 worker 使用 MySQL 行锁领取任务，在不写 Neo4j 的情况下生成完整变更集。
4. worker 校验基础 `graph_revision`。版本未变化时将任务置为 `awaiting_confirmation`，并设置应用级全局写锁；变化时重新排队。
5. 管理员整单确认或拒绝。确认使用一个 Neo4j 写事务应用变更；拒绝不修改 Neo4j。
6. 原始上传文件保留在 Web 不可访问的私有目录，管理员可从历史任务详情下载；MySQL 永久保留文件 SHA-256、输入摘要、变更统计和事件历史。

待确认任务不会自动过期。存在待确认任务时 worker 不再领取后续任务，所有使用 `graph_write_lock()` 的写操作返回 409。
任务文件通过管理员鉴权接口下载，磁盘目录权限为 `700`、文件权限为 `600`，后端不会向 API 返回私有路径。

## 任务类型

- `job_import`：按 `job_key` 和内容指纹增量提取岗位；同步 JobTitle，并可选择生成晋升路径和换岗关系。`snapshot` 只清理同一 `source_id` 管理的缺失岗位。
- `learning_resource_import`：使用 `datasets/master/learning_resources.csv` 字段契约，更新 `LearningResource` 和 `FOR_JOB_TITLE`。
- `competition_import`：使用 `datasets/master/competitions.csv` 字段契约，更新 `Competition` 和 `FOR_JOB_TITLE`。
- `job_capability_evaluation`：对缺失、过期或全部存量岗位生成八维评分与置信度变更集。
- `job_capability_result_import`：严格校验并导入历史岗位能力 JSONL。
- `job_promotion_import` / `job_lateral_import`：导入策展晋升与换岗数据，策展来源优先于自动生成。
- `promotion_recommendation_import`：同时导入学习资源和竞赛推荐两个 CSV，整单确认。
- `salary_normalization` / `inferred_job_cleanup`：无文件维护任务，仍须生成变更集并由管理员确认。

所有生产写入必须由 graph worker 规划、MySQL 队列留痕并在管理员确认后执行。命令行批处理使用
`python -m app.domains.graph.cli enqueue <task-type> ...`，该命令只入队，不直接连接 Neo4j 写库。

八维评估使用任务参数 `capability_batch_size` 控制每次模型请求的岗位数（默认 8，范围 1–50）。
图谱结构化/派生调用使用 `GRAPH_MAX_RETRIES`，八维评估使用 `GRAPH_CAP_MAX_RETRIES`；临时 API
或网络异常会按指数退避重试，耗尽重试后任务才会失败。

旧的直接导入及五个独立派生写接口返回 410，不再提供预览模式。紧急清空接口保留，但受全局 guard 约束并写入 MySQL 审计历史。

## API

所有接口仅管理员可用，并使用 `ok` envelope。

- `POST /api/graph/tasks`：multipart 创建任务，返回 202。
- `GET /api/graph/tasks`：分页并按 `status`、`task_type` 筛选。
- `GET /api/graph/tasks/:id`：任务摘要和事件时间线。
- `POST /api/graph/tasks/:id/confirm`：确认整份变更集。
- `POST /api/graph/tasks/:id/reject`：提交 `{ "reason": "..." }` 拒绝。
- `POST /api/graph/tasks/:id/cancel`：仅取消 `queued` 任务。
- `GET /api/graph/guard`：当前 revision 和锁状态。

## Worker

```bash
cd backend
python -m app.domains.graph.worker
# 调试时只领取一次
python -m app.domains.graph.worker --once
```

生产环境必须将 worker 与 Gunicorn 作为两个独立进程运行。Supervisor 和 Docker Compose 示例已包含对应服务。
