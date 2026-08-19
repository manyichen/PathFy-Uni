# PathFy-Uni 性格测试融合完整设计方案

> 文档状态：Phase 0～Phase 4 已完成工程实施；Phase 4 默认关闭，等待真实覆盖率与观察周期后灰度启用  
> 适用版本：基于 2026-08-19 当前仓库代码  
> 目标读者：产品、前端、后端、算法、数据治理、测试与答辩人员  
> 方案范围：性格测评、个人画像、岗位探索、人岗匹配、生涯报告、周期复盘的端到端融合

### 实施进度（2026-08-19）

第一阶段“测评数据可信化与结果可恢复”已落地：

- [x] 保留现有“人格视觉指纹”及其测量值/类型签名双模式；
- [x] 严格校验完整题集、重复题号、非法选项和越界题号；
- [x] 统一临界值口径：四字母摘要在平局时保持兼容规则，连续分数明确标记 `neutral` 与 `borderline`；
- [x] 引入 `question_set_version`、`scoring_version`、连续维度分数和稳定答案签名；
- [x] 将测评结果与本次答案在同一事务内分组保存；
- [x] 增加当前结果、历史列表、详情、切换当前结果和个性化授权 API；
- [x] 前端支持服务器结果恢复与历史切换，视觉指纹跨刷新/跨设备保持稳定；
- [x] 旧记录明确标记为“历史口径”，不伪造连续测量值；
- [x] 数据库体检、后端单元测试、前端契约测试和类型检查已覆盖本阶段契约。

第二阶段“产品闭环与解释模式”已落地：

- [x] 个人画像并列展示“能力画像 + 工作偏好”，并保留人格视觉指纹；
- [x] 性格结果页可直接进入真实岗位搜索、解释模式匹配与个人职业画像；
- [x] 岗位推荐不再是静态标签，查询词可被岗位库读取并回显来源；
- [x] 匹配支持 `off/explain` 两种偏好模式，偏好解释在能力排序完成后附加，明确保证 `influenced_ranking=false`；
- [x] 匹配历史冻结性格画像 ID、最小偏好快照和算法版本，历史详情不读取最新性格结果；
- [x] 个性化授权可关闭，关闭后旧缓存也不会让后续匹配继续使用解释模式；
- [x] 支持删除性格结果，并清理其在匹配记录中的直接偏好快照；
- [x] 首页画像阶段已改为“识别能力与工作偏好”；
- [x] 后端全量测试、前端类型/契约测试以及匹配—岗位—性格端到端回归已覆盖本阶段。

第三阶段“岗位环境画像与双层匹配”已落地：

- [x] 定义 `Job/JobTitle` 四轴工作环境字段、逐轴置信度、证据、来源、评分版本和更新时间；
- [x] 具体 Job 证据优先，缺失轴才从 `JobTitle` 逐轴继承，并在响应中标记来源；
- [x] 增加保守的招聘正文证据提取器，不根据岗位名称生成刻板画像；
- [x] 增加工作环境自动评估与人工 CSV 导入两类图谱任务，写入前均生成待复核变更集；
- [x] 实现 `preference-fit-v1` 纯函数，使用偏好强度、测量质量和岗位置信度计算逐轴解释；
- [x] 至少两个有原文证据的轴且平均置信度达到系统阈值时才输出适配分；
- [x] 岗位详情独立展示工作环境画像，匹配卡片可展开查看逐轴结论和原文证据；
- [x] 图谱 Dashboard 展示工作环境证据覆盖率、缺失量和未达到解释门槛数量；
- [x] 匹配快照记录 `preference-fit-v1` 与 `workstyle-v1`，历史岗位卡片保留生成时证据；
- [x] 排序仍只由现有八维能力逻辑决定，所有偏好结果保持 `influenced_ranking=false`。

第四阶段“报告个性化与复盘校准”已落地：

- [x] 报告 input snapshot 升级为 schema v2，同时继续验证历史 v1 哈希；
- [x] 冻结最小人格偏好快照、画像 ID 与算法版本，不保存原始答案；
- [x] 生成“协作启动、学习切入、反馈决策、时间组织”四类执行方式建议；
- [x] 每条建议包含依据、备选方式、编辑入口和“不改变能力要求”说明；
- [x] 用户接受、编辑或切换备选方案均写入报告版本与审计事件；
- [x] 复盘加入四项 1～5 分体验信号，确认后形成结构化行为偏好证据；
- [x] 只有连续三个周期出现同向信号时才提示校准，绝不自动改写人格画像；
- [x] PDF 与个人数据导出包含执行方式建议和确认后的行为证据。

第五阶段“受控软排序实验”已完成工程实现：

- [x] 新增 `tie_break` 用户主动选择模式；
- [x] 同时受系统总开关、岗位证据覆盖率、实验分桶、人格授权与能力分差门槛约束；
- [x] 只在相邻且能力分差不超过配置阈值的岗位带内使用偏好分二级排序；
- [x] 保存原能力顺序、实验顺序、逐岗位名次差异、实验分桶和算法版本；
- [x] 前端可随时切回原能力排名，每个岗位明确标记偏好是否影响名次；
- [x] 管理端设置支持即时关闭，并提供请求量、实验变体量、策略接受/编辑与行为证据计数。

当前上线约束：`MATCH_PREFERENCE_TIE_BREAK_ENABLED` 默认仍为 `false`。完成岗位工作环境数据发布、达到覆盖率阈值并观察至少一个解释模式周期后，由管理员灰度开启；关闭开关会立即回退为能力原序。人格视觉指纹继续保留在测评与统一画像中，不参与能力评分或职业淘汰。

---

## 1. 摘要与核心决策

当前 PathFy-Uni 已经形成“材料与简历 → 八维能力画像 → 岗位探索与匹配 → 生涯报告 → 周期复盘”的主链路，但性格测试仍然是一个独立问卷和结果展示页面。它能够生成 MBTI 类型、四维倾向、详细解释和静态岗位建议，却没有被能力画像、真实岗位库、匹配快照、报告输入快照或复盘机制消费。

本方案的核心决策是：

1. **性格不是第九个能力维度。**能力描述“当前能做什么”，性格测评描述“更自然的工作方式和环境偏好”，两者必须分层。
2. **MBTI 类型只用于用户可理解的结果摘要。**核心计算使用连续四维倾向值、偏好强度、数据完整度和岗位环境证据，不使用 16 类型进行硬编码淘汰。
3. **默认不改变当前能力匹配排序。**第一阶段仅增加偏好解释；只有在岗位环境数据覆盖率和置信度达标后，才允许偏好作为相近能力分岗位的软排序依据。
4. **性格最重要的价值是调整“怎样执行计划”，而不是决定“能不能从事职业”。**报告中的目标能力、资源依据和缺口计算不因 MBTI 改变，但行动形式、协作方式、反馈方式和时间组织可以个性化。
5. **所有跨模块结果必须快照化、可解释、可关闭、可删除。**历史匹配和报告必须保留生成时使用的性格画像版本，不能随着用户重新测试而静默漂移。

目标产品模型如下：

```text
简历 / 项目 / 竞赛 / 作品 ──→ 能力画像：我目前能做什么
性格问卷 / 用户偏好确认 ────→ 偏好画像：我更自然地怎样工作
岗位数据 / 岗位图谱 ────────→ 岗位要求 + 工作环境画像
                                    │
                                    ▼
                         双层人岗判断
                  ┌────────────────────────┐
                  │ 能力匹配：是否具备胜任基础 │
                  │ 偏好适配：环境是否利于发挥 │
                  └────────────────────────┘
                                    │
                                    ▼
                     目标岗位与个性化行动计划
                                    │
                                    ▼
                       月度复盘与真实行为校准
```

---

## 2. 当前实现审计

### 2.1 已有能力

性格域当前并非功能残缺，而是跨域消费缺失。现有实现已经包含：

- 50 道二选一题目；
- E/I、S/N、T/F、J/P 四组计数；
- MBTI 类型计算；
- 四维百分比和当前名为 `confidence` 的倾向差值；
- 类型摘要、核心优势、职业倾向、职场关系、成长建议和压力应对；
- 静态推荐岗位和职业建议；
- 结果持久化、结果详情和历史接口；
- 前端断点续答、本地缓存、详细结果组件和人格指纹可视化。

相关代码入口：

- `backend/app/domains/personality/router.py`
- `backend/app/domains/personality/services.py`
- `backend/app/domains/personality/data/mbti_static.json`
- `frontend/app/pages/personality.vue`
- `frontend/app/composables/api/usePersonalityApi.ts`
- `frontend/app/types/personality.ts`

### 2.2 脱钩位置

| 环节 | 当前状态 | 脱钩表现 |
|---|---|---|
| 首页流程 | 五阶段为材料、画像、匹配、计划、复盘 | 性格测试只在模块列表中单独出现，不属于流程输入 |
| 个人画像 | 仅展示简历生成的八维能力 | 无“能力 + 偏好”的统一职业画像 |
| 岗位探索 | 按关键词、公司、地点、薪资和能力值浏览 | 性格结果中的推荐岗位只是字符串，不能进入真实岗位库 |
| 岗位详情 | 包含八维要求与基础岗位属性 | 没有互动强度、结构化程度等工作环境数据 |
| 人岗匹配 | Pearson 能力轮廓 + 软缺口粗排，可选 LLM 精排 | 只读取 `student_resume`，不读取性格画像 |
| 匹配历史 | 快照保存简历、能力、岗位和模型设置 | 不保存性格画像 ID 或四维偏好快照 |
| 生涯报告 | 从 `resume_id` 和目标岗位生成缺口与计划 | 报告输入快照没有性格画像 |
| 周期复盘 | 评估能力缺口、完成率、成果和匹配变化 | 不收集工作方式体验，也无法校准偏好建议 |
| 设置与隐私 | 已有外部 LLM、报告个性化等用户偏好 | 没有“是否用性格结果个性化”的独立授权 |

### 2.3 数据完整性问题

以下问题必须在跨模块接入前修复，否则融合会放大错误：

1. **默认数据库结构没有持久化性格详细分析的正式字段。**
   
   `personality_profiles` 在 `backend/schema.sql` 中没有 `detailed_analysis`，当前提交路由通过 `SHOW COLUMNS` 动态判断。这意味着不同环境可能得到不同的数据能力。

2. **答案无法可靠归属某一次测评。**
   
   `personality_test_answers` 只有 `user_id`、`question_id` 和时间，没有 `personality_profile_id` 或 `assessment_id`。用户多次测试后，无法严格重建每次测评的答案集合。

3. **缺少题库与评分版本。**
   
   题目发生变化后，历史结果仍只有 MBTI 和时间，无法说明它基于哪一版题库、哪一版计分规则。

4. **平票规则不一致。**
   
   MBTI 类型计算使用 `>`，平票落到 I/N/F/P；维度详情使用 `>=`，平票落到 E/S/T/J；`dominant` 又落到右侧字母。一次结果内部可能产生矛盾。

5. **提交校验不足。**
   
   当前只验证 `answers` 是非空数组，没有严格验证题目是否完整、是否重复、是否属于当前题库、选项是否只能为 A/B。非 A 值会被当成 B 处理。

6. **前端没有消费服务端历史。**
   
   `usePersonalityApi` 只有 `questions` 和 `submit`，页面主要依赖 `localStorage` 恢复结果；服务端已有详情和历史路由却未进入当前工作区。

7. **现有 `confidence` 语义不准确。**
   
   当前值是左右计数差除以总数，反映的是“偏好强度”或“离中点距离”，不等同于测量可靠性。接近 50/50 可能表示偏好灵活，不代表问卷质量低。

### 2.4 当前跨域契约约束

本方案必须遵守仓库已有契约：

- `profile/personality` 使用 `{ code, msg, data }` 包络；
- `auth/jobs/match/report` 使用 `{ ok, message, data }` 包络；
- 新增性格接口继续使用 `code` 包络，避免扩大一次性重构范围；
- 匹配和报告新增字段必须保持可选，旧客户端和无性格数据用户行为不变；
- 报告异步增强依赖输入快照哈希，新字段接入时需要升级快照 schema，而不是直接修改历史快照。

---

## 3. 产品定位与设计原则

### 3.1 双画像模型

统一的“个人职业画像”由两部分组成：

| 画像 | 回答的问题 | 数据来源 | 是否用于能力缺口 |
|---|---|---|---|
| 能力画像 | 我现在能完成什么、证据在哪里 | 简历、项目、竞赛、作品、OCR 与评分 | 是 |
| 偏好画像 | 我更自然地如何协作、决策和组织工作 | 性格问卷、用户确认、长期行为反馈 | 否 |

性格测试页面可以保留，但不再被定义为孤立的“测完看结果”功能，而是“补充个人职业画像”的一个数据采集入口。

### 3.2 非目标

本方案明确不做以下事情：

- 不用 MBTI 排除岗位；
- 不宣称性格测试是心理诊断；
- 不把某个岗位硬绑定到某个 MBTI 类型；
- 不因偏好分低而隐藏能力匹配高的岗位；
- 不把性格四维直接混入八维能力雷达；
- 不让 LLM 根据原始答题记录自由推断人格；
- 不在用户未授权时把性格派生数据发送给外部模型；
- 不根据一次月度复盘自动修改用户性格类型。

### 3.3 表达规范

用户侧统一采用“偏好”“工作方式”“环境适配”语言：

- 推荐：“你在结构明确、可独立深入的任务中可能更容易进入状态。”
- 不推荐：“你是 INTJ，所以不适合销售。”
- 推荐：“该岗位客户互动较多，与你当前偏好的独立工作方式存在差异，可通过小范围访谈逐步验证。”
- 不推荐：“性格不匹配，建议放弃。”

---

## 4. 目标用户流程

### 4.1 新用户主流程

```text
注册 / 登录
  ↓
上传简历，生成能力画像
  ↓
个人职业画像显示：能力已完成 / 偏好待补充
  ↓
用户可直接匹配，也可完成 5 分钟偏好测评
  ↓
匹配页面显示能力匹配；有偏好数据时追加环境适配解释
  ↓
选择目标岗位并生成报告
  ↓
报告按能力差距决定“练什么”，按偏好画像建议“怎么练”
  ↓
月度复盘提交完成证据和工作体验
  ↓
系统提示偏好与真实体验的一致处或待验证处
```

性格测评是可选增强，不应成为开始匹配或生成报告的强制门槛。

### 4.2 已有能力画像但没有性格结果

- 匹配算法和返回结果保持当前行为；
- 在首次看到匹配结果后显示非阻塞提示；
- 提示说明补充性格后会获得什么，不使用“画像不完整”制造焦虑；
- 用户关闭后本周期不重复弹出。

示例：

> 当前排名基于八维能力。完成工作偏好测评后，可进一步查看互动方式、工作节奏和环境适配说明，不会改变你的能力分数。

### 4.3 已有历史性格结果

- 服务端加载最新一条“有效且可用于个性化”的结果；
- 页面显示测评时间、题库版本和数据状态；
- 旧结果只有 MBTI、没有连续四维时，标记为“历史类型摘要”；
- 历史类型摘要可以展示，但不能生成数值型环境适配分；
- 引导用户重新测评以获得四维数据，不静默伪造 50/50 或类型预设分数。

### 4.4 重新测试

- 新测评生成新的 `personality_profile_id`；
- 默认把新结果设为当前生效画像，旧结果归档而不覆盖；
- 历史匹配与历史报告继续使用原快照；
- 当前工作区提示“偏好画像已更新，重新匹配后才会应用到新结果”；
- 不对已有报告自动重写。

### 4.5 用户手动确认与覆盖

问卷结果不是唯一事实。结果页应允许用户对四个轴分别标记：

- 很符合；
- 部分符合；
- 暂不确定；
- 不符合，暂不用于个性化。

V1 可以只保存整体“是否用于个性化”，后续再支持轴级确认。任何手动覆盖都必须有来源和时间，不能覆盖原始测评数据。

---

## 5. 各模块融合设计

### 5.1 首页与工作流

不建议把性格测试增加为第六个串行阶段。性格与简历都是“认识自己”的输入，它应并入画像阶段的并行支路：

```text
材料证据 ──→ 能力画像 ──┐
                         ├─→ 个人职业画像 → 匹配 → 计划 → 复盘
偏好测评 ──→ 偏好画像 ──┘
```

首页修改建议：

- 五阶段仍保持材料、画像、匹配、计划、复盘；
- “画像”阶段文案改为“识别能力与工作偏好”；
- 流程可视化在画像节点前显示材料和偏好两条输入；
- 快速入口增加“补充工作偏好”；
- 模块卡片继续保留性格测试，但输出名称统一为“工作偏好画像”。

### 5.2 个人画像 `/profile`

页面目标从“能力画像工作台”升级为“个人职业画像工作台”。

建议布局：

1. 顶部完成状态：能力画像、偏好画像、最近更新时间；
2. 八维能力雷达和证据地图保持不变；
3. 新增“工作偏好”卡片，展示四个连续轴、偏好强度和可用状态；
4. 展示“用于匹配解释”“用于报告个性化”的授权状态；
5. 提供开始测试、查看结果、查看历史、重新测试入口；
6. 明确声明偏好不会修改能力分数。

个人画像摘要建议新增：

```ts
interface CareerPortraitOverview {
  capability: {
    resume_id?: number
    status: 'missing' | 'ready'
    updated_at?: string
  }
  preference: {
    personality_profile_id?: number
    status: 'missing' | 'legacy' | 'measured' | 'disabled'
    mbti_type?: string
    completed_at?: string
    axes?: PreferenceAxis[]
  }
}
```

### 5.3 性格测试 `/personality`

保留当前问卷、详细结果和人格指纹，同时补齐闭环操作：

- 顶部显示当前结果是否正在用于个性化；
- 结果页增加“带着偏好探索岗位”；
- 增加“进入人岗匹配”；
- 增加“查看偏好如何影响行动建议”；
- 静态推荐岗位从徽章变为可点击搜索入口；
- 搜索入口必须落到真实岗位库，而不是直接宣称岗位适合；
- 增加服务端历史列表和详情恢复；
- 增加“停用个性化”和“删除测评”入口；
- 旧结果缺少连续四维时显示明确的历史降级说明。

静态岗位推荐的定位改为“探索线索”，文案示例：

> 以下岗位来自类型资料的探索线索，不代表你一定适合。进入真实岗位库后，系统会继续比较你的能力证据和岗位环境。

### 5.4 岗位探索 `/jobs`

#### 5.4.1 立即可做

- 性格推荐岗位徽章跳转 `/jobs?q=<岗位名称>`；
- 岗位列表读取路由查询参数并自动发起搜索；
- AI 岗位助手可在用户明确选择后读取派生偏好摘要；
- 助手回复区分“你主动描述的偏好”和“测评得到的偏好”。

#### 5.4.2 岗位环境数据就绪后

新增筛选与展示：

- 互动强度；
- 工作结构；
- 抽象探索程度；
- 决策与反馈方式；
- 工作环境数据置信度。

岗位列表默认不因性格隐藏数据。用户可以主动选择：

- 不考虑工作偏好；
- 仅标注可能舒适的岗位；
- 优先显示环境更适配的岗位。

### 5.5 岗位详情

岗位详情增加“工作方式画像”区域：

- 展示四维环境值；
- 展示证据来源和置信度；
- 有用户偏好时显示逐轴比较；
- 数据不足时显示“暂无足够工作环境证据”，不输出伪精确分数；
- 允许用户反馈“这个岗位的实际工作方式与描述不符”，进入后续数据治理队列。

### 5.6 人岗匹配 `/match`

匹配结果采用双层结构：

| 指标 | 含义 | 是否影响默认排名 |
|---|---|---|
| `match_score` | 当前八维能力轮廓和缺口分 | 是，保持现有算法 |
| `preference_fit.score` | 工作环境与偏好适配分 | V1 否 |
| `preference_fit.confidence` | 岗位环境证据和测评数据可用度 | 仅控制是否展示 |
| `decision_hint` | 综合解释，不是第三个黑盒分数 | 否 |

岗位卡片示例：

```text
能力匹配 84                    环境偏好 67 · 中等证据

优势：实践能力与数字素养接近岗位要求。
环境提示：该岗位客户互动和临时协调较多，与你当前偏好的
深度独立工作存在差异，建议先通过岗位访谈验证实际工作节奏。
```

匹配控制区新增：

- 当前偏好画像及测评时间；
- `不使用 / 仅解释 / 相近岗位软排序` 模式；
- V1 只开放“不使用”和“仅解释”；
- 无有效画像时显示测试入口，不自动使用旧类型预设。

### 5.7 匹配历史

每次匹配快照新增：

- `personality_profile_id`；
- `preference_mode`；
- `preference_snapshot_json`；
- 岗位工作环境版本；
- 偏好算法版本；
- 是否实际影响排序。

恢复历史匹配时必须显示历史快照，而不是读取当前最新性格结果。

### 5.8 生涯报告 `/report`

报告融合遵循“能力决定内容，偏好调整形式”：

#### 不受性格影响

- 目标岗位集合；
- 八维能力缺口；
- 匹配分；
- 图谱课程和竞赛依据；
- 需要形成的作品、证书和成果；
- 复盘指标目标值。

#### 可以由偏好调整

- 学习任务的呈现顺序；
- 独立任务与协作任务的起步方式；
- 反馈渠道；
- 时间安排方式；
- 建立行业联系的渐进路径；
- 压力风险提醒；
- 同一目标下的备选执行方式。

示例映射：

| 偏好轴 | 不改变的目标 | 可调整的行动形式 |
|---|---|---|
| 互动偏低 | 仍需建立行业联系人 | 先进行一对一访谈，再参加小组活动 |
| 互动偏高 | 仍需沉淀个人作品 | 通过公开演示、结对项目推动交付 |
| 抽象偏高 | 仍需掌握岗位工具 | 先理解体系和场景，再完成工具练习 |
| 具体偏高 | 仍需理解理论 | 从案例、模板和操作任务反推概念 |
| 分析偏高 | 仍需获得他人反馈 | 使用量化标准，同时补充利益相关方反馈 |
| 关系偏高 | 仍需达到验收指标 | 先解释用户价值，再对齐量化指标 |
| 结构偏高 | 仍需完成同样交付物 | 固定里程碑、截止日期和周检查点 |
| 灵活偏高 | 仍需完成同样交付物 | 使用短冲刺、任务池和阶段性交付 |

报告新增“执行方式建议”区块，必须同时提供：

- 建议依据；
- 可替代方案；
- 用户可手动修改入口；
- “此建议不改变岗位能力要求”的说明。

### 5.9 周期复盘

复盘增加少量可选的体验信号，不增加大量问卷负担：

```ts
interface PreferenceReviewSignals {
  energy_after_tasks?: 1 | 2 | 3 | 4 | 5
  collaboration_fit?: 1 | 2 | 3 | 4 | 5
  structure_fit?: 1 | 2 | 3 | 4 | 5
  task_mode_fit?: 1 | 2 | 3 | 4 | 5
  note?: string
}
```

处理规则：

1. 单次反馈只进入报告复盘记录；
2. 连续至少三个周期出现同方向信号，才生成“偏好可能需要校准”的提示；
3. 系统只能提出候选变更，不能自动改写性格画像；
4. 用户确认后生成一条 `behavioral_preference_evidence`，保留来源；
5. 问卷结果和行为证据并列显示，避免把执行困难全部归因于性格。

---

## 6. 偏好与岗位环境模型

### 6.1 用户偏好轴

现有四维结果转换为内部统一方向，所有值范围为 0～100：

| 内部轴 | 0 端 | 100 端 | 现有来源 |
|---|---|---|---|
| `interaction_intensity` | 更偏独立恢复 | 更偏互动恢复 | I ↔ E，取 E 百分比 |
| `abstraction_preference` | 更偏具体事实 | 更偏模式与可能性 | S ↔ N，取 N 百分比 |
| `analytical_decision` | 更偏关系与价值权衡 | 更偏规则与分析判断 | F ↔ T，取 T 百分比 |
| `structure_preference` | 更偏灵活开放 | 更偏计划和确定性 | P ↔ J，取 J 百分比 |

类型结果仍保留用于显示，但内部算法只读取上述连续值。

### 6.2 三种容易混淆的量

必须区分：

1. `value`：偏好方向，例如互动强度为 75；
2. `preference_strength`：离 50 中点有多远，范围 0～1；
3. `measurement_quality`：本次测评的数据质量，例如题目完整、题库版本有效、无重复答案。

计算示例：

```text
preference_strength = abs(value - 50) / 50
```

接近 50 表示这一轴更灵活或暂时不明显，不等于测评失败。只有缺题、重复题、题库异常等情况才降低 `measurement_quality`。

### 6.3 岗位工作环境轴

岗位侧使用与用户侧同方向的四个字段：

| 字段 | 低值示例 | 高值示例 |
|---|---|---|
| `workstyle_interaction` | 长时间独立产出 | 高频客户、跨团队和公开沟通 |
| `workstyle_abstraction` | 标准流程和具体操作 | 策略、研究和开放问题 |
| `workstyle_analytical` | 高人际协调和价值权衡 | 高规则、指标和分析判断 |
| `workstyle_structure` | 需求变化和探索式推进 | 流程明确、计划稳定、合规要求高 |

每一轴同时保存：

- `value`；
- `confidence`；
- `evidence`；
- `source`；
- `scoring_version`；
- `updated_at`。

### 6.4 岗位环境数据来源优先级

1. 招聘信息中的明确文本证据；
2. 经人工复核的岗位族模板；
3. 同一 `JobTitle` 下多条招聘信息统计；
4. LLM 结构化抽取并通过规则校验；
5. 仅由岗位名称推断，置信度必须很低且不得参与排序。

禁止仅根据“程序员”“销售”等标题赋予高置信度刻板标签。

### 6.5 Neo4j 建议字段

为保持与现有 `cap_req_*`、`cap_conf_*` 结构一致，Job 节点可以增加标量属性：

```text
workstyle_interaction
workstyle_abstraction
workstyle_analytical
workstyle_structure

workstyle_conf_interaction
workstyle_conf_abstraction
workstyle_conf_analytical
workstyle_conf_structure

workstyle_scoring_version
workstyle_evidence_json
workstyle_updated_at
```

岗位族聚合数据可放在 `JobTitle`，具体招聘实例优先使用自身证据；缺失时才继承岗位族值，并在响应中标记 `inherited_from_job_title=true`。

---

## 7. 偏好适配算法

### 7.1 为什么不能直接使用绝对距离

如果用户某轴为 50，说明偏好不强或较灵活。简单计算 `100 - abs(user - job)` 会让中性用户对极端岗位只能得到 50 分，产生不合理惩罚。

因此需要用偏好强度调节差异惩罚。

### 7.2 单轴适配

对每个轴 `i`：

```text
strength_i = abs(user_i - 50) / 50
distance_i = abs(user_i - job_i)
axis_fit_i = 100 - strength_i * distance_i
```

边界行为：

- 用户为 50：`strength=0`，任何岗位都不因该轴受罚；
- 用户为 100、岗位为 100：适配为 100；
- 用户为 100、岗位为 0：适配为 0；
- 用户偏好不强时，只产生温和提示。

### 7.3 聚合分

```text
weight_i = job_confidence_i * measurement_quality_i
preference_fit = sum(axis_fit_i * weight_i) / sum(weight_i)
```

补充规则：

- 至少两个轴具备岗位证据才输出总分；
- `sum(weight_i)` 过低时状态为 `insufficient_evidence`；
- 缺失轴不按 50 补值；
- 总分保留一位小数；
- 响应同时返回逐轴差异，禁止只有单一黑盒分数。

### 7.4 证据置信度

建议输出：

```text
fit_confidence = average(job_confidence_i * measurement_quality_i)
```

用户侧分级：

- `< 0.40`：证据不足，不展示分数；
- `0.40～0.69`：中等证据，展示但明确提示验证；
- `>= 0.70`：较充分证据。

阈值必须进入系统设置，不硬编码在组件中。

### 7.5 与能力分的关系

#### V1：解释模式

- 岗位排名完全沿用现有 `match_score`；
- 偏好只生成环境提示；
- 用于验证模型、数据覆盖率和用户理解。

#### V2：相近岗位软排序

满足以下条件才允许启用：

- 用户明确选择；
- 岗位环境覆盖率达到发布门槛；
- `fit_confidence >= threshold`；
- 两岗位能力分差在一个小窗口内，例如不超过 3 分；
- 快照明确记录排序变化。

建议只做稳定的二级排序：

```text
primary key   = capability_match_score bucket
secondary key = preference_fit
```

不建议初期生成一个 `0.8 × 能力 + 0.2 × 性格` 的综合总分，因为它会掩盖两种不同含义，也难以向用户解释。

---

## 8. 数据库与快照设计

### 8.1 `personality_profiles` 扩展

建议通过新 Alembic migration 扩展现有表，而不是另起一套完全平行表：

```sql
ALTER TABLE personality_profiles
  ADD COLUMN detailed_analysis LONGTEXT NULL,
  ADD COLUMN dimension_scores_json JSON NULL,
  ADD COLUMN question_set_version VARCHAR(64) NOT NULL DEFAULT 'legacy-v1',
  ADD COLUMN scoring_version VARCHAR(64) NOT NULL DEFAULT 'mbti-count-v1',
  ADD COLUMN result_status VARCHAR(24) NOT NULL DEFAULT 'legacy_signature',
  ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN personalization_enabled TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN completed_at DATETIME NULL,
  ADD COLUMN superseded_by_profile_id INT NULL,
  ADD KEY idx_personality_profiles_user_active (user_id, is_active, completed_at),
  ADD CONSTRAINT fk_personality_profiles_superseded
    FOREIGN KEY (superseded_by_profile_id)
    REFERENCES personality_profiles(id) ON DELETE SET NULL;
```

说明：

- `detailed_analysis` 暂时保留现有路由兼容；
- `dimension_scores_json` 是跨域读取的稳定字段；
- `result_status` 可取 `measured / legacy_signature / invalid / deleted`；
- migration 先把旧记录标记为 `legacy_signature`，只有成功回填连续四维的记录才升级为 `measured`；
- migration 按用户选择最新一条有效记录设为 active，并用 `created_at` 回填 `completed_at`，不能让历史记录因字段默认值全部激活；
- `personalization_enabled` 对旧数据默认关闭，新提交由用户在结果页确认后显式开启；
- 同一用户默认只允许一条 `is_active=1`，由服务层事务维护；
- 不使用数据库 ENUM，便于后续迁移和兼容。

考虑到部分既有环境可能通过人工 SQL 提前增加过 `detailed_analysis`，migration 必须先检查列是否存在，再执行新增，避免升级生产库时因重复列失败。

### 8.2 `personality_test_answers` 扩展

```sql
ALTER TABLE personality_test_answers
  ADD COLUMN personality_profile_id INT NULL,
  ADD COLUMN question_set_version VARCHAR(64) NULL,
  ADD KEY idx_personality_answers_profile (personality_profile_id, question_id),
  ADD CONSTRAINT fk_personality_answers_profile
    FOREIGN KEY (personality_profile_id)
    REFERENCES personality_profiles(id) ON DELETE CASCADE;
```

新提交必须先创建 profile，再写入带 profile ID 的答案，或在同一事务中创建测评主记录和答案。旧答案无法可靠归组时保持 `NULL`，禁止猜测回填。

### 8.3 `match_runs` 扩展

```sql
ALTER TABLE match_runs
  ADD COLUMN personality_profile_id INT NULL,
  ADD COLUMN preference_mode VARCHAR(24) NOT NULL DEFAULT 'off',
  ADD COLUMN preference_snapshot_json LONGTEXT NULL,
  ADD COLUMN preference_algorithm_version VARCHAR(64) NULL,
  ADD COLUMN workstyle_snapshot_version VARCHAR(64) NULL,
  ADD KEY idx_match_runs_personality_profile (personality_profile_id),
  ADD CONSTRAINT fk_match_runs_personality_profile
    FOREIGN KEY (personality_profile_id)
    REFERENCES personality_profiles(id) ON DELETE SET NULL;
```

外键删除后仍可根据隐私策略决定是否保留派生快照。默认推荐在用户执行“彻底删除性格数据”时同步清除快照，而不是仅把外键设空。

### 8.4 `career_reports` 与输入快照

建议给 `career_reports` 增加便于索引的 `personality_profile_id`，同时把完整派生数据写入报告 `input_snapshot`：

```sql
ALTER TABLE career_reports
  ADD COLUMN personality_profile_id INT NULL,
  ADD KEY idx_career_reports_personality_profile (personality_profile_id),
  ADD CONSTRAINT fk_career_reports_personality_profile
    FOREIGN KEY (personality_profile_id)
    REFERENCES personality_profiles(id) ON DELETE SET NULL;
```

报告快照从 schema version 1 升级为 version 2：

```json
{
  "schema_version": 2,
  "resume_id": 12,
  "personality_profile_id": 7,
  "profile": {},
  "preference_profile": {
    "status": "measured",
    "mbti_type": "INTJ",
    "axes": [],
    "question_set_version": "mbti-50-v1",
    "scoring_version": "mbti-count-v2",
    "completed_at": "2026-08-19T10:00:00Z"
  },
  "targets": [],
  "constraints": {},
  "revisions": {
    "settings_revision": 3,
    "preference_algorithm_version": "preference-fit-v1",
    "workstyle_snapshot_version": "workstyle-v1"
  },
  "sha256": "..."
}
```

历史 version 1 快照继续按旧规则验证，不能就地重算哈希。

### 8.5 行为偏好证据

V2 可新增：

```sql
CREATE TABLE behavioral_preference_evidence (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  report_id BIGINT UNSIGNED NULL,
  review_id BIGINT UNSIGNED NULL,
  axis_code VARCHAR(32) NOT NULL,
  observed_value DECIMAL(6,2) NULL,
  source_type VARCHAR(32) NOT NULL,
  source_json JSON NULL,
  user_confirmed TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_behavioral_preference_user_axis (user_id, axis_code, created_at)
);
```

该表只保存确认后的结构化证据；未经确认的 LLM 推断只存在复盘草稿中。

---

## 9. 后端架构设计

### 9.1 领域边界

避免 `match.router`、`report.router` 直接查询性格表。建议在 personality 域提供稳定服务：

```text
personality/
├── router.py
├── services.py
├── repository.py              # 新增：测评与历史数据访问
├── preference_profile.py      # 新增：四维归一化与快照构建
├── scoring.py                 # 新增：纯函数，问卷计分与校验
└── data/mbti_static.json
```

跨域调用方向：

```text
match.services ─────┐
report.services ────┼─→ personality.preference_profile.get_active_snapshot()
profile router ─────┘

personality 域不反向导入 match / report / profile
```

### 9.2 核心服务接口

```py
def get_active_preference_snapshot(
    user_id: int,
    *,
    profile_id: int | None = None,
    require_personalization_enabled: bool = True,
) -> dict | None:
    """返回归一化、最小化、可快照的派生偏好，不返回原始答案。"""
```

返回结构：

```json
{
  "personality_profile_id": 7,
  "status": "measured",
  "mbti_type": "INTJ",
  "axes": [
    {
      "code": "interaction_intensity",
      "value": 28.0,
      "preference_strength": 0.44,
      "measurement_quality": 1.0
    }
  ],
  "question_set_version": "mbti-50-v1",
  "scoring_version": "mbti-count-v2",
  "completed_at": "2026-08-19T10:00:00Z"
}
```

### 9.3 提交流程

新提交流程必须在单一事务中完成：

1. 获取当前题库版本与题目集合；
2. 验证答案数量、唯一性、题目归属和 A/B 选项；
3. 使用一次批量查询加载题目，不逐题查询数据库；
4. 统一处理平票；
5. 计算 MBTI、连续轴、偏好强度和测量质量；
6. 生成 profile 主记录；
7. 批量写入带 `personality_profile_id` 的答案；
8. 将旧 active profile 归档；
9. 提交事务；
10. 返回兼容现有前端的完整结果。

建议平票规则：

- 连续轴保留准确的 50/50；
- `dominant` 为 `neutral`，而不是强制选左或右；
- MBTI 显示类型若必须保持四字母，可采用稳定的兼容规则，但同时返回 `borderline_axes`；
- 所有类型说明不得覆盖连续轴事实。

### 9.4 工作环境适配服务

建议新增纯函数模块 `backend/app/domains/match/preference_fit.py`：

```py
def build_preference_fit(
    preference_snapshot: dict | None,
    job_workstyle: dict | None,
    *,
    min_axes: int,
    min_confidence: float,
) -> dict:
    ...
```

返回状态应包含：

- `not_enabled`；
- `missing_user_profile`；
- `insufficient_job_evidence`；
- `available`。

不可用不是错误，不能让匹配主流程失败。

### 9.5 LLM 使用边界

匹配和报告发送给 LLM 的数据只包括：

- 四轴派生值；
- 偏好强度；
- 已确认的工作方式提示；
- 岗位环境证据摘要。

永不发送：

- 原始题目答案；
- 逐题选择序列；
- 用户 ID、profile ID；
- 未经确认的复盘人格推断；
- 用于心理诊断的提示词。

当用户关闭外部 LLM 时，偏好适配分和本地模板解释仍然可用。

---

## 10. API 契约设计

### 10.1 性格域接口

保持 `code` 包络。

#### 当前生效画像

```http
GET /api/personality/me/latest
```

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "status": "measured",
    "profile_id": 7,
    "mbti_type": "INTJ",
    "dimension_scores": [],
    "preference_axes": [],
    "question_set_version": "mbti-50-v1",
    "scoring_version": "mbti-count-v2",
    "personalization_enabled": true,
    "created_at": "2026-08-19T10:00:00Z"
  }
}
```

没有结果时仍返回 200：

```json
{"code": 200, "data": {"status": "missing"}}
```

#### 历史列表

```http
GET /api/personality/me/profiles?limit=30
```

不再要求前端传入 `user_id`。旧 `/history/<user_id>` 保留一个兼容周期后弃用。

#### 详情

```http
GET /api/personality/profiles/<profile_id>
```

必须校验当前登录用户所有权。

#### 启用或停用个性化

```http
PATCH /api/personality/profiles/<profile_id>/preferences
Content-Type: application/json

{"personalization_enabled": true}
```

#### 激活历史结果

```http
POST /api/personality/profiles/<profile_id>/activate
```

#### 删除测评

```http
DELETE /api/personality/profiles/<profile_id>
```

删除接口返回受影响的匹配和报告快照数量，并执行隐私清理策略。

### 10.2 匹配请求扩展

现有字段保持不变，新增字段可选：

```ts
interface MatchRunRequest {
  resume_id: number
  q?: string
  location_q?: string
  match_goal: 'fit' | 'stretch'
  refine_with_llm: boolean
  persist_snapshot?: boolean
  personality_profile_id?: number
  preference_mode?: 'off' | 'explain' | 'tie_break'
}
```

服务端不能接受客户端直接提交四维分数作为可信输入。传 ID 时必须校验所有权；未传 ID 且模式不为 `off` 时可读取当前生效画像。

### 10.3 匹配响应扩展

保留现有 `match_preview.match_score`：

```json
{
  "match_preview": {
    "match_score": 84.2,
    "dimension_gaps": {},
    "preference_fit": {
      "status": "available",
      "score": 67.4,
      "confidence": 0.72,
      "evidence_level": "sufficient",
      "axes": [
        {
          "code": "interaction_intensity",
          "user_value": 28,
          "job_value": 76,
          "fit": 57.8,
          "job_confidence": 0.81,
          "explanation": "该岗位互动频率高于你当前的自然偏好"
        }
      ],
      "influenced_ranking": false
    }
  }
}
```

顶层新增最小化快照摘要：

```json
{
  "preference_context": {
    "mode": "explain",
    "personality_profile_id": 7,
    "status": "measured",
    "completed_at": "2026-08-19T10:00:00Z"
  }
}
```

### 10.4 报告生成请求扩展

```json
{
  "resume_id": 12,
  "target_job_ids": ["job-1"],
  "primary_job_id": "job-1",
  "personality_profile_id": 7,
  "preference_personalization": true
}
```

没有性格画像时报告照常生成，`preference_strategy.status=missing`。

### 10.5 设置接口扩展

在 `UserPreferences` 中增加：

```ts
use_personality_in_match: boolean
use_personality_in_report: boolean
allow_personality_external_llm: boolean
default_preference_mode: 'off' | 'explain' | 'tie_break'
```

建议默认值：

```text
use_personality_in_match = true
use_personality_in_report = true
allow_personality_external_llm = false
default_preference_mode = explain
```

`allow_personality_external_llm` 必须同时受现有 `allow_external_llm` 和平台级开关约束。

---

## 11. 前端架构与文件改造

### 11.1 类型层

扩展 `frontend/app/types/personality.ts`：

```ts
export type PreferenceAxisCode =
  | 'interaction_intensity'
  | 'abstraction_preference'
  | 'analytical_decision'
  | 'structure_preference'

export interface PreferenceAxis {
  code: PreferenceAxisCode
  value: number
  preference_strength: number
  measurement_quality: number
  label?: string
  low_label?: string
  high_label?: string
}

export interface ActivePreferenceProfile extends PersonalityResult {
  status: 'missing' | 'legacy' | 'measured' | 'disabled'
  preference_axes?: PreferenceAxis[]
  question_set_version?: string
  scoring_version?: string
  personalization_enabled?: boolean
  created_at?: string
}
```

扩展 `types/job.ts`、`types/match.ts` 和 `types/report.ts`，不要在 Vue 页面中使用未声明的任意字段。

### 11.2 API adapter

`usePersonalityApi` 增加：

- `latest()`；
- `history()`；
- `detail(profileId)`；
- `activate(profileId)`；
- `updatePreferences(profileId, patch)`；
- `remove(profileId)`。

所有 legacy `code` 解析仍收敛在 adapter 中，页面不直接判断 `code`。

### 11.3 状态组织

建议把 `personality.vue` 当前的答题、缓存、提交、结果状态拆为：

```text
frontend/app/composables/personality/
├── usePersonalityAssessment.ts
├── usePersonalityHistory.ts
└── useActivePreferenceProfile.ts
```

`useActivePreferenceProfile` 可被 profile、jobs、match 和 report 复用。服务端是结果事实来源，`localStorage` 只保存未提交的答题进度和短期页面缓存。

### 11.4 建议新增组件

```text
components/personality/
├── PersonalityUsageStatus.vue
├── PersonalityHistoryModal.vue
├── PreferenceAxisSummary.vue
├── PreferenceIntegrationActions.vue
└── PreferenceDataNotice.vue

components/profile/
└── ProfilePreferenceCard.vue

components/jobs/
└── JobWorkstyleProfile.vue

components/match/
├── MatchPreferenceContext.vue
└── MatchPreferenceFit.vue

components/report/
├── ReportPreferenceStrategy.vue
└── ReportPreferenceEvidence.vue
```

### 11.5 缓存策略

- 未提交答案继续使用用户隔离的本地缓存；
- 已提交结果以服务端最新 profile 为准；
- 缓存中保存 `profile_id`、`saved_at` 和 schema version；
- 服务端当前 active profile 变化时使本地结果缓存失效；
- 匹配和报告恢复只使用各自快照，不读取 personality 页面缓存。

---

## 12. 迁移与兼容策略

### 12.1 数据迁移顺序

1. 新增 personality 字段和答案外键；
2. 新增 match/report 快照字段；
3. 部署只写新结构但仍兼容旧读法的后端；
4. 回填可确定的 `dimension_scores_json`；
5. 发布新性格 API adapter；
6. 接入 profile 和 match 解释模式；
7. 接入 report；
8. 岗位工作环境覆盖率达标后再开放软排序。

### 12.2 旧数据处理

| 旧数据状态 | 处理方式 |
|---|---|
| 有 `detailed_analysis.dimension_scores` | 规范化后回填 `dimension_scores_json`，标记来源 `legacy_backfill` |
| 只有 MBTI 类型 | 标记 `legacy_signature`，仅展示类型摘要，不计算偏好适配分 |
| 答案没有 profile 归属 | 不自动猜测归组，保留原记录 |
| 本地缓存有完整结果、服务端缺失 | 不静默上传；提示重新测评或由用户明确确认导入 |
| 历史匹配无性格快照 | 按 `preference_mode=off` 恢复 |
| 历史报告 schema v1 | 保持原哈希和原展示，不补写新字段 |

### 12.3 回滚能力

所有新行为由设置和 feature flag 控制：

- 关闭偏好解释时回到当前能力匹配；
- 关闭报告个性化时仍保留报告生成；
- 工作环境数据异常时只隐藏偏好分，不影响岗位列表；
- migration downgrade 不删除原始 MBTI、分析文本和答案；
- 软排序必须可以通过系统设置立即关闭。

---

## 13. 系统设置与发布开关

建议新增平台设置：

```text
PERSONALITY_ENABLE_INTEGRATION=true
PERSONALITY_ENABLE_MATCH_EXPLANATION=true
PERSONALITY_ENABLE_MATCH_TIE_BREAK=false
PERSONALITY_ENABLE_REPORT_PERSONALIZATION=true
PERSONALITY_MIN_JOB_AXES=2
PERSONALITY_MIN_FIT_CONFIDENCE=0.40
PERSONALITY_TIE_BREAK_SCORE_WINDOW=3.0
PLATFORM_ALLOW_PERSONALITY_LLM=false
```

进入现有 settings registry：

| 设置 | 分组 | 类型 | 说明 |
|---|---|---|---|
| `PERSONALITY_ENABLE_INTEGRATION` | personality | bool | 总开关 |
| `PERSONALITY_MIN_JOB_AXES` | personality | int 1～4 | 输出环境分所需最少轴数 |
| `PERSONALITY_MIN_FIT_CONFIDENCE` | personality | float 0～1 | 最低证据阈值 |
| `PERSONALITY_ENABLE_MATCH_TIE_BREAK` | match | bool | 允许相近岗位软排序 |
| `PERSONALITY_TIE_BREAK_SCORE_WINDOW` | match | float 0～10 | 能力分相近窗口 |
| `PERSONALITY_ENABLE_REPORT_PERSONALIZATION` | career | bool | 报告执行方式个性化 |
| `PLATFORM_ALLOW_PERSONALITY_LLM` | privacy | bool | 平台允许派生偏好进入外部 LLM |

设置修订号需要进入匹配和报告快照。

---

## 14. 隐私、安全与伦理

### 14.1 数据分级

| 数据 | 敏感级别 | 处理原则 |
|---|---|---|
| 原始逐题答案 | 高 | 仅本地业务使用，不发送外部 LLM |
| MBTI 类型 | 中 | 可展示，跨域使用需用户授权 |
| 连续偏好轴 | 中高 | 只发送最小派生快照 |
| 行为复盘信号 | 高 | 明确来源，未经确认不进入长期画像 |
| 岗位环境标签 | 普通业务数据 | 必须保留证据与版本 |

### 14.2 用户控制

用户必须能够：

- 查看当前生效测评；
- 查看哪些模块正在使用；
- 单独关闭匹配或报告个性化；
- 单独禁止外部 LLM；
- 切换生效历史结果；
- 删除某次测评；
- 执行彻底删除并清理跨域派生快照。

### 14.3 日志规则

日志中不得记录：

- 原始 answers 请求体；
- 完整逐题选择；
- 性格分析长文本；
- 用户 ID 与 MBTI 的直接拼接日志；
- 外部模型完整提示词中的个人偏好快照。

允许记录聚合指标：

- 测评完成数；
- measured / legacy 状态占比；
- 偏好解释可用率；
- 工作环境数据覆盖率；
- 软排序触发次数；
- 用户关闭或删除次数。

### 14.4 删除语义

“停用”和“删除”必须分开：

- 停用：保留数据，不再参与新匹配和报告；
- 删除单次测评：删除 profile 与对应 answers，并清除直接引用；
- 彻底删除性格数据：清除全部测评、答案、行为偏好证据和匹配/报告内的偏好派生快照。

报告快照被清理后需要重新生成哈希并写入审计说明，或将报告标记为 `preference_data_removed`。不能保留旧哈希却修改内容。

---

## 15. 可观测性与效果评估

### 15.1 事件指标

建议记录以下匿名事件：

```text
personality_test_started
personality_test_completed
personality_profile_activated
personality_personalization_toggled
personality_job_exploration_clicked
match_preference_context_attached
match_preference_explanation_viewed
match_preference_insufficient_evidence
match_tie_break_changed_order
report_preference_strategy_generated
report_preference_strategy_edited
review_preference_signal_submitted
personality_retest_prompt_accepted
```

### 15.2 产品效果指标

不以“测评完成率”作为唯一成功标准，应关注：

- 性格结果到岗位探索的转化率；
- 双层解释的查看率；
- 用户对“能力匹配”和“环境适配”的区分正确率；
- 报告执行方式被保留、修改或关闭的比例；
- 个性化组与非个性化组的月度行动完成率；
- 用户主动修改建议后完成率是否提升；
- 环境适配高/低与真实体验反馈是否相关；
- 误解为“性格决定职业”的投诉或反馈数量。

### 15.3 数据发布门槛

开放软排序前建议至少满足：

- 可参与匹配岗位中，四轴至少两轴有证据的覆盖率 ≥ 80%；
- 参与软排序岗位的平均工作环境置信度 ≥ 0.70；
- 偏好解释人工抽检无明显职业刻板印象；
- 解释模式运行至少一个完整观察周期；
- 用户能够一键关闭且关闭后排序与当前算法一致；
- 线上实验没有显著降低岗位多样性。

---

## 16. 测试方案

### 16.1 后端单元测试

性格计分：

- 完整题集正常计分；
- 缺题拒绝；
- 重复题拒绝；
- 非法题目 ID 拒绝；
- 非 A/B 选项拒绝；
- 平票产生 50/50 和 `neutral`；
- MBTI 摘要与连续轴方向不矛盾；
- 同一输入结果稳定；
- 题库版本进入结果。

偏好适配：

- 用户 50 时不惩罚极端岗位；
- 用户和岗位同向时为高分；
- 强偏好完全反向时为低分；
- 缺失轴不补零；
- 少于最小轴数返回 `insufficient_job_evidence`；
- 岗位置信度正确影响聚合；
- 分数边界始终为 0～100；
- 无性格画像不影响能力匹配结果。

### 16.2 后端集成测试

- 提交事务同时产生 profile 和关联 answers；
- 新测试正确归档旧 active profile；
- 只能读取和激活自己的 profile；
- `me/latest` 在 missing、legacy、measured、disabled 下契约稳定；
- 匹配请求传入他人 profile ID 返回 403；
- 匹配快照保存使用时的派生值；
- 重测后恢复旧匹配仍显示旧快照；
- 报告 input snapshot v2 哈希可验证；
- v1 历史报告仍可读取；
- 删除测评执行跨域清理；
- 关闭外部 LLM 时不发送派生偏好。

### 16.3 前端单元与组件测试

- personality adapter 归一化 latest/history/detail；
- legacy 类型结果不显示伪造的四维适配分；
- ProfilePreferenceCard 的四种状态；
- MatchPreferenceFit 的 available / insufficient / off 状态；
- 双分数不会覆盖原 `match_score`；
- ReportPreferenceStrategy 显示依据和替代方式；
- 设置开关正确保存；
- 服务端 active profile 变化使缓存失效。

### 16.4 E2E 场景

1. 新用户上传简历，不做测试，完成匹配与报告；
2. 完成性格测试，从结果进入真实岗位搜索；
3. 带 active profile 运行匹配，看到能力和环境双层解释；
4. 关闭个性化后重新匹配，结果回到纯能力模式；
5. 生成报告，查看执行方式建议；
6. 重新测试后，新匹配使用新画像，旧历史仍保持旧快照；
7. legacy 结果只显示类型摘要和重测提示；
8. 岗位环境证据不足时不显示伪精确分数；
9. 删除性格数据后跨模块不再展示派生结果；
10. 外部 LLM 不可用时本地解释正常降级。

### 16.5 回归测试

必须证明：

- 无性格数据时，现有匹配排序逐项一致；
- `match_score` 算法与字段不变；
- 报告不因性格服务失败而生成失败；
- 首页首屏资源不加载性格可视化 chunk；
- 当前 profile/personality legacy envelope 仍被 adapter 正确解析；
- 报告异步 enrichment 质量门禁继续通过。

---

## 17. 分阶段实施计划

### Phase 0：数据与计分可信化

目标：使性格结果成为可被其他模块安全读取的正式数据源。

任务（已完成）：

- [x] 新增 Alembic migration；
- [x] 修复 `detailed_analysis` 正式字段；
- [x] answers 关联 profile；
- [x] 增加题库和评分版本；
- [x] 统一平票语义；
- [x] 严格提交校验和批量查询；
- [x] 增加 latest/history/detail/activate 接口；
- [x] 前端历史结果改为服务端事实来源；
- [x] 补齐单元和集成测试。

完成标准：任何一条 measured profile 都能回答“谁、何时、基于哪版题库、使用哪些连续轴、对应哪些答案”。

### Phase 1：产品闭环与解释模式

目标：让性格结果真正进入个人画像、岗位探索和匹配，但不改变排名。

任务（已完成）：

- [x] `ProfilePreferenceCard`；
- [x] 性格结果页三个闭环 CTA；
- [x] 推荐岗位跳转真实搜索；
- [x] jobs 页面读取 query；
- [x] match 请求和快照接入 active profile；
- [x] preference mode 支持 off/explain；
- [x] 匹配卡片展示“偏好数据待补充/岗位证据不足”；
- [x] 用户设置和隐私开关；
- [x] 首页画像阶段改造。

实施说明：本阶段新增的偏好上下文在能力匹配完成排序之后才附加到岗位卡片；即使请求 `explain`，岗位分数和顺序也与 `off` 完全一致。系统只冻结派生后的最小偏好快照，不把原始答案或长篇分析发送给匹配逻辑或外部模型。`tie_break` 在 Phase 1 被明确拒绝，待 Phase 4 达到数据覆盖率和实验门槛后再考虑启用。

验证记录（2026-08-19）：后端 `209 passed`；前端类型检查通过；性格/匹配相关单元测试 `39 passed`；`matching-jobs-personality.spec.ts` 端到端 `16 passed`。

完成标准：性格测试完成后，用户无需手动复制信息即可进入岗位、匹配和个人画像；无性格结果用户的匹配不发生变化。

### Phase 2：岗位环境画像与双层匹配

目标：基于可审计的岗位工作环境数据输出逐轴适配。

任务（已完成）：

- [x] 定义 Job/JobTitle 工作环境字段；
- [x] 构建抽取、置信度和人工复核流程；
- [x] 图谱任务支持工作环境字段更新；
- [x] job serializer、types、详情组件接入；
- [x] `preference_fit.py` 实现与测试；
- [x] 工作环境证据覆盖率仪表板；
- [x] 上线解释模式。

实施说明：`job_workstyle_evaluation` 只从 `demand/company_detail/experience_text` 提取明确措辞，岗位名称不进入提取输入；`job_workstyle_import` 要求每个已填写轴都有 0～100 数值、0～1 置信度、来源、版本和 JSON 证据。两者都复用图谱任务的“规划 → 管理员复核 → 整单确认 → 原子写入”流程。匹配先完成原能力排序，再调用 `build_preference_fit` 附加解释，因此开关解释模式不会改变岗位 ID 顺序和能力匹配分。

验证记录（2026-08-19）：后端全量 `225 passed`；前端全量 `88 passed`；前端类型检查通过；匹配—岗位—性格端到端 `18 passed`；图谱管理端到端 `5 passed`。

完成标准：偏好分可回到逐轴岗位证据，数据不足时系统选择不输出分数。

### Phase 3：报告个性化与复盘校准

状态：已完成工程实施。

目标：让偏好真正改善行动可执行性。

任务：

- [x] 报告 snapshot schema v2；
- [x] 报告执行方式策略；
- [x] 本地确定性模板（外部 LLM 不成为事实来源）；
- [x] 用户编辑和接受记录；
- [x] 复盘体验信号；
- [x] 三周期校准提示；
- [x] 行为证据确认流程；
- [x] PDF 和数据导出接入。

完成标准：性格只调整执行方式，不改变能力证据和岗位要求；历史报告可复现。

### Phase 4：受控软排序实验

状态：工程实现完成，默认关闭，等待数据门槛与真实观察周期后灰度发布。

目标：验证偏好是否能在不损害岗位多样性的前提下改善选择质量。

任务：

- [ ] 达成生产数据发布门槛（需真实岗位标注与观察周期，非代码任务）；
- [x] 开放用户主动选择 tie-break；
- [x] 保存排序前后差异；
- [x] A/B 稳定分桶实验；
- [x] 保存可用于岗位多样性、点击、报告导入和复盘体验分析的版本与差异数据；
- [x] 支持系统级即时关闭。

完成标准：只有证据充分且能力分相近的岗位发生二级排序，用户始终能查看原能力排名。

### 建议排期与关键依赖

以下为单仓库、小团队条件下的相对工作量估算，不包含大规模岗位人工标注时间：

| 阶段 | 预估工程量 | 可并行工作 | 关键依赖 |
|---|---:|---|---|
| Phase 0 | 6～9 人日 | 后端 migration/API 与前端历史工作区可部分并行 | 数据库升级窗口、旧库结构审计 |
| Phase 1 | 6～10 人日 | profile、personality、home UI 可并行 | Phase 0 active snapshot API |
| Phase 2 | 10～16 人日 + 数据治理 | 算法纯函数、图谱字段、岗位详情可并行 | 工作环境标注规范与样本覆盖率 |
| Phase 3 | 8～12 人日 | 报告快照、执行策略、复盘 UI 可部分并行 | Phase 1 稳定快照、报告异步质量门禁 |
| Phase 4 | 4～7 人日 + 观察周期 | 埋点分析与软排序开关可并行 | Phase 2 数据发布门槛、至少一个解释模式观察周期 |

关键路径为：

```text
数据可信化
  → active preference snapshot
  → 匹配解释模式
  → 岗位环境覆盖率达标
  → 报告个性化验证
  → 受控软排序实验
```

如果资源有限，应完整交付 Phase 0 和 Phase 1，再决定是否进入岗位环境评分。只做页面跳转而不修数据归属和快照，会让后续历史结果无法解释。

---

## 18. 验收标准

### 18.1 功能验收

- 用户可以在个人画像中查看能力和偏好两个独立区域；
- 性格结果可以一键进入真实岗位探索和匹配；
- 匹配显示能力分与偏好适配的不同含义；
- 无岗位环境证据时不显示虚构分数；
- 报告显示偏好驱动的执行方式建议和依据；
- 重新测试不改写历史匹配与报告；
- 用户可以关闭和删除性格个性化数据。

### 18.2 算法验收

- 能力匹配算法输出保持兼容；
- 50/50 用户不被当作低质量或强偏好；
- 偏好适配结果逐轴可解释；
- 工作环境置信度参与是否展示；
- 默认模式不改变岗位排名；
- tie-break 只在配置窗口内生效。

### 18.3 数据验收

- 所有新测评答案均可关联到 profile；
- 所有新测评包含题库与评分版本；
- match/report 均保存使用时快照；
- 快照哈希可验证；
- legacy 数据状态明确，不伪造连续值；
- 删除流程覆盖跨域派生数据。

### 18.4 文案验收

- 不出现“某 MBTI 不适合某职业”的确定性结论；
- 不把偏好低分表述为能力不足；
- 不把 50/50 表述为测试失败；
- 所有环境提示都包含验证建议；
- 明确声明测评不是心理诊断。

---

## 19. 主要风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 把 MBTI 当作职业淘汰条件 | 降低职业探索多样性 | 双分数、默认不排序、文案规则和人工抽检 |
| 岗位环境数据不足 | 输出伪精确分数 | 最少轴数和置信度门槛，不足时不显示 |
| 旧数据无法重建 | 历史结果不完整 | 标记 legacy，不猜测回填，引导重测 |
| 重测导致历史漂移 | 报告无法复现 | match/report 保存不可变派生快照 |
| 个性化建议过度刻板 | 用户被标签限制 | 提供替代方案、允许编辑、真实行为校准 |
| LLM 扩大隐私面 | 原始答案泄露 | 只发送派生轴、独立授权、默认禁止 personality LLM |
| 新字段破坏现有前端 | 发布回归 | 字段全部可选，保留包络和原 match_score |
| 偏好压过能力与现实约束 | 推荐失真 | 能力主排序、偏好只解释或相近分软排序 |
| 报告个性化造成计划不稳定 | 用户无法比较版本 | 目标与验收物不变，只调整执行形式并快照 |

---

## 20. 建议的工程任务拆分

### 后端

- BE-PER-001：性格表结构 migration；
- BE-PER-002：题库版本、严格答案校验和批量计分；
- BE-PER-003：统一平票和连续轴语义；
- BE-PER-004：personality repository 与 active snapshot service；
- BE-PER-005：latest/history/detail/activate/delete API；
- BE-MATCH-001：匹配请求和快照接入 preference context；
- BE-MATCH-002：纯函数 preference fit；
- BE-JOBS-001：工作环境字段与 serializer；
- BE-REPORT-001：input snapshot schema v2；
- BE-REPORT-002：执行方式个性化和本地模板；
- BE-REVIEW-001：体验信号与候选校准；
- BE-PRIVACY-001：停用、删除与跨域清理。

### 前端

- FE-PER-001：Personality API adapter 扩展；
- FE-PER-002：答题与历史 composable 拆分；
- FE-PER-003：结果页闭环入口与使用状态；
- FE-PROFILE-001：个人职业画像偏好卡片；
- FE-JOBS-001：query 搜索与工作环境组件；
- FE-MATCH-001：偏好模式控件和双层解释；
- FE-MATCH-002：历史快照恢复；
- FE-REPORT-001：执行方式建议和证据区；
- FE-ACCOUNT-001：用户授权设置；
- FE-HOME-001：首页画像阶段并行输入表达。

### 数据与图谱

- DATA-WORKSTYLE-001：四轴定义与标注手册；
- DATA-WORKSTYLE-002：岗位族初始模板；
- DATA-WORKSTYLE-003：招聘文本抽取与证据字段；
- DATA-WORKSTYLE-004：置信度和人工复核；
- GRAPH-WORKSTYLE-001：Job/JobTitle 字段写入任务；
- DATA-QA-001：覆盖率、漂移和刻板印象审计。

### 测试

- QA-PER-001：计分边界与提交安全；
- QA-PER-002：历史、重测和删除；
- QA-MATCH-001：无性格数据零回归；
- QA-MATCH-002：偏好适配边界；
- QA-REPORT-001：快照与异步增强；
- QA-E2E-001：完整双画像用户旅程；
- QA-PRIVACY-001：外部 LLM 和彻底删除审计。

---

## 21. 最终建议

性格测试最有价值的融合方式，不是给当前匹配总分再加一个 MBTI 权重，而是补齐 PathFy-Uni 对“人”的第二种理解：

- 能力画像保证建议有胜任证据；
- 偏好画像解释用户在什么环境中更容易发挥；
- 岗位环境画像提供可比较的现实对象；
- 生涯报告把相同目标转换成更适合个人执行的路径；
- 周期复盘用真实行为持续校准问卷结论。

这样改造后，性格测试不再是导航栏末尾的一次性测评，而会成为贯穿个人画像、岗位理解、匹配解释、计划执行和长期复盘的“偏好证据层”。同时，它仍然不会越权替代能力证据、职业选择或用户本人。
