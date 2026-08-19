# PathFy-Uni 前端架构、报告链路与视觉升级方案

更新日期：2026-07-16  
适用分支：`suilli`  
目标：先解除生涯报告模块的 500 与匹配记录不可见问题，再逐步处理前端页面膨胀、类型不稳、API 响应历史包袱和视觉同质化问题。

## 1. 当前诊断结论

### 1.1 P0 故障：代码版本与本地数据库结构不一致

本地只读诊断结果：

```text
backend /api/health: ok
frontend proxy /api/health: ok
MySQL users: 9
MySQL student_resume: 25
MySQL match_runs: 14
MySQL match_run_items: 420
MySQL career_reports: 25
Neo4j Job count: 6664

system_setting_state: missing
system_setting_revisions: missing
graph_update_tasks: missing
match_runs.settings_revision: missing
match_runs.config_snapshot_json: missing
career_reports.settings_revision: missing
career_reports.config_snapshot_json: missing

mizi user_id: 14
mizi match_runs: 7
mizi student_resume: 1
```

这说明 `mizi` 用户不是没有匹配记录，而是后端代码已经升级到“系统设置分层 + 执行快照”版本，本地数据库仍停在旧结构。

直接影响：

- `/api/match/history` 会查询 `match_runs.settings_revision`，旧表没有该列，接口返回 500，前端弹窗保持空列表，于是看到“暂无匹配记录”。
- `/api/match/preview` 虽然主流程会返回结果，但快照落库会写 `settings_revision/config_snapshot_json`，旧表没有列时会被 `snapshot_warning` 静默吞掉，后续报告页无法复用本次匹配。
- `/api/report/generate` 入口会读取 `active_system_settings()`，但 `system_setting_state/system_setting_revisions` 不存在，直接 500。
- 即使跳过上一步，`career_reports` 旧表也缺少 `settings_revision/config_snapshot_json`，报告插入仍可能失败。

### 1.2 报告模块链路风险

报告页当前链路：

```text
前端 report.vue
  -> GET /api/profile/resumes
  -> GET /api/match/history
  -> POST /api/report/targets/import-from-match
  -> POST /api/report/targets/manual-search 或 random-browse
  -> POST /api/report/generate
       -> active_system_settings()
       -> _load_profile(resume_id, user_id)
       -> _query_jobs_by_ids(target_job_ids) from Neo4j
       -> build target insights / recommendations / plans
       -> insert career_reports / career_report_targets
```

风险点：

- 前端手动选择的目标最终只传 `job_id`，生成时后端会重新查 Neo4j。如果 `job_id` 为空、被旧缓存污染、或不是 Neo4j 中 `job_key/job_code/name/title/elementId` 的任一值，会报“无效 job_id”。
- `generate_report` 目前只捕获 `ReportServiceError`，数据库结构错误、Neo4j 连接异常、未预料的 LLM/推荐逻辑异常会直接变成 Flask 500，前端只能看到泛化失败。
- 匹配历史接口失败时，前端没有在弹窗里展示错误状态，只是 toast 后保留空列表，用户会误解为没有记录。

### 1.3 前端工程债

当前较重文件：

- `frontend/app/pages/report.vue`：约 858 行，状态、缓存、弹窗、API、展示、样式全部混在一起。
- `frontend/app/components/AppHeader.vue`：约 448 行，桌面导航、移动抽屉、主题、账号操作耦合。
- `frontend/app/pages/account.vue`、`frontend/app/pages/profile.vue`：表单、展示、缓存、业务解释混合。
- `frontend/app/pages/match.vue`：仍是早期压缩写法，后续维护和类型增强困难。

类型风险：

- `frontend/app` 中 `any` 数量偏多。
- API 类型目前只有基础 envelope 和少量通用类型，报告、匹配、画像、岗位对象靠运行时猜字段。
- 前端已同时兼容 `{ ok, message, data }` 与 `{ code, msg, data }`，短期可运行，长期增加认知成本。

### 1.4 视觉问题

当前页面多数以线框、图标、卡片、表格为主，信息密度有了，但职业规划产品应更有“路径感”和“成长感”。现在的问题不是“简洁”，而是缺少领域化视觉结构：

- 首页与工作台之间的视觉语言没有完全统一。
- 报告页像后台配置页，而不是“职业发展驾驶舱”。
- 能力画像、人岗匹配、报告复盘之间缺少一条可感知的成长路线。
- 线条和图标过多，内容区域缺少层次、场景、成果物和故事化锚点。

## 2. P0 修复方案：先让报告链路可用

### 2.1 数据库迁移修复

先备份数据库，再处理迁移状态。

建议流程：

```powershell
cd E:\Suilli10086\PathFy-Uni\backend
.\.venv\Scripts\Activate.ps1

# 只读校验当前旧基线是否符合预期
python tools/verify_alembic_baseline.py

# 如果当前库是历史 schema.sql / migrations/*.sql 初始化，但 alembic_version 为空：
alembic stamp 20260712_0001

# 执行 0002 -> 0005，创建 graph_update_tasks / system settings，并补齐快照列
alembic upgrade head
```

需要补充一个“迁移体检脚本”：

```text
backend/tools/check_runtime_schema.py
```

检查项：

- `alembic_version` 当前版本是否为 `20260715_0005`。
- `system_setting_state/system_setting_revisions/user_preferences` 是否存在。
- `graph_update_tasks` 是否存在。
- `match_runs/career_reports/graph_update_tasks` 是否包含 `settings_revision/config_snapshot_json`。
- `match_run_items` 是否存在且与 `match_runs` 外键正常。

如果要兼容已手动改过的数据库，建议把 `20260715_0004_settings_layers.py` 改为幂等迁移：通过 `INFORMATION_SCHEMA.COLUMNS` 判断列是否存在后再 `ALTER TABLE`，避免重复执行失败。

### 2.2 后端错误兜底

改造 `backend/app/domains/report/router.py`：

- `generate_report` 捕获普通 `Exception`。
- 后端用 `current_app.logger.exception(...)` 记录堆栈。
- 前端返回统一 JSON，而不是裸 500。

建议返回：

```json
{
  "ok": false,
  "message": "报告生成失败：数据库结构未升级或外部服务异常，请联系管理员检查迁移状态"
}
```

改造 `backend/app/domains/match/router.py`：

- `/history` 捕获数据库结构类错误时返回可读 message。
- 不要让用户只看到空列表。

### 2.3 前端报告页错误状态

改造 `report.vue` / 后续拆分后的 `ReportImportMatchDialog.vue`：

- 匹配历史加载失败时，弹窗内显示 `UAlert`，附“刷新 / 去人岗匹配生成 / 检查数据库迁移”动作。
- `generate()` 失败时保留当前目标选择，不清空工作区。
- 手动选择目标后，在按钮区显示“已选择 N 个目标，可生成报告”，并在请求前过滤空 `job_id`。
- 如果后端返回“无效 job_id”，前端高亮对应目标并提示重新选择。

### 2.4 P0 验收标准

- `mizi` 登录后，报告页“导入匹配数据”能看到 7 条历史记录。
- 从匹配历史导入后，`resumeId` 自动设置为记录关联画像。
- 手动搜索 / 随机浏览 / 岗位选择三种入口添加目标后都能生成报告。
- `/api/report/generate` 不再出现无解释的 500；即使失败也返回可读 JSON。
- 后端新增测试覆盖：
  - 缺少 settings 表时返回可读错误或 schema doctor 提示。
  - 旧 match_runs 表缺列时，测试能复现并由迁移修复。
  - `import_targets_from_match` 能从粗排列表提取 Top5。

## 3. 前端拆分方案

### 3.1 报告页目标结构

将 `report.vue` 从“巨型页面”改为页面编排层：

```text
frontend/app/pages/report.vue
  只保留：
  - definePageMeta / useSeoMeta
  - 调用 composables
  - 页面主布局
  - 组合子组件

frontend/app/types/report.ts
frontend/app/types/match.ts
frontend/app/types/profile.ts
frontend/app/types/job.ts

frontend/app/composables/report/useReportWorkspace.ts
frontend/app/composables/report/useReportTargets.ts
frontend/app/composables/report/useReportGeneration.ts
frontend/app/composables/report/useReportHistory.ts
frontend/app/composables/report/useReportPublicInfo.ts

frontend/app/components/report/ReportPageHeader.vue
frontend/app/components/report/ReportConfigPanel.vue
frontend/app/components/report/ReportSelectedTargets.vue
frontend/app/components/report/ReportImportMatchDialog.vue
frontend/app/components/report/ReportHistoryDialog.vue
frontend/app/components/report/ReportSummaryPanel.vue
frontend/app/components/report/ReportTargetInsights.vue
frontend/app/components/report/ReportDevelopmentLines.vue
frontend/app/components/report/ReportReviewPanel.vue
frontend/app/components/report/ReportResetDialog.vue
```

目标：

- `pages/report.vue` 控制在 120 行以内。
- 每个组件只负责一种视图。
- 每个 composable 只负责一种状态或副作用。
- 所有本地缓存读写集中在 `useReportWorkspace.ts`。

### 3.2 AppHeader 拆分

```text
frontend/app/components/app-header/AppHeaderShell.vue
frontend/app/components/app-header/AppBrand.vue
frontend/app/components/app-header/AppDesktopNav.vue
frontend/app/components/app-header/AppMobileNav.vue
frontend/app/components/app-header/AppUserActions.vue
frontend/app/components/app-header/AppAppearanceActions.vue
```

目标：

- `AppHeader.vue` 退化为薄封装，行数控制在 80 行以内。
- 移动端抽屉关闭逻辑只在 `AppMobileNav` 内部处理。
- 主题切换和账号操作不与导航渲染互相污染。

### 3.3 account/profile/match 后续整理

优先顺序：

1. `match.vue` 先从压缩写法改为正常 Vue 结构，抽出 `useMatchPreview.ts`。
2. `profile.vue` 抽出上传表单、雷达卡、历史画像弹窗、分析区块。
3. `account.vue` 抽出偏好设置、账号信息、主题设置。

## 4. 类型硬化方案

### 4.1 建立业务类型

新增：

```text
frontend/app/types/job.ts
frontend/app/types/profile.ts
frontend/app/types/match.ts
frontend/app/types/report.ts
frontend/app/types/settings.ts
```

核心类型：

```ts
export type CapabilityKey =
  | 'cap_req_theory'
  | 'cap_req_cross'
  | 'cap_req_practice'
  | 'cap_req_digital'
  | 'cap_req_innovation'
  | 'cap_req_teamwork'
  | 'cap_req_social'
  | 'cap_req_growth'

export type CapabilityScores = Record<CapabilityKey, number>

export interface JobTarget {
  job_id: string
  id?: string
  title: string
  company?: string
  location?: string
  salary?: string
  score_avg?: number
  scores?: Partial<CapabilityScores>
  source?: 'manual_search' | 'random_browse' | 'match_snapshot_llm' | 'match_snapshot_coarse' | string
}

export interface MatchHistoryItem {
  run_id: number
  resume_id: number
  match_goal: 'fit' | 'stretch'
  q: string
  location_q: string
  returned: number
  student_name: string
  created_at: string
}

export interface CareerReportGenerateRequest {
  resume_id: number
  target_job_ids: string[]
  primary_job_id: string
  match_goal: 'fit' | 'stretch'
}
```

### 4.2 用 Zod 做边界解析

项目已有 `zod` 依赖，建议用于 API 边界而不是所有内部对象。

```text
frontend/app/schemas/report.ts
frontend/app/schemas/match.ts
```

策略：

- API 响应入口做 `safeParse`。
- 解析失败时保留原错误和路径，toast 展示“接口结构异常”，console 记录 schema issue。
- 内部组件只接收已归一化类型，减少 `?.` 和 `any`。

### 4.3 `any` 降低目标

当前 `frontend/app` 中 `any` 偏多。阶段目标：

- Phase 1：报告相关 `any` 降到 10 个以内。
- Phase 2：匹配、画像相关 `any` 降到 20 个以内。
- Phase 3：全 `frontend/app` 控制在 40 个以内，且剩余 `any` 必须带注释说明外部接口不稳定原因。

## 5. API 响应格式收敛方案

### 5.1 保留兼容，不继续扩散

现状：

- 新域多用 `{ ok, message, data }`。
- `profile/personality` 仍用 `{ code, msg, data }`。
- 前端 `unwrapOk/unwrapCode` 双轨兼容。

规则：

- 新接口只允许 `{ ok, message, data }`。
- 老接口不立刻破坏，先由前端 adapter 统一转成内部 `Result<T>`。
- 文档标记 `CodeEnvelope` 为 legacy。

### 5.2 前端统一入口

建议扩展 `useApi`：

```ts
api.ok<T>()       // 新接口
api.legacyCode<T>() // 仅 profile/personality 老接口使用
```

禁止新页面直接写 `api.request<CodeEnvelope<any>>`。

### 5.3 后端迁移路径

短期：

- `profile/personality` 后端暂不改协议。
- 前端建立 `profileApi` / `personalityApi` adapter，把 legacy response 转成内部 ok 结果。

中期：

- 后端新增 v2 路由或通过响应中同时提供 `ok: true` 过渡。
- E2E 和单测全部切到 ok envelope。

长期：

- 删除 `CodeEnvelope` 直接使用点。
- `docs/API_CONTRACT.md` 更新为“统一 envelope + legacy 说明”。

## 6. 视觉升级方案

### 6.1 参考原则

参考来源：

- Linear 的 redesign 强调降低视觉噪声、保持对齐、提升层级和导航密度，适合借鉴到当前页眉、页面分区和工作台导航。
- Stripe Dashboard 把首页作为可定制概览，并提供资源导航、搜索、过滤、导出等高频操作，适合借鉴到岗位、报告、图谱管理页。
- Atlassian 的数据可视化指南强调按任务选择图表：看趋势用线图，看比较用柱状/点图，看关系用散点/热力等，适合重构能力画像与报告图表。
- Notion 的设计系统建议包含组件库、样式指南、文档与版本管理，同时避免过度复杂、不响应式、过时的组件。

链接：

- Linear UI redesign: https://linear.app/now/how-we-redesigned-the-linear-ui
- Stripe Dashboard basics: https://docs.stripe.com/dashboard/basics
- Atlassian data visualization guide: https://www.atlassian.com/data/charts/how-to-choose-data-visualization
- Notion design system templates: https://www.notion.com/templates/collections/best-design-system-templates-for-ux-ui-designers

### 6.2 PathFy-Uni 新视觉方向

建议定位为：

```text
职业规划驾驶舱 Career Cockpit
```

而不是普通后台。界面要围绕“我现在在哪、我要去哪、下一步做什么”组织。

核心页面气质：

- 信息密度保留，但更有路线感。
- 少一点平均分布的卡片，多一点带优先级的主视图。
- 少一点纯图标说明，多一点真实职业对象、路径节点、证据成果、阶段任务。
- 主题色继续保留可调，但默认视觉不要只靠单一青蓝色，可加入状态色：能力差距用琥珀，完成度用绿色，风险用玫红，路径关系用靛蓝。

### 6.3 首页改造

当前首页已有 `.old` 迁移的视觉基础，下一步应强化“第一屏就是产品体验”：

- 顶部保留动态水波，但加入“职业路径地图”主画面。
- H1 下方不是宣传语，而是三段实时入口：
  - 生成能力画像
  - 浏览岗位图谱
  - 生成生涯报告
- 首页下半部分改为“你的规划如何形成”：
  - 材料证据 -> 能力画像 -> 岗位差距 -> 路径计划 -> 月度复盘
- 每个模块用真实 UI 片段，而不是抽象图标卡。

### 6.4 报告页改造

报告页从“配置表单 + 卡片堆叠”改成三层：

```text
顶部：报告驾驶舱
  - 当前画像
  - 已选目标
  - 总体匹配/差距/下一步
  - 生成、导入、导出动作

中部：职业路径主画布
  - 左侧目标岗位列表
  - 中间 0-12 月路线
  - 右侧关键差距与资源推荐

底部：复盘与证据库
  - 本月任务
  - 已完成证据
  - 复盘曲线
  - 下月计划调整
```

视觉组件：

- `CareerRouteCanvas`：横向路线，不再只是一张折线图。
- `TargetSignalCard`：岗位卡带公司、地点、薪资、能力差距、风险标签。
- `NextBestAction`：报告生成后最突出的下一步行动，不让用户淹没在长内容里。
- `EvidenceShelf`：展示证书、项目、竞赛、课程等可投递证据。
- `ReviewPulse`：复盘结果用脉冲/进度节点，而不是普通 textarea 卡片。

### 6.5 能力画像页改造

能力画像页应从“上传表单 + 雷达图”升级为“证据画像”：

- 上传区域做成材料工作台：简历、证书、项目、补充文本分组。
- 雷达图旁增加“证据来源热度”：每个能力维度来自哪些材料。
- 画像结果按“优势 / 缺口 / 可证明成果 / 下一步材料”四栏组织。

### 6.6 人岗匹配页改造

当前 `match.vue` 需要先正常化代码，再做视觉升级：

- 左侧筛选不再是普通表单，而是“目标意图面板”。
- 中间结果使用排名列表 + 差距条 + 标签。
- 右侧保留能力对比，但加入“为什么排在这里”的解释。
- 成功匹配后明确提示“已保存到报告可导入记录”，并展示快照保存状态。

## 7. 实施路线

### Phase 0：恢复报告链路（P0）

预计：0.5 天

- 备份数据库。
- 增加 schema doctor。
- 修复 / 执行 Alembic 迁移。
- 后端 report/match 路由增加普通异常兜底与日志。
- 前端匹配历史弹窗增加错误态。
- 验证 `mizi` 匹配记录与报告生成。

### Phase 1：类型与 API 边界

预计：1 天

- 新增 `types/job.ts/profile.ts/match.ts/report.ts/settings.ts`。
- 新增 report/match Zod schema。
- 修改 `useApi` 命名，标记 legacy code envelope。
- 把 report 页相关 `any` 先替换为类型。

### Phase 2：报告页拆分

预计：1-2 天

- 抽 composables。
- 抽 report 子组件。
- `report.vue` 控制在 120 行以内。
- 保持现有功能和 E2E 通过。

### Phase 3：Header / match / profile 整理

预计：1-2 天

- 拆 `AppHeader`。
- 重写 `match.vue` 为可维护结构。
- 抽 `profile.vue` 中上传、画像展示、历史弹窗。

### Phase 4：视觉升级

预计：2-3 天

- 首页职业路径地图。
- 报告页职业驾驶舱。
- 能力画像证据化。
- 人岗匹配解释化。
- 增加视觉回归截图检查。

### Phase 5：测试与 CI

预计：0.5 天

- CI 增加 `dev` / `suilli` push 触发。
- 增加报告链路 E2E：
  - 匹配历史加载成功。
  - 匹配历史加载失败显示错误态。
  - 手动选择目标后生成报告。
- 增加后端 schema doctor 测试。

## 8. 验收清单

功能：

- `mizi` 报告页能看到已有匹配记录。
- 从匹配记录导入目标后能生成报告。
- 手动搜索目标后能生成报告。
- 后端 500 不再以裸错误暴露给前端。

工程：

- `report.vue <= 120` 行。
- `AppHeader.vue <= 80` 行或仅作为 shell。
- `frontend/app` 中 `any <= 40`。
- 新接口不再新增 `CodeEnvelope`。
- 所有新增组件有清晰 props/emit 类型。

视觉：

- 首页首屏不再像模板落地页，而是展示真实职业路径体验。
- 报告页第一屏能回答“我当前状态、目标、下一步”。
- 能力画像能看到证据来源，而不只是分数。
- 人岗匹配能解释排名，而不只是列结果。

测试：

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm test:e2e
pnpm build

cd ..\backend
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

## 9. 不建议的做法

- 不建议直接删除 `CodeEnvelope`，会破坏 `profile/personality`。
- 不建议只在前端吞掉 500，根因是数据库迁移缺失。
- 不建议继续把报告页所有新功能塞进 `report.vue`。
- 不建议用大面积装饰渐变和纯图标堆砌解决美观问题；应该把视觉资源绑定到职业路径、能力证据和行动计划。
- 不建议先大改 UI 再修报告接口。当前 P0 是链路可用性。

## 10. 推荐下一步

按顺序执行：

1. 修复数据库迁移状态，让 `/api/match/history` 和 `/api/report/generate` 恢复。
2. 增加 schema doctor，避免以后代码升级但数据库没升级。
3. 把报告页先拆出类型和 composables。
4. 再做报告页视觉驾驶舱。
5. 最后统一推广到首页、画像、匹配页。
