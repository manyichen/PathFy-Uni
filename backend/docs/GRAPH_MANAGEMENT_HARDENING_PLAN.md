# 图谱管理可靠性加固执行方案

## 目标与边界

本方案在现有 MySQL 图谱任务队列、Neo4j 变更集、管理员确认、全局写锁和系统设置快照之上继续演进，不重做已经可用的任务类型。

核心目标：

- 所有删除都来自管理员已经审阅的显式删除清单，apply 阶段不得动态扩大删除范围。
- worker 崩溃、并行启动和临时外部服务失败不会造成任务重复规划、重复提交或永久卡死。
- Neo4j 已提交、MySQL 派生投影失败时能够自动补偿，不重复写图。
- 大型变更集支持真正分页审阅，确认事务保持原子且减少 Cypher 往返。
- 八维评估、队列健康和图谱版本具有可追溯、可监控、可恢复的运营能力。

保持不变：

- 普通用户图谱、岗位、匹配和报告 API 契约。
- Neo4j 现有业务标签和关系语义。
- `merge`、`snapshot`、`source_id` 的用户可见含义。
- 管理员整单确认或拒绝，不增加绕过任务队列的生产写入口。
- 上传数据集继续允许管理员下载；保留策略单独配置，不改成数据库大二进制。

## 当前基线

现有实现已经具备：

- MySQL 任务、事件、文件元数据和单例 `graph_write_guard`。
- `queued → running → awaiting_confirmation → applying → final` 状态链。
- 变更集 SHA-256、Neo4j `GraphTaskCommit` 幂等标记和配置快照。
- 岗位、八维评估、学习资源、竞赛、晋升、换岗、推荐、薪资和清理任务。
- 能力评估批大小、Provider 请求重试、管理员任务列表/详情/确认/拒绝/取消。

已确认的主要风险：

- 横向换岗规划只覆盖部分岗位，但 apply 会全局清理未在本轮出现的自动关系。
- 岗位导入重建 JobTitle 时可能断开策展资源、竞赛或晋升关系。
- worker 启动时无条件恢复所有 `running` 任务，不能安全支持多进程或滚动重启。
- Neo4j 提交与 MySQL `job_titles` 投影之间没有可持续重试的补偿状态。
- `/changes` 会先反序列化完整 LONGTEXT，再在内存中分页。
- apply 对岗位、技能和关系执行大量逐条 Cypher。
- 旧 repository/sync service 仍保留可直接写 Neo4j 的函数。

## 批次一：删除范围与策展数据保护

### 修改

1. 将 version 2 变更集扩展为带删除 manifest 的兼容格式：
   - `delete_manifest.jobs`
   - `delete_manifest.job_titles`
   - `delete_manifest.promotions`
   - `delete_manifest.lateral`
   - 每项保存业务键、来源、删除原因和影响关系摘要。
2. `snapshot` planner 在只读阶段查询并固化同一 `source_id` 下需要删除的对象。
3. apply 只执行 manifest 中的删除项，不再使用“本轮 run id 未命中”进行全局删除。
4. JobTitle 删除前保护策展关系：存在 curated 关系时保留 JobTitle，并在摘要中标记 `retained_for_curated_links`。
5. 移除横向换岗前 50 个标题的静默截断；采用分块规划并记录完整覆盖范围。
6. 任务摘要增加精确新增、修改、删除、保留和冲突数量。

### 测试门禁

- 超过 50 个 JobTitle 时，未参与当前分块的自动换岗关系不得被删除。
- 一个来源的 snapshot 不得删除其他来源岗位或关系。
- 与学习资源、竞赛、策展晋升关联的 JobTitle 不得被岗位导入 `DETACH DELETE`。
- 变更集没有 delete manifest 时，version 2 apply 不得执行推导式删除；version 1 历史任务保持兼容。
- 确认前后删除数量与详情页预览一致。

### 回退

本批不增加数据库迁移。若出现差异，只回退 planner/apply 的 version 2 manifest 改动，保留既有任务表和历史任务兼容。

## 批次二：Worker 租约、心跳与分类重试

### 数据库迁移

为 `graph_update_tasks` 增加：

- `worker_id`
- `lease_token`
- `heartbeat_at`
- `lease_expires_at`
- `attempt_count`
- `next_retry_at`
- `last_error_code`
- `last_error_retryable`

### 修改

1. claim 使用行锁抢占并生成随机 lease token。
2. worker 在解析、LLM 批次和生成变更集期间续租。
3. 所有 running 状态更新同时校验 task id 与 lease token。
4. 启动恢复只处理已经过期的 lease，不重置其他 worker 的活动任务。
5. 错误分类：
   - 网络超时、429、Provider 5xx、临时 Neo4j/MySQL 连接失败：可重试。
   - 输入格式、引用不存在、重复业务键、评分字段非法：不可重试。
   - graph revision 冲突：重新规划，不计入普通失败次数。
6. 重试使用带抖动的指数退避，并记录每次计划时间和错误事件。

### 测试门禁

- 两个 worker 同时启动只能有一个任务获得有效租约。
- 第二个 worker 启动不得重置第一个 worker 的运行任务。
- worker 进程退出后，任务仅在 lease 到期后恢复。
- 旧 lease token 不能更新已经被新 worker 领取的任务。
- 可重试和不可重试错误进入正确状态，最大次数生效。

## 批次三：确认异步化与跨库投影补偿

### 数据库迁移

增加任务提交与投影字段：

- `confirm_requested_at`
- `neo4j_committed_at`
- `projection_status`
- `projection_attempts`
- `projection_error`
- `projection_next_retry_at`

### 修改

1. 确认 API 只校验管理员、guard、revision 和变更集哈希，并将任务置为 `applying`。
2. worker 执行 Neo4j 短事务；`GraphTaskCommit` 继续作为幂等事实。
3. Neo4j 提交成功后立即记录 commit、递增 revision 并释放写 guard。
4. `job_titles` 等 MySQL 投影独立、幂等、可持续重试。
5. worker 重启发现 `GraphTaskCommit` 时不重写 Neo4j，继续完成缺失的 MySQL 投影。
6. 前端继续轮询任务状态，展示“图谱已提交，派生索引同步中”。

### 测试门禁

- HTTP 确认不执行长时间 Neo4j 写事务。
- Neo4j 成功而 MySQL 同步失败时，重试不得产生第二个图谱提交。
- worker 重启能从 commit marker 恢复投影。
- projection 最终成功后任务状态、revision、guard 一致。

## 批次四：变更集真分页、批量 Apply 与唯一写入口

### 数据库迁移

新增 `graph_update_task_change_chunks`：

- `task_id`
- `group_name`
- `chunk_no`
- `item_count`
- `chunk_sha256`
- `payload_json`
- `(task_id, group_name, chunk_no)` 唯一约束

任务表保留 manifest、摘要和总哈希，继续读取未处理的旧 LONGTEXT 任务。

### 修改

1. planner 按固定条数写入 change chunks。
2. 总哈希基于稳定排序的 manifest 和 chunk hash 计算。
3. `/changes` 直接按 group/chunk 查询，不读取完整变更集。
4. apply 流式读取分组，在同一个 Neo4j 事务中使用 `UNWIND` 批量写入。
5. Neo4j constraints/index 移到初始化检查，不在每次确认时创建。
6. 将旧直接写图函数迁成只读 planner helper 或删除；静态检查确保生产写入只存在于 apply 和明确的紧急维护入口。

### 测试门禁

- 十万条预览请求的内存使用不随完整变更集线性增长。
- chunk 缺失、乱序或篡改时禁止确认。
- 批量 apply 与固定 fixture 的旧行为结果一致。
- 仓库静态检查阻止新增绕过 guard 的 Neo4j 写事务。

## 批次五：质量、可观测性与恢复

### 数据库迁移

新增能力评估缓存和可选的反向任务元数据：

- `graph_capability_evaluation_cache`
- 任务 `inverse_manifest_json` 或对应 change chunks。

缓存键至少包含：

- `cap_input_fingerprint`
- `cap_version`
- `provider`
- `model`
- `prompt_version`

### 修改

1. 八维评估按岗位命中缓存，批量响应缺项时只重试缺失岗位。
2. 记录主评/复核模型、调用耗时、token、请求 ID、重试次数和风险原因。
3. Dashboard 完整检查 8 个评分、8 个置信度、版本和输入指纹。
4. 低置信度和薪资版本使用统一配置，不硬编码。
5. 增加 worker 心跳、队列等待时间、锁定时长、失败率、投影积压和 LLM 成本统计。
6. 成功任务可以创建新的反向变更任务；反向任务仍需管理员整单确认，不提供直接回滚。
7. 增加任务类型 catalog API，让前端从后端注册表读取字段、限制和输入格式说明。

### 测试门禁

- 相同输入、模型和 prompt 版本命中缓存；任一版本变化会失效。
- Dashboard 缺失数量覆盖任意一个评分或置信度为空的岗位。
- 反向任务恢复固定 fixture 后，图谱业务数据回到提交前状态。
- API 不返回密钥、完整配置快照或模型隐私数据。

## 提交与验证策略

- 每个批次至少一个独立提交，不混入普通用户功能修改。
- 每个批次先增加回归测试，再修改实现。
- 后端门禁：`pytest tests/test_graph*.py -q`，随后运行全量 `pytest tests/ -q`。
- 数据库批次必须验证 Alembic upgrade/downgrade 和空数据库 `upgrade head`。
- 涉及前端状态展示的批次运行 `pnpm typecheck`、`pnpm test` 和 `pnpm generate`。
- 使用固定 Excel、CSV、JSONL fixture 比较 planner 的业务键、属性和关系结果。
- 所有危险删除场景必须验证：确认前 Neo4j 不变、拒绝后不变、revision 冲突后不使用过期清单。

## 完成定义

- 多 worker、滚动重启和临时 Provider 故障不会重复执行任务。
- Neo4j 写入成功后不存在无法自动修复的 MySQL 投影状态。
- version 2 任务的所有删除对象在确认前均可精确查看。
- 策展数据不会被自动岗位导入或自动派生任务删除。
- 大型任务详情是真分页，确认事务使用批量 Cypher。
- 生产图谱写入只能经过管理员确认后的 apply 层。
