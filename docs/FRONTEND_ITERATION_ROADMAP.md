# PathFy-Uni 前端迭代更新总方案

更新日期：2026-08-15  
适用前端：`frontend/`（Nuxt 4 + Vue 3 + Nuxt UI）  
参考实现：`frontend.old/`（Astro 5 + Svelte 5，只读归档）  
适用分支：`suilli` 及后续集成分支  
预计投入：单人约 22～32 人日；两名前端并行约 3～4 周完成主体  

> 本文是全前端迭代总路线，覆盖架构、功能回迁、视觉体验、性能、测试和发布。  
> `docs/FRONTEND_REPORT_REFACTOR_UX_PLAN.md` 继续作为报告故障与报告视觉设计的专题记录；若两者出现进度或指标冲突，以本文的当前基线和阶段门禁为准。

## 1. 执行摘要

### 1.1 核心决策

1. **继续以 Nuxt/Vue 前端为唯一正式实现，不回退 Astro/Svelte。**
2. **不做第二次整体重写。**采用“契约收敛 → 页面拆分 → 功能回迁 → 视觉升级 → 性能治理”的增量路线。
3. **从 `.old` 迁移产品能力，不迁移旧架构。**重点吸收旧版报告解释层、匹配分层、完整性格报告和岗位助手保存能力。
4. **图谱管理绝不回迁旧直接写接口。**旧 `/api/graph/import-jobs` 等接口已退役，正式前端只使用任务队列、变更审阅和确认写入模型。
5. **先稳数据边界，再继续扩展 UI。**所有新页面逻辑应只消费经过 adapter/schema 归一化的数据。
6. **保留现有路由和本地缓存兼容。**迭代过程中不改变用户可见 URL，不无提示丢弃画像、匹配和报告工作区缓存。

### 1.2 最终目标

把当前“可运行的 Nuxt SPA”升级成：

- 业务链路完整：画像 → 岗位 → 匹配 → 报告 → 月度复盘连续可用；
- 结果可解释：用户能理解为什么匹配、差距在哪里、下一步做什么；
- 工程可维护：页面只负责编排，类型、API、状态和视图职责清晰；
- 性能可控：图表按需加载，公开页面具备真实静态 HTML；
- 发布可信：类型、单测、E2E、契约、可访问性和性能预算形成门禁；
- 回滚可靠：每个阶段独立可部署，不依赖切回已经不兼容后端的 `.old`。

## 2. 当前基线

以下数据来自 2026-08-15 当前工作树，不是最初迁移提交的数据。

### 2.1 工程与构建基线

| 指标 | 当前值 | 说明 |
|---|---:|---|
| Nuxt 页面文件 | 16 | 包含用户端和图谱管理端 |
| Vue 组件文件 | 30 | 报告、Header 已开始拆分 |
| `frontend/app` 文件数 | 61 | `.vue/.ts/.css` |
| `frontend/app` 代码行数 | 约 6,943 | 不含生成物 |
| 显式 `any` | 约 112 | 类型检查能通过，但领域边界仍偏弱 |
| `report.vue` | 479 行 | 已从旧规划记录的约 858 行下降，但仍过重 |
| `AppHeader.vue` | 275 行 | 已有子组件，Shell 仍未完成 |
| 静态产物总量 | 约 1.66 MB | `.output/public` 原始字节 |
| JavaScript 总量 | 约 1.39 MB | 旧版约 0.36 MB |
| CSS 总量 | 约 234 KB | 旧版约 129 KB |

### 2.2 已通过的验证

```text
pnpm typecheck   通过
pnpm test        1 个测试文件、3 个测试通过
pnpm test:e2e    20 个测试通过
pnpm generate    成功生成静态 SPA 产物
```

需要正确理解这些结果：

- 当前工程具备稳定的基础门禁；
- 单元测试数量仍少；
- Playwright 主要 Mock `/api/**`，尚不能替代真实 Flask/MySQL/Neo4j 集成测试；
- `ssr: false` 导致生成 HTML 仍是客户端空壳，`generate` 成功不等于首页静态内容已经生成。

### 2.3 已经完成或部分完成的旧规划任务

| 原规划项 | 当前状态 | 后续处理 |
|---|---|---|
| 报告页组件拆分 | 部分完成 | 页面逻辑和状态仍需进入 composable |
| Header 拆分 | 部分完成 | Nav/MobileMenu 已拆，Shell/用户动作仍耦合 |
| 报告类型补强 | 部分完成 | 已有报告类型，仍存在 `any` 与运行时猜字段 |
| 匹配历史错误态 | 部分完成 | 有 Toast，但弹窗内可恢复错误态仍不足 |
| 图谱管理任务化 | 已完成主体 | 继续补类型、状态和审阅测试 |
| CI E2E | 已完成 | 下一步增加集成、失败路径和性能门禁 |
| 报告驾驶舱视觉 | 部分完成 | 已有摘要/目标/发展线，旧版解释深度尚未恢复 |

## 3. 页面级能力矩阵

### 3.1 当前版本与旧版取舍

| 模块 | 当前 Nuxt 优势 | `.old` 值得迁移的能力 | 迭代决策 |
|---|---|---|---|
| 首页 | 产品入口统一、真实工作台预览、响应式更稳定 | 更轻的 Islands、部分手工动画气质 | 保留当前结构，恢复静态 HTML 和轻量动效 |
| 登录/注册 | API、认证状态和跳转集中 | 动画角色、强视觉识别 | 动画作为懒加载装饰层，不迁移 800 行 AuthCard |
| 能力画像 | 历史画像恢复、多材料展示、统一组件 | 旧版详细分析结构较完整 | 增加证据到维度映射，继续拆分组件 |
| 性格测试 | 流程简洁、移动端清晰 | 职业倾向、职场关系、压力应对、成长建议、综合报告 | P1 恢复完整结果展示 |
| 岗位探索 | 列表与助手同屏、详情组件复用 | 保存 AI 回答、更细的会话反馈 | P1 恢复保存能力，补消息状态 |
| 人岗匹配 | 统一筛选、缓存、双雷达 | 智能 Top5/完整列表分层、岗位详情、历史摘要、快照说明 | P0/P1 重构并恢复解释层 |
| 职业图谱 | 当前岗位/目标岗位选择统一，后端路径接口兼容 | 少量路径卡片表现形式 | 保留当前，补类型与空/错状态 |
| 生涯报告 | API 链路完整、组件拆分已开始 | 月度节点、动态调整原因、岗位切换、趋势详情、全屏画布 | P0/P1 重点恢复，但必须组件化 |
| 个人中心 | 偏好、隐私、主题和推荐数量完整 | 无关键缺口 | 继续拆分与表单验证 |
| 图谱管理 | 任务队列、审阅确认、设置版本全面领先 | 旧版接口不可再用 | 只优化当前实现，不参考旧操作模型 |

### 3.2 明确不回迁的旧实现

- `document.getElementById` 驱动的业务状态；
- `innerHTML` 拼接分析结果；
- 自定义 DOM 事件同步雷达图；
- 4000 行级单组件；
- 每个 API 模块各自拼 Bearer Header；
- Astro ClientRouter 换页后的重复初始化补丁；
- 直接写入、清空或同步 Neo4j 的旧前端按钮；
- 同时维护 `package-lock.json` 与 `pnpm-lock.yaml` 的依赖方式。

## 4. 目标架构

### 4.1 分层结构

```text
frontend/app/
├── pages/                    # 路由编排：标题、权限、布局、组合领域组件
├── components/
│   ├── ui/                   # PathFy 轻量领域无关组件
│   ├── app-header/
│   ├── profile/
│   ├── personality/
│   ├── jobs/
│   ├── match/
│   ├── graph/
│   ├── report/
│   └── graph-admin/
├── composables/
│   ├── api/                  # 统一 HTTP 与领域 adapter
│   ├── auth/
│   ├── profile/
│   ├── match/
│   ├── report/
│   └── graph-admin/
├── schemas/                  # 仅在外部数据边界使用 Zod
├── types/                    # 领域类型，不放业务副作用
├── utils/                    # 纯函数、format、normalizer、cache migration
└── assets/css/               # Token、基础布局、少量全局模式
```

### 4.2 单向数据流

```text
后端响应
  -> useApi（传输、认证、401、通用错误）
  -> domain adapter（ok/code 兼容、字段归一化）
  -> Zod schema（高风险边界校验）
  -> typed composable（状态、缓存、副作用）
  -> page（组合）
  -> component（纯展示或局部交互）
```

禁止反向依赖：

- 组件不能直接解释两种 API envelope；
- 页面不能自己解析 localStorage JSON；
- 类型文件不能导入 composable；
- 通用组件不能依赖报告或匹配领域；
- 展示组件不能自行决定认证跳转。

### 4.3 状态管理决策

当前阶段不引入 Pinia。优先继续使用 Nuxt `useState` 与领域 composable，原因是全局共享状态目前主要只有认证和外观。

状态分为三类：

| 类型 | 存放位置 | 示例 |
|---|---|---|
| 全局会话态 | `useState` | token、用户、主题偏好 |
| 页面工作态 | 领域 composable | 报告配置、当前匹配、图谱筛选 |
| 可恢复持久态 | 版本化 localStorage adapter | 画像快照、匹配结果、报告工作区 |

只有出现三个以上跨路由共享且需要复杂派生的领域状态时，再单独评估 Pinia。

## 5. 全局完成标准

### 5.1 工程指标

| 指标 | 当前 | 最终门槛 |
|---|---:|---:|
| `frontend/app` 显式 `any` | 约 112 | ≤ 35 |
| `pages/report.vue` | 479 行 | ≤ 150 行 |
| `pages/match.vue` | 20 个压缩行 | 正常格式且 ≤ 180 行 |
| `AppHeader.vue` | 275 行 | ≤ 100 行 |
| 单个业务组件 | 最高 337 行以上 | 原则 ≤ 250 行，超出需说明 |
| 前端单元测试 | 3 个 | 核心 normalizer/cache/contract ≥ 30 个 |
| E2E | 20 个 Mock 场景 | 关键成功/失败路径 ≥ 35 个 |

行数是架构告警，不是机械 KPI。若一个组件超过门槛但职责单一、类型清晰、测试充分，可在代码审查中记录例外。

### 5.2 性能预算

| 指标 | 目标 |
|---|---|
| 构建后 JS 原始总量 | 从约 1.39 MB 降至 ≤ 1.0 MB |
| 首页初始 JS（gzip） | ≤ 220 KB |
| 最大业务路由增量 chunk（gzip） | ≤ 120 KB，图表 vendor 单独记录 |
| LCP | 移动端模拟网络 ≤ 2.5 秒 |
| CLS | ≤ 0.1 |
| INP | ≤ 200 ms |
| 图表 | 离开相关路由时不预加载 ECharts 业务模块 |

### 5.3 质量标准

- 所有新 API 字段有领域类型；
- 所有新接口只接受 `ok` envelope；
- legacy `code` envelope 只能出现在 profile/personality adapter；
- 所有 Modal、Drawer、菜单支持键盘关闭和焦点恢复；
- 重要颜色信息同时有文字或图形标识；
- 不在 localStorage 保存简历原文、OCR 全文或密钥；
- 每个迭代结束都能独立部署和回滚。

## 6. 迭代路线总览

| 迭代 | 主题 | 优先级 | 预计投入 | 依赖 |
|---|---|---:|---:|---|
| Iteration 0 | 基线冻结与回归护栏 | P0 | 1～2 人日 | 无 |
| Iteration 1 | 类型、API adapter 与缓存边界 | P0 | 3～4 人日 | I0 |
| Iteration 2 | 报告页彻底拆分与解释能力恢复 | P0 | 5～7 人日 | I1 |
| Iteration 3 | 匹配、岗位、性格功能回迁 | P1 | 4～6 人日 | I1，可与 I2 后半并行 |
| Iteration 4 | 画像、Header、账户组件化 | P1 | 3～4 人日 | I1 |
| Iteration 5 | Career Cockpit 视觉系统 | P1 | 3～5 人日 | I2～I4 主体完成 |
| Iteration 6 | 渲染与性能治理 | P1 | 2～4 人日 | I5 可部分并行 |
| Iteration 7 | 测试、安全、可访问性与发布 | P0/P1 | 2～4 人日 | I0～I6，已完成收口 |

## 7. Iteration 0：基线冻结与回归护栏

目标：确保后续重构可以证明“没有丢功能”，并建立可重复的数字基线。

### 7.1 工作项

#### FE-0001：建立页面能力清单

为以下页面记录成功、空、加载、失败、未登录五种状态：

- `/profile`
- `/personality`
- `/jobs`
- `/match`
- `/graph`
- `/report`
- `/account`
- `/graph-admin/**`

输出到 `docs/smoke-test.md`，每个状态标注触发方式和期望行为。

#### FE-0002：建立构建体积快照

新增只读脚本或 CI 步骤，输出：

- JS/CSS/HTML 总量；
- 最大 10 个 chunk；
- 首页初始资源；
- ECharts 所在 chunk；
- 与主分支预算差异。

建议文件：

```text
frontend/scripts/report-bundle-size.mjs
frontend/bundle-budget.json
```

初期只报告不阻断；Iteration 6 后转为超预算失败。

#### FE-0003：补关键失败态 E2E

最低补充：

- `/api/match/history` 失败时弹窗显示可读错误；
- `/api/report/generate` 失败后已选目标仍保留；
- `/api/profile/resumes` 失败时页面不崩溃；
- 401 自动清理认证并带 redirect 返回登录；
- 管理员接口 403 时不进入管理页。

#### FE-0004：保存视觉基线

保存桌面 1440×900、平板 768×1024、手机 390×844 三档截图：

- 首页；
- 画像结果；
- 匹配结果；
- 报告已生成；
- 图谱管理 Dashboard。

### 7.2 验收门禁

- 当前 20 个 E2E 继续通过；
- 新增至少 5 个失败路径测试；
- 能生成机器可读的 bundle 报告；
- 所有核心页面具有可复用 Mock fixture；
- 不改变生产行为。

### 7.3 实施记录（2026-08-15）

状态：已完成。

- `docs/smoke-test.md` 已补齐核心页面成功、空、加载、失败、未登录状态矩阵与发布记录模板；
- 新增 `frontend/scripts/report-bundle-size.mjs` 和 `frontend/bundle-budget.json`，CI 在静态生成后上传机器可读报告；Iteration 0 只报告，暂不因超预算阻断；
- 新增 6 条失败路径 E2E，覆盖匹配历史、报告生成、画像列表、401、普通用户越权和管理员接口 403；
- 新增共享稳定 Mock fixture，供失败测试与视觉基线复用；
- 已保存首页、画像、匹配、报告、图谱管理在 1440×900、768×1024、390×844 下的 15 张全页截图；
- 验证结果：`typecheck`、3 个单元测试、26 个 E2E、静态生成、视觉基线采集和当前预算检查全部通过；
- 当前体积基线：公共产物 1,663,930 B，JS 1,386,221 B，CSS 233,551 B，最大 JS chunk 483,645 B。

## 8. Iteration 1：类型、API adapter 与缓存边界

目标：停止页面直接猜测字段，为后续拆分建立稳定契约。

### 8.1 领域类型

新增或拆分：

```text
frontend/app/types/capability.ts
frontend/app/types/job.ts
frontend/app/types/profile.ts
frontend/app/types/personality.ts
frontend/app/types/match.ts
frontend/app/types/report.ts
frontend/app/types/settings.ts
frontend/app/types/graph-task.ts
```

必须建模的核心对象：

- 八维能力 Key、分数、差距；
- JobCard、JobDetail、JobTarget、JobOption；
- ProfileSummary、ProfileDetail、材料与详细分析；
- PersonalityQuestion、PersonalityResult；
- MatchPreview、MatchCandidate、MatchHistorySummary/Detail；
- Report、TargetInsight、PlanByTarget、Review、DevelopmentLine；
- SystemSettings、UserPreferences；
- GraphTask、GraphChangeGroup、GraphGuard、GraphStats。

### 8.2 API adapter

目标目录：

```text
frontend/app/composables/api/useProfileApi.ts
frontend/app/composables/api/usePersonalityApi.ts
frontend/app/composables/api/useMatchApi.ts
frontend/app/composables/api/useReportApi.ts
frontend/app/composables/api/useJobsApi.ts
frontend/app/composables/api/useGraphTasksApi.ts
frontend/app/composables/api/useSettingsApi.ts
```

规则：

1. `useApi.request()` 只负责 HTTP；
2. `api.ok<T>()` 用于正式接口；
3. 将 `api.code<T>()` 重命名为 `api.legacyCode<T>()`；
4. profile/personality 页面禁止直接引用 `CodeEnvelope`；
5. adapter 返回内部模型，不返回后端 envelope；
6. 401、网络错误、非 JSON 错误保持统一消息结构；
7. 后端 validation error 可携带字段路径，不全部压成一个字符串。

### 8.3 Zod 边界

优先校验高风险结构：

- 匹配预览与历史详情；
- 报告生成、报告详情、复盘结果；
- 图谱任务详情和变更集；
- 用户偏好和系统设置。

不要求给所有内部对象套 Zod。简单列表可以先做 TypeScript normalizer，避免运行时校验体积失控。

### 8.4 缓存升级

当前缓存键继续兼容：

```text
career_profile_portrait_v1_<user>
career_pj_match_v1_<user>
career_personality_v1_<user>
career_report_workspace_v1_<user>
```

新增统一缓存层：

```text
frontend/app/utils/cache/profile-cache.ts
frontend/app/utils/cache/match-cache.ts
frontend/app/utils/cache/personality-cache.ts
frontend/app/utils/cache/report-cache.ts
```

每份缓存包含：

```ts
interface CacheEnvelope<T> {
  schemaVersion: number
  savedAt: number
  userId: number | 'guest'
  data: T
}
```

迁移规则：

- 能读取旧 `v: 1` 结构；
- 迁移成功后写新格式；
- 损坏缓存只清理对应键，不影响认证；
- 缓存恢复失败不得覆盖服务器最新结果；
- 报告快照保留必要展示字段，不保存材料全文。

### 8.5 验收门禁

- 页面代码不再直接声明 `CodeEnvelope<any>`；
- profile/personality 只有 adapter 知道 legacy envelope；
- 报告和匹配相关 `any` 数量至少下降 50%；
- normalizer、schema、缓存迁移新增至少 15 个单测；
- 旧 localStorage 数据仍可恢复；
- 所有既有 E2E 继续通过。

### 8.6 实施记录（2026-08-15）

状态：已完成。

- 已按能力、岗位、画像、性格、匹配、报告、设置和图谱任务拆分领域类型；
- 已建立 7 个 API adapter，`useApi` 统一提供 HTTP、正式 envelope、legacy envelope 与字段级错误；
- profile、personality、match、report 页面已改为消费 adapter，页面不再解析后端 envelope；
- 匹配、报告、图谱任务与设置已在 adapter 边界应用 Zod 校验，普通列表经 normalizer 兼容；
- profile、match、personality、report 缓存已升级至 schemaVersion 2，并兼容 v1 数据、用户隔离和损坏键清理；报告缓存会移除材料全文；
- 新增 21 个 contracts/cache 单元测试，覆盖 envelope、normalizer、四类 v1 迁移、版本化读写与损坏缓存隔离；
- 验证结果：`pnpm typecheck`、`pnpm test`、`pnpm generate` 和 26 个 E2E 均通过。E2E Mock 已收紧为仅拦截真实 `/api/` 请求，避免误拦截 `composables/api` 前端模块；开发模式首屏断言超时调整为 20 秒以覆盖冷启动预编译。

## 9. Iteration 2：报告页重构与能力恢复

目标：让 `report.vue` 成为编排页，并恢复旧版最有价值的解释和复盘交互。

### 9.1 状态拆分

```text
frontend/app/composables/report/useReportWorkspace.ts
frontend/app/composables/report/useReportTargets.ts
frontend/app/composables/report/useReportGeneration.ts
frontend/app/composables/report/useReportHistory.ts
frontend/app/composables/report/useReportReview.ts
frontend/app/composables/report/useReportPublicInfo.ts
```

职责边界：

- `Workspace`：缓存、恢复、重置和当前报告快照；
- `Targets`：手选、随机、搜索、匹配导入、主目标；
- `Generation`：生成骨架、AI enrich、进度、错误；
- `History`：列表、恢复和冲突处理；
- `Review`：模板、提交、指标、下月调整；
- `PublicInfo`：按目标加载、刷新和缓存。

### 9.2 组件目标

保留现有组件并进一步调整：

```text
ReportPageHeader.vue
ReportConfigPanel.vue
ReportMatchImportModal.vue
ReportTargetExplorerDialog.vue
ReportHistoryModal.vue
ReportSummaryCard.vue
ReportTargetsSection.vue
ReportPlanView.vue
ReportDevelopmentLines.vue
ReportReviewSection.vue
```

新增：

```text
ReportNextBestAction.vue
ReportTargetTabs.vue
ReportGapTable.vue
ReportMonthlyTimeline.vue
ReportMonthDetail.vue
ReportAdjustmentNotice.vue
ReportTrackProfile.vue
ReportEvidenceShelf.vue
```

### 9.3 从旧版恢复的能力

#### FE-0201：目标岗位切换

- 每个目标有独立计划、差距、推荐和发展线；
- 当前激活目标写入工作区缓存；
- 恢复历史报告时优先恢复原激活目标，否则使用主目标。

#### FE-0202：月度复盘节点

- 横轴固定 0～12 月；
- 计划节点与已复盘节点有不同形状和文字；
- 点击节点显示该月任务、复盘原文、实际指标和调整结果；
- 不只依赖颜色表达状态。

#### FE-0203：调整原因解释

展示：

- 是否触发自动调整；
- `replan_mode`；
- 触发指标；
- 原计划与新计划的关键差异；
- 下一月最优先动作。

#### FE-0204：赛道画像

按目标展示招聘可见度、路径宽度和资源密度，并附简短解释。公开信息失败时只影响当前目标，不阻断整份报告。

#### FE-0205：证据与行动

- 下月 action 可打卡；
- 打卡失败乐观更新必须回滚；
- 学习资源、竞赛、项目成果以不同类型标识；
- 下一步行动固定在报告首屏或目标摘要附近。

### 9.4 交互与错误处理

- 生成失败不清空画像和目标；
- enrich 失败时保留骨架，并提供重试；
- 历史导入失败在 Modal 内显示错误和重试；
- 无效 `job_id` 高亮具体目标；
- 导出 PDF 显示准备、下载、失败三态；
- 重置工作区必须二次确认；
- 页面离开前只持久化经过 schema 校验的快照。

### 9.5 验收门禁

- `pages/report.vue ≤ 150` 行；
- 页面中无直接 `$fetch`、localStorage 和 envelope 解析；
- 生成、enrich、历史、复盘、导出、行动打卡全部保留；
- 旧版五项重点能力完成：岗位切换、月度节点、调整解释、赛道画像、节点详情；
- 报告 E2E 至少覆盖 12 个成功/失败场景；
- 同一报告在刷新后能恢复到相同目标和月份；
- 图表空数据、单点和多线数据均不报错。

### 9.6 实施记录（2026-08-15）

状态：已完成。

- `pages/report.vue` 已从 503 行压缩为 8 行薄入口；页面不再包含接口调用、localStorage、envelope 解析或业务状态实现；
- 已新增 `useReportWorkspace`、`useReportTargets`、`useReportGeneration`、`useReportHistory`、`useReportReview`、`useReportPublicInfo` 六个职责明确的 composable；
- 已新增页面头部、目标岗位 Tab、下一步最佳行动、能力差距、0～12 月时间轴、月份详情、调整解释、赛道画像、证据资源架等报告组件；
- 每个目标岗位现在具有独立的差距、下月行动、阶段计划、发展线、赛道画像和推荐证据；切换岗位会同步切换完整工作区；
- 当前激活岗位、选中月份和配置折叠状态已进入 schemaVersion 2 缓存，并兼容旧版 `activeJobId`、`selectedCanvasMonth`、`configRailCollapsed` 字段；刷新和历史恢复会优先保留有效焦点；
- 月度时间轴固定展示 0～12 月，使用文字、圆形和菱形共同区分复盘与计划节点；月份详情展示复盘原文、量化指标、调整任务和触发指标；
- 计划调整区展示自动调整状态、`replan_mode`、触发项、关键变化和下一月优先行动；公开信息失败仅影响当前岗位卡片；
- 下月行动采用乐观更新，接口失败时回滚；AI enrich 失败保留报告骨架并支持重试；历史加载、PDF 导出和清空工作区均具有明确失败/确认状态；
- 报告专用 E2E 新增 14 个成功/失败场景，覆盖生成、恢复、岗位切换、月份详情、调整解释、公开信息、行动回滚、历史重试、AI enrich、PDF、重置和复盘提交；
- 验证结果：`pnpm typecheck`、23 个单元测试、40 个 E2E、静态生成、包体积预算和桌面/平板/手机视觉基线均通过；当前公共产物 1,659.4 KiB，JS 1,386.0 KiB，CSS 230.2 KiB。

## 10. Iteration 3：匹配、岗位和性格功能回迁

### 10.1 人岗匹配

重写 `pages/match.vue` 的压缩结构，新增：

```text
frontend/app/composables/match/useMatchWorkspace.ts
frontend/app/components/match/MatchIntentPanel.vue
frontend/app/components/match/MatchResultList.vue
frontend/app/components/match/MatchCandidateCard.vue
frontend/app/components/match/MatchComparisonPanel.vue
frontend/app/components/match/MatchHistoryModal.vue
frontend/app/components/match/MatchSnapshotStatus.vue
```

恢复/新增能力：

- “智能推荐 Top 5”和“完整粗排结果”分区；
- 每个岗位能打开统一 `JobDetailModal`；
- 展示匹配分、差距、优势、风险和推荐理由；
- 双雷达正确使用岗位八维要求，而不是猜测 `selected.scores`；
- 历史记录展示关键词、地点、策略、是否 AI 精排、结果数；
- 历史恢复后同步筛选条件和画像；
- 成功匹配后显示“快照已保存，可在报告中导入”；
- 落库失败时显示 `snapshot_warning`，不能假装保存成功。

### 10.2 岗位探索与助手

新增：

- AI 消息发送失败后的重试；
- “保存本次回答/筛选结果”；
- 保存中、已保存、保存失败状态；
- 会话标题和最近更新时间；
- 结果被 AI 筛选替换时提供“回到普通岗位列表”；
- 岗位卡和详情使用同一 Job normalizer。

`saveMessage` 已存在于 API composable，优先恢复 UI 和状态，不新增后端接口。

### 10.3 性格测试

新增结果组件：

```text
PersonalityHero.vue
PersonalityDimensions.vue
PersonalityStrengths.vue
PersonalityCareerTendency.vue
PersonalityWorkplaceRelations.vue
PersonalityGrowthAdvice.vue
PersonalityStressResponse.vue
PersonalityRecommendedJobs.vue
```

恢复旧版字段时必须经 normalizer，兼容后端字段缺失。没有数据的区块不显示空白大卡，而是降级到摘要。

测试过程中保存：

- 当前题号；
- 已答选项；
- 题目版本或题目 ID 集；
- 保存时间。

题目集发生变化时不得把旧答案错误提交到新题目。

### 10.4 验收门禁

- `match.vue` 正常格式化且 ≤ 180 行；
- 匹配相关不再使用无注释 `any`；
- Top5、完整列表、岗位详情和历史恢复均有 E2E；
- 岗位助手保存能力可见且失败可恢复；
- 性格结果至少恢复五类详细解释；
- 测试中途刷新能恢复，题目版本变化能安全重置。

### 10.5 实施记录（2026-08-15）

状态：已完成。

- `pages/match.vue` 已由压缩模板重构为 43 行薄入口，筛选、请求、缓存、历史恢复和选择状态集中到 `useMatchWorkspace`；匹配模块中不再出现直接 `$fetch`、localStorage 或无类型 `any`；
- 已新增 `MatchIntentPanel`、`MatchResultList`、`MatchCandidateCard`、`MatchComparisonPanel`、`MatchHistoryModal`、`MatchSnapshotStatus`，智能 Top 5 与完整粗排结果独立展示；
- AI 精排结果恢复匹配分、推荐理由、优势、缺口与风险；完整结果保留粗排依据。两类结果均可打开统一 `JobDetailModal`，对比雷达使用标准化后的岗位八维要求；
- 匹配历史现在展示画像、关键词、地点、策略、AI 精排状态、结果数和时间；恢复历史会同步筛选条件、可用画像和完整结果；原画像失效时给出明确说明；
- 匹配成功显示快照已保存且可供报告导入；后端返回 `snapshot_warning` 时改为可见警告，不再误报保存成功；
- 岗位 API 已统一标准化普通列表、AI 筛选结果、会话与消息；助手支持失败问题重试、回答与筛选结果保存，以及保存中、已保存、失败重试三态；
- 岗位助手会话显示标题和最近更新时间；AI 替换列表后显示结果来源与数量，并提供“返回普通岗位列表”；
- 性格结果已拆为八个独立组件，恢复四维解析、核心优势、职业倾向、职场关系、成长建议、压力应对、岗位推荐和职业建议；缺少数据的区块不渲染空卡片；
- 性格测试缓存新增题目 ID 顺序签名与保存时间；相同题集刷新后恢复当前题号和答案，题集变化时清空旧进度并阻止旧答案进入新题库；
- 新增 3 个单元测试和 8 个专项 E2E，覆盖 Top 5/完整列表/详情/历史/快照警告、岗位结果替换/保存/失败重试、性格续答/题库变化/详细结果；
- 验证结果：`pnpm typecheck`、26 个单元测试、48 个 E2E、静态生成、包体积预算和桌面/平板/手机视觉基线均通过；当前公共产物 1,679.8 KiB，JS 1,405.4 KiB，CSS 231.3 KiB。

## 11. Iteration 4：画像、Header 与账户组件化

### 11.1 能力画像

目标结构：

```text
ProfileMaterialWorkbench.vue
ProfileRadarCard.vue
ProfileScoreSummary.vue
ProfileEvidenceMap.vue
ProfileDimensionAnalysis.vue
ProfileActionPlan.vue
ProfileIndustryFit.vue
ProfileKeywordAnalysis.vue
ProfileHistoryModal.vue
```

重点能力：

- 文件按简历、证书、成绩、项目、补充材料显示类型；
- 上传前显示数量、大小、允许格式和删除动作；
- 画像维度显示证据来源，而不只显示分数；
- 历史恢复明确显示画像 ID、生成时间、姓名和专业；
- 最新服务器画像优先于陈旧本地缓存；
- OCR/分析失败时保留用户填写的姓名、专业和补充文本；
- 不在浏览器缓存上传文件内容。

### 11.2 Header

目标结构：

```text
AppHeader.vue                 # Shell
app-header/AppBrand.vue
app-header/AppHeaderNav.vue
app-header/AppHeaderMobileMenu.vue
app-header/AppUserActions.vue
app-header/AppAppearanceActions.vue
app-header/AppLogoutConfirm.vue
```

要求：

- Header Shell 不处理复杂业务；
- 导航配置只有一个事实来源；
- 移动菜单切页后关闭；
- Logout 必须确认；
- 滚动状态通过一个 listener 管理并正确清理；
- 管理员入口只由认证状态派生；
- 键盘 Tab 顺序和焦点样式清晰。

### 11.3 个人中心

拆分账户信息、外观、匹配偏好、AI/隐私和推荐数量。使用一个 typed form model，并增加：

- 数值上下界验证；
- 未保存修改提示；
- 保存失败回滚；
- 服务端配置与本地外观偏好的合并规则说明；
- 密钥和敏感部署配置永不在前端回显。

### 11.4 验收门禁

- `AppHeader.vue ≤ 100` 行；
- `account.vue ≤ 140` 行；
- `profile.vue ≤ 160` 行；
- 上传、恢复、保存偏好均有失败态测试；
- 移动端 390px 下无横向溢出；
- Header、Modal、文件输入通过键盘基础检查。

### 11.5 实施记录（2026-08-15）

状态：已完成。

- `pages/profile.vue` 已收敛为 30 行薄入口；画像工作区拆分为 9 个展示组件与 `useProfileWorkspace`，集中管理草稿、材料、分析结果、缓存和历史恢复；
- 上传材料现在显示数量、大小、允许格式、材料分类和逐项删除动作；单文件限制 10 MB、最多 12 份，OCR/分析失败不会清空姓名、专业、补充文本或待上传材料；浏览器缓存只保存画像结果，不保存 `File` 或输入草稿；
- 画像维度补齐证据来源，历史列表明确显示画像 ID、生成时间、姓名和专业；页面初始化始终查询服务器最新画像，并以服务器结果覆盖同 ID 的陈旧本地缓存；历史加载与恢复失败均在弹窗内提供可见错误和重试入口；
- `AppHeader.vue` 已收敛为 22 行 Shell；品牌、导航、移动菜单、外观、用户操作与退出确认独立组件化，导航配置统一到 `types/navigation.ts`，滚动监听和路由切换收口至 `useHeaderController` 并在卸载时清理；管理员入口只由认证状态派生；
- `pages/account.vue` 已收敛为 21 行薄入口；账户身份、外观、匹配偏好、AI/隐私、推荐数量和保存状态拆为独立组件，`useAccountPreferences` 使用完整的 typed form model 管理加载、校验、脏状态和提交；
- 账户偏好新增整数及上下界校验、离页未保存提醒和保存失败回滚；首次加载允许本地外观偏好补全默认值，此后以服务端快照为准；提交使用已知字段白名单，未知字段、密钥和敏感部署配置不会进入 UI 或请求载荷；
- 新增 3 个单元测试和 10 个专项 E2E，覆盖材料分类/移除、OCR 失败保留草稿、历史失败重试、服务器最新画像优先、证据来源、偏好范围校验、保存失败回滚、字段白名单、390px 横向溢出和键盘操作；
- 验收行数为 Header 22、Account 21、Profile 30，全部低于门禁；`pnpm typecheck`、29 个单元测试、58 个 E2E、静态生成、包体积预算和桌面/平板/手机视觉基线均通过；当前公共产物 1,695.1 KiB（gzip 汇总 543.8 KiB），JS 1,418.1 KiB，CSS 233.9 KiB。

## 12. Iteration 5：Career Cockpit 视觉系统

目标：统一成“职业规划驾驶舱”，但不以大面积渐变和装饰动画掩盖信息结构。

### 12.1 Design Token

在 Nuxt UI Token 之上定义 PathFy 语义层：

```text
--pathfy-capability
--pathfy-gap
--pathfy-success
--pathfy-risk
--pathfy-route
--pathfy-evidence
--pathfy-surface-workbench
```

语义约定：

- 蓝/青：路径和主操作；
- 琥珀：能力缺口与待确认；
- 绿色：完成和已验证证据；
- 玫红/红：风险和不可逆操作；
- 靛蓝：岗位关系与发展路线。

颜色不可作为唯一状态信号。

### 12.2 页面统一框架

每个业务页按以下层级组织：

```text
Page Header：我在做什么
Primary View：当前最重要的信息或动作
Supporting Evidence：结果依据
Next Action：下一步
History/Settings：低频操作
```

### 12.3 首页

- 保留当前 Hero 水波和真实能力雷达预览；
- 首页首屏直接提供画像、岗位、报告三个入口；
- 用材料 → 画像 → 匹配 → 计划 → 复盘展示完整路径；
- 装饰动画遵守 `prefers-reduced-motion`；
- 登录状态下入口文案可以变为“继续画像/继续报告”。

### 12.4 报告

- 第一屏回答“当前状态、目标、最大差距、下一步”；
- 目标岗位以信号卡而非普通列表展示；
- 时间线突出当前月，历史月份可追溯；
- 复盘和证据放在计划之后，而不是埋在长页面底部；
- 允许全屏查看发展线，但关闭后恢复焦点。

### 12.5 画像与匹配

- 画像突出证据来源；
- 匹配突出排名依据；
- 雷达图只是辅助，不承担全部解释；
- 桌面三栏在平板变两栏、手机变单列；
- 重要操作保持在首屏或固定操作区。

### 12.6 验收门禁

- 三种目标视口完成视觉回归；
- 页面间标题、间距、空状态、错误态一致；
- Light/Dark 与可调 hue 均可读；
- Reduced Motion 下无强制大动画；
- 首页、画像、匹配、报告完成一次非开发人员可用性走查。

### 12.7 实施记录（2026-08-15）

状态：已完成。

- 新增 `career-cockpit.css` 语义层，完整定义能力、缺口、成功、风险、路线、证据和工作台表面 Token；Light/Dark 分别提供可读色值，能力主色继续响应用户的 `--pathfy-hue`，颜色状态同时配有图标、名称和说明文本；
- 新增 `CockpitPageHeader`、`CockpitStageRail`、`CockpitSectionHeading` 和 `CockpitSignalCard` 四个共享原语，统一页面标题、工作流、信息层级和状态信号；画像、匹配与报告均按 Primary View、Supporting Evidence、Next Action、Review 分层；
- 首页保留 Hero 水波和轻量 SVG 雷达，首屏同时提供画像、岗位、报告三个入口；登录状态下自动改为“继续”文案，并明确展示材料 → 画像 → 匹配 → 计划 → 复盘五阶段链路；全局 Reduced Motion 规则及水波自身规则会停止强制动画；
- 画像页将材料/雷达/评分留在主视图，把整体判断、材料来源和维度证据集中为 Supporting Evidence，并用语义化证据色、成功色和缺口色强化来源、优势与待提升项；桌面三栏、平板折行、手机单列均保持可读；
- 匹配页统一到相同工作流框架；结果卡明确标注“智能精排”或“八维粗排”，正文使用“排名依据”标签，双雷达只作为右侧辅助比较，不替代文字解释；
- 报告首屏新增当前状态、当前目标、最大差距和下一步四张信号卡；目标岗位标签同步显示匹配分与最大差距，时间线为当前查看月份增加文本和 `aria-current`，发展线支持全屏查看且关闭后恢复触发按钮焦点；计划之后继续展示证据、发展线和复盘区；
- 视觉基线脚本会在交互后恢复页面顶部，避免吸顶 Header 污染全页截图；除桌面 1440、平板 768、手机 390 外，新增深色 + 320° hue 基线，首页、画像、匹配、报告和图谱管理均完成目视走查；
- 新增 7 个专项 E2E，覆盖语义 Token、Light/Dark/hue、首页三入口、五阶段工作流、跨页信息层级、报告首屏四问、全屏焦点恢复、Reduced Motion 和三视口横向溢出；
- 验证结果：`pnpm typecheck`、29 个单元测试、65 个 E2E、4 组视觉基线、静态生成和包体积预算均通过；当前公共产物 1,710.0 KiB（gzip 汇总 548.4 KiB），JS 1,426.6 KiB，CSS 240.3 KiB，相比 Iteration 4 增加 14.9 KiB 公共产物，仍在预算内。

## 13. Iteration 6：渲染与性能治理

### 13.1 ECharts

当前已使用 `echarts/core` 按模块注册，但图表仍在多个高频路由出现。继续执行：

- `CapabilityRadar` 和发展线图使用异步组件；
- 进入图表可见区域或相关路由后再加载；
- 雷达图和折线图共享注册模块，避免重复 vendor；
- 首页继续使用轻量 SVG，不引入 ECharts；
- 报告无图表数据时不加载图表库；
- 记录拆分前后 chunk 差异。

### 13.2 Nuxt UI 和图标

- 确认自动导入没有把未使用的大型组件带入公共 chunk；
- 图标保持本地 bundle，清理未使用图标集合；
- 避免为了简单布局引入重量级交互组件；
- Modal、Select 等继续复用 Nuxt UI，避免重复造轮子。

### 13.3 SSR/静态 HTML 试验

当前 `ssr: false` 使公开首页只有空壳。先创建独立技术试验，不直接全局切换：

1. 开启 SSR/静态生成实验分支；
2. 验证首页、登录、注册能输出真实 HTML；
3. 验证 `.client.vue` 图表不发生 hydration mismatch；
4. 验证 localStorage 只在 client hook 中访问；
5. 验证认证中间件在服务端不错误跳转；
6. 验证 Nginx `/200.html` fallback 和直接访问动态路由；
7. 对比构建体积、LCP 和部署复杂度。

推荐结果：公开路由使用 SSR/SSG，登录后工作台保留客户端交互。若静态部署限制导致混合渲染成本过高，则保留 SPA，但必须达到首页性能预算，并在文档记录放弃 SSR 的原因。

### 13.4 请求与交互性能

- 搜索输入 debounce 250～350 ms；
- 同一路由的新请求取消旧请求；
- 岗位列表不重复请求已缓存详情；
- 报告公开信息按目标缓存并支持强制刷新；
- 长列表超过 100 项时评估虚拟化；
- Skeleton 尺寸与最终内容一致，降低 CLS。

### 13.5 验收门禁

- JS 原始总量 ≤ 1.0 MB，或有逐项豁免说明；
- 首页不加载 ECharts；
- 首页 LCP/CLS 达标；
- 直接访问所有静态路由不白屏；
- 低速网络下主要操作有明确 loading；
- CI 能检测明显的 bundle 回退。

### 13.6 实施记录（2026-08-15）

状态：已完成。

- 雷达图与发展线改为共享注册、异步组件和基于可视区的延迟挂载；无数据不实例化图表，首页继续使用 SVG，bundle 门禁确认首页不加载 ECharts；
- 搜索统一为 300 ms debounce，同路由新请求取消旧请求；岗位详情增加 5 分钟缓存，报告公开信息按目标缓存且保留强制刷新；
- Skeleton 与图表/详情最终尺寸对齐；当前列表均有 12～24 项分页或 100 项上限，完成虚拟化评估，本轮不增加虚拟滚动依赖；
- 新增独立 SSR/SSG layer，首页、登录、注册输出真实 HTML；4 条运行时测试确认无 hydration mismatch、认证中间件服务端安全且 `/200.html` 深链接 fallback 正常；主生产配置暂不全局切换；
- Hero LCP 图片补充固有尺寸和高优先级提示，E2E 对空间预留与 CLS ≤ 0.1 建立断言；
- CI 已从 bundle 报告升级为强制预算检查。当前公共产物 1,753,169 B，JS 1,462,881 B，CSS 246,130 B，首页直接初始资源 195,346 B gzip，首页不加载 ECharts；JS 超过 1 MB 的组成和硬上限记录在 `docs/FRONTEND_PERFORMANCE_BASELINE.md`；
- 详细 SSR 试验、部署约束和正式切换顺序见 `docs/SSR_SSG_SPIKE.md`。
- 验证结果：`pnpm typecheck`、32 个单元测试、66 个主 E2E、SSR/SSG 构建与 4 个 hydration/fallback E2E、静态生成和强制包体积预算全部通过。

## 14. Iteration 7：测试、安全、可访问性与发布

此迭代不是最后才开始，而是在前六个迭代中持续增加，末期统一收口。

> 状态（2026-08-15）：已完成。组件测试、自动化 WCAG 扫描、无前端 API Mock 的 Flask 浏览器集成链路、并行 CI、CSP、安全外链、危险操作确认、版本化发布与回滚手册均已落地。验收记录见 `docs/FRONTEND_ITERATION_7_ACCEPTANCE.md`。

### 14.1 测试金字塔

#### 单元测试

重点测试纯逻辑：

- `unwrapOk/legacyCode`；
- Job/Profile/Match/Report normalizer；
- Zod schema 错误路径；
- 缓存版本迁移和损坏恢复；
- 八维分数、差距和进度计算；
- 报告目标去重、最大数量和主目标选择；
- 月份节点和调整映射。

#### 组件测试

重点组件：

- MatchCandidateCard；
- ReportTargetTabs；
- ReportMonthlyTimeline；
- ReportAdjustmentNotice；
- ProfileMaterialWorkbench；
- PersonalityResult sections。

#### Mock E2E

继续覆盖 UI 状态和确定性业务流程，至少包括：

- 画像上传成功/失败/恢复；
- 性格测试中断恢复；
- 匹配成功、无结果、精排失败但粗排可用；
- 匹配历史恢复；
- 报告生成、enrich 失败、复盘、导出；
- 图谱任务创建、等待确认、拒绝和取消；
- 手机导航和主题偏好。

#### 后端集成 E2E

新增一个轻量测试环境：

- Flask 测试实例；
- 测试数据库或事务隔离数据库；
- Neo4j/LLM/OCR 使用稳定 stub；
- 前端不 Mock `/api`；
- 跑通注册 → 画像 fixture → 匹配 → 报告骨架。

集成 E2E 可以先作为 nightly 或手动 workflow，稳定后进入 PR 门禁。

### 14.2 安全

- 继续由后端执行真正授权，前端 middleware 只负责体验；
- 所有外链增加协议白名单和必要的 `rel="noopener noreferrer"`；
- 不使用未经净化的 `v-html`；
- 文件上传在前端做扩展名、MIME、大小提示，但以后端校验为准；
- 管理端危险操作必须二次确认并显示影响范围；
- localStorage JWT 风险单独立项评估 HttpOnly Cookie，不能只改前端；
- 生产 CSP 与第三方字体/资源策略写入部署文档。

### 14.3 可访问性

- 引入自动化 a11y 扫描或等效检查；
- 所有图表有标题、摘要和数据表替代；
- Dialog 打开锁定焦点，关闭恢复触发按钮；
- 自定义可点击卡片必须支持 Enter/Space；
- 表单错误与字段关联；
- 对比度满足 WCAG AA；
- 200% 缩放仍能完成核心任务。

### 14.4 CI 门禁

最终 PR 必须执行：

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm test:e2e
pnpm generate
pnpm bundle:check

cd ..\backend
python -m pytest tests/ -q
```

建议将 CI 拆为并行 Job：

- frontend-type-unit；
- frontend-e2e；
- frontend-build-budget；
- backend-test；
- integration-nightly。

## 15. 发布、灰度与回滚

### 15.1 版本切片

建议形成四个可发布里程碑：

| 版本 | 包含内容 | 发布价值 |
|---|---|---|
| `frontend-r1-contracts` | I0～I1 | 数据边界稳定，不改变主要 UI |
| `frontend-r2-report` | I2 | 报告可维护、复盘解释恢复 |
| `frontend-r3-workflows` | I3～I4 | 匹配、岗位、性格、画像完整 |
| `frontend-r4-experience` | I5～I7 | 视觉、性能和质量收口 |

### 15.2 发布步骤

1. 执行全部 CI；
2. 运行 schema doctor；
3. 在预发布环境完成 smoke test；
4. 保存旧静态产物目录；
5. 构建新 `.output/public`；
6. 原子切换 Nginx 静态目录或版本软链接；
7. 检查 `/api/health`、首页、登录、岗位、报告；
8. 观察前后端错误日志；
9. 确认无异常后清理超过保留期的旧产物。

### 15.3 回滚原则

- 回滚到上一版 Nuxt 构建产物或 Git Tag；
- 不把 `frontend.old` 当生产回滚方案，因为图谱管理接口已经不兼容；
- 数据库迁移必须向前兼容上一版前端；
- localStorage 新格式必须保留旧读取路径至少两个发布版本；
- 新组件上线不应要求立即删除旧字段。

## 16. 风险清单

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---:|---:|---|
| 报告历史 JSON 形态多版本 | 高 | 高 | normalizer + schema + fixture 回归 |
| 重构期间功能悄然缩水 | 中 | 高 | I0 能力矩阵、旧版对照、E2E 门禁 |
| SSR 切换造成 hydration 问题 | 中 | 中 | 独立 Spike，不与业务重构同批合并 |
| ECharts 拆包收益不足 | 中 | 中 | 构建分析后再决定异步边界 |
| 本地缓存污染新页面 | 高 | 中 | 版本化 cache adapter 和安全迁移 |
| 视觉升级扩大范围 | 高 | 中 | I5 必须在业务拆分完成后，按页面验收 |
| 后端双 envelope 长期存在 | 高 | 中 | adapter 隔离，禁止新接口扩散 legacy |
| Mock E2E 掩盖真实集成问题 | 高 | 高 | 增加 Flask 集成 E2E 和发布 smoke |
| 管理端误操作图谱 | 低 | 高 | 保持任务审阅、二次确认和锁机制 |
| `.old` 被误当可部署前端 | 中 | 高 | README、CI、部署文档持续标记只读 |

## 17. Backlog 优先级

### P0：必须先完成

- FE-0001 页面能力清单；
- FE-0003 关键失败态 E2E；
- FE-0101 领域类型；
- FE-0102 profile/personality legacy adapter；
- FE-0103 匹配/报告 schema 与 normalizer；
- FE-0104 缓存迁移；
- FE-0201 报告 composable 拆分；
- FE-0202 报告历史、生成、复盘错误态；
- FE-0301 `match.vue` 正常化和快照状态；
- FE-0701 Flask 集成链路。

### P1：主体体验

- 报告月度节点和调整解释；
- 匹配 Top5/完整列表分层；
- 岗位助手保存回答；
- 完整性格报告；
- 画像证据映射；
- Header/Account/Profile 拆分；
- ECharts 懒加载；
- 公开首页静态 HTML；
- 可访问性扫描和视觉回归。

### P2：增强项

- 登录页轻量动画角色；
- 长列表虚拟化；
- 更完整的证据库；
- 前端错误遥测；
- HttpOnly Cookie 跨端改造；
- 个性化首页继续任务入口。

## 18. 推荐执行顺序

单人执行：

```text
I0 -> I1 -> I2 -> I3 -> I4 -> I5 -> I6 -> I7 收口
```

两名前端并行：

```text
共同完成 I0/I1
  ├─ A：I2 报告
  └─ B：I3 匹配/岗位/性格
合并后共同完成 I4/I5
A：I6 性能；B：I7 测试与可访问性
最后共同发布验收
```

后端配合点：

- 固化报告、匹配、设置和图谱任务响应契约；
- 提供集成测试 fixture/stub；
- legacy envelope 迁移；
- HttpOnly Cookie 可行性；
- 性格和画像详细字段的稳定命名。

## 19. 每次迭代的 Definition of Done

一个工作项只有同时满足以下条件才算完成：

- 代码职责符合目标分层；
- 新增类型没有用 `any` 绕过；
- 成功、空、加载、失败和权限状态都有明确表现；
- 单元/组件/E2E 测试与风险相匹配；
- `typecheck/test/test:e2e/generate` 通过；
- 移动端、深色模式和键盘操作已检查；
- 体积没有无说明突破预算；
- 文档、smoke test 或 API 契约已同步；
- 可以通过上一版静态产物回滚；
- 没有修改 `frontend.old`。

## 20. 第一批建议任务

建议下一个开发周期直接领取以下任务，不先做大面积视觉改造：

1. 建立 Match/Report/Profile 领域类型和 normalizer；
2. 将 profile/personality 的 legacy envelope 收进 adapter；
3. 为四种 localStorage 工作区增加版本化读取和迁移测试；
4. 把 `report.vue` 的历史、生成、复盘、公开信息拆为 composable；
5. 把 `match.vue` 改回可读格式并展示快照保存状态；
6. 增加匹配历史失败、报告生成失败、401 redirect E2E；
7. 加入 bundle 报告脚本，记录 ECharts 和公共 chunk 基线。

完成这批任务后，再开始报告月度画布和完整性格结果回迁，整体风险最低。
