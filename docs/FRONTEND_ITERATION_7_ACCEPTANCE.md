# Frontend Iteration 7 验收记录

更新日期：2026-08-17  
结论：阶段 7 代码与工程体系已完成，项目进入 `frontend-r4-experience` 发布候选状态。

## 1. 已交付

### 测试

- 单元测试覆盖契约、normalizer、缓存迁移、安全外链和上传预检；
- 组件测试覆盖 MatchCandidateCard、ReportTargetTabs、ReportMonthlyTimeline、ReportAdjustmentNotice、ProfileMaterialWorkbench 和 Personality 结果区；
- Mock E2E 保留成功、空态、失败、恢复、移动端和管理端流程；
- `tests/e2e/accessibility.spec.ts` 使用 axe 扫描首页明暗主题、画像、匹配和报告，阻断 critical/serious 问题；
- `tests/integration/flask-workflow.spec.ts` 不拦截 `/api`，经 Nuxt 代理访问 Flask 测试实例，跑通注册、画像、匹配和报告骨架；
- Flask 集成实例使用进程内测试数据，并为 Neo4j、LLM、OCR 提供确定性结果。

### 安全

- 外链统一使用 `safeExternalUrl`，只允许绝对 `http/https`，新窗口链接带 `noopener noreferrer`；
- 全项目无 `v-html`；
- 画像材料预检扩展名、MIME、10MB 大小和 12 份数量，界面明确以后端校验为准；
- 图谱整单应用显示 revision 与影响摘要，危险任务需输入确认短语；排队任务取消增加二次确认；
- Nginx 模板加入 CSP、Referrer-Policy、nosniff、DENY frame 和权限策略；
- HttpOnly Cookie 迁移边界已写入发布手册，保留为跨端专项，不伪装成前端已解决。

### 可访问性

- 修复主题主色、语义成功/警告色和工作台色在明暗背景下的 WCAG AA 对比度；
- 匹配候选卡改为两个独立原生按钮，消除嵌套交互；
- 报告目标标签支持左右方向键；时间轴使用正确的 ARIA group 语义；
- 文件输入具有明确可访问名称，认证表单使用 Zod schema 关联字段错误；
- 雷达图和发展线图包含标题、文字摘要、ECharts aria 描述及可展开数据表；
- 640px 视口作为 1280px 页面 200% 缩放等效检查，无横向溢出且核心按钮可操作。

### CI、发布与回滚

- CI 拆分为 `backend-test`、`frontend-type-unit`、`frontend-build-budget`、`frontend-e2e` 和 `integration-nightly`；
- 失败时上传 Playwright 诊断产物，构建任务保留静态产物和 bundle report；
- 生产配置使用 `frontend-current` 软链接，支持版本化产物原子切换；
- `docs/FRONTEND_RELEASE_RUNBOOK.md` 定义发布准入、上线检查、回滚判定和保留策略；
- `frontend.old` 明确为只读参考，不再描述为紧急回退方案。

## 2. 验证结果

| 检查 | 结果 |
|---|---|
| `pnpm typecheck` | 通过 |
| `pnpm test` | 40 项通过（阶段收口时） |
| axe accessibility E2E | 3 项通过 |
| Flask integration E2E | 1 条完整链路通过 |
| 完整 Mock/可访问性 E2E | 70 项通过 |
| SSR/SSG E2E | 4 项通过 |
| `pnpm generate` / `bundle:check` | 通过；JS 1,472,400 B，首页 195,592 B gzip，首页未加载 ECharts |
| 后端 pytest | 120 项通过，3 条既有依赖/测试密钥警告 |

最终全量 E2E、静态生成、bundle budget、SSR/SSG 和后端测试结果以本次收尾最后一次命令为准；如数字变化，应更新本表而不是沿用阶段中间值。

## 3. 不属于阶段 7 已完成范围

- JWT 从 localStorage 迁移到 HttpOnly Cookie；
- 生产错误遥测平台；
- 大于 100 行并发 DOM 的虚拟列表；
- SSR/SSG spike 全量切换为生产主配置；
- 真实生产数据库和外部 AI/OCR 的破坏性自动化测试。

这些项目属于后续增强或跨端专项，不影响阶段 7 的质量收口结论，但在正式上线前仍需按发布手册完成预发布 smoke test。
