# 人格融合上线与回滚清单

## 1. 上线顺序

1. 备份 MySQL，并执行 `alembic upgrade head`；目标 head 为 `20260819_0012`。
2. 保持 `MATCH_PREFERENCE_TIE_BREAK_ENABLED=false`，先发布报告 snapshot v2、执行方式建议和复盘信号。
3. 在图谱管理中运行工作环境评估/导入任务，人工复核后写入；不得只按岗位名称生成高置信度标签。
4. 观察至少一个完整复盘周期，核对报告策略接受率、编辑率、复盘体验信号与投诉情况。
5. 当候选岗位工作环境覆盖率稳定达到 `MATCH_PREFERENCE_TIE_BREAK_MIN_COVERAGE` 后，小流量开启软排序。
6. 逐步调整 `MATCH_PREFERENCE_TIE_BREAK_EXPERIMENT_PERCENT`；每次调整保留一个观察窗口。

## 2. 发布门槛

- 报告 input snapshot v1/v2 哈希验证均通过；
- 岗位工作环境逐轴具有原文证据、来源、版本和置信度；
- `tie_break` 只在 `MATCH_PREFERENCE_TIE_BREAK_MAX_ABILITY_GAP` 同分带内改变顺序；
- 任何结果均可恢复原能力排名；
- 人格数据删除、报告数据导出和报告删除覆盖新增字段/行为证据；
- 后端、前端单测、类型检查和匹配/报告 E2E 通过。

## 3. 监控指标

- `preference_tie_break_requested_count`：用户主动请求量；
- `preference_tie_break_variant_count`：进入实验变体量；
- `preference_strategy_accepted_count` / `preference_strategy_edited_count`：执行建议接受与编辑；
- `confirmed_preference_evidence_count`：用户确认的复盘行为证据；
- 离线按快照中的 `original_ability_order`、`preference_order`、`changes` 计算名次变化和岗位多样性；
- 联合现有点击、报告导入、计划接受、行动完成和复盘状态指标评估效果。

## 4. 即时回滚

1. 将 `MATCH_PREFERENCE_TIE_BREAK_ENABLED` 设为 `false` 并发布系统设置；新请求立即恢复能力原序。
2. 如需停止报告人格个性化，将 `CAREER_ENABLE_PERSONALITY_STRATEGY` 设为 `false`；历史报告仍按冻结快照可复现。
3. 用户可单独关闭 `use_personality_in_match` 和 `use_personality_in_report`。
4. 不要通过删除历史快照实现回滚；如涉及隐私删除，必须同步重建哈希或删除对应报告。

## 5. 数据边界

- 人格视觉指纹保留为用户可理解的身份表达；
- MBTI 标签不参与岗位淘汰；
- 四维偏好不改变八维能力、岗位要求、能力缺口和报告事实；
- 行为证据与问卷结果并列呈现，三周期提示仅建议核对或重测，不自动改写画像。
