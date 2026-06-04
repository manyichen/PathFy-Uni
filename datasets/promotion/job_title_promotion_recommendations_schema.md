# 晋升路径 × 学习资源 / 竞赛 关联数据集

将 `JobPromotion` 的三段晋升目标，映射到图谱中已有的 `LearningResource`、`Competition`（二者均通过 `FOR_JOB_TITLE` 挂在 `JobTitle` 上）。

## 文件

| 文件 | 说明 |
|------|------|
| `promotion_learning_resources.csv` | 晋升路线 × 阶段 × 学习资源 |
| `promotion_competitions.csv` | 晋升路线 × 阶段 × 竞赛 |
| `job_title_promotions.csv` | 晋升路线主表（`promotion_id`） |
| `../master/learning_resources.csv` | 资源源数据 |
| `../master/competitions.csv` | 竞赛源数据 |

生成命令：

```bash
python tools/csv/build_promotion_recommendations_csv.py
```

## 匹配逻辑（生成脚本）

### 学习资源

1. 取 `job_title` 与 `learning_resources.job_name`（支持 `|` 多岗位）**精确匹配** 的资源池。
2. 按晋升 **stage 1/2/3** 分别推荐：
   - 阶段 1：偏好 `入门` 难度 + 贴合 `stage1` 称谓关键词
   - 阶段 2：偏好 `进阶`
   - 阶段 3：偏好 `进阶`/`高阶` + 贴合 `stage3` 与路线 `title` 关键词
3. 每条 `promotion_id` 每阶段最多 5/5/4 条，按 `score` 降序，`rank` 从 1 编号。
4. **通用面试资源**（`job_interview*`）：每条晋升路线在 stage 3 额外追加 2 条，由 `_score_interview_lr` 按岗位、阶段目标称谓、路线关键词匹配（技术向优先牛客笔试面经，管理/HR 向优先人力资源管理，销售/法务/翻译等优先礼仪与沟通类），不按难度/资源类型一刀切。

### 竞赛

1. **直链**：`competitions.job_name` 含当前 `job_title`。
2. **终点岗位**：若 `stage3_job_title` 在竞赛 `job_name` 中，纳入池。
3. **赛道扩展**：无直链竞赛的岗位（如销售、运营、客服），按 `_COMP_JOB_ALIASES` 使用同赛道 JobTitle 的竞赛（如销售类 → `BD经理`/`商务专员` 相关赛）。
4. 仅推荐 **stage 2、3**（竞赛偏实践与综合，阶段 1 以课程为主）。
5. 每条路线 stage2 最多 2 条、stage3 最多 3 条竞赛。

### 图谱导入

```
(JobPromotion)-[:RECOMMENDS_RESOURCE {stage, stage_role, rank, score, rationale}]->(LearningResource)
(JobPromotion)-[:RECOMMENDS_COMPETITION {stage, stage_role, rank, score, match_via, rationale}]->(Competition)
```

```bash
python tools/neo4j/sync_neo4j_promotion_recommendations.py --dry-run
python tools/neo4j/sync_neo4j_promotion_recommendations.py
```

前置：`sync_neo4j_job_promotions`、`sync_neo4j_learning_resources`、`sync_neo4j_competitions` 已执行。

## `promotion_learning_resources.csv` 表头

| 列 | 说明 |
|----|------|
| promotion_id | 对应 JobPromotion |
| job_title | 锚定岗位 |
| stage | 1 / 2 / 3，对应 stage1→stage2→stage3 |
| stage_role | 该阶段目标称谓（来自 promotions 表） |
| resource_id | LearningResource 主键 |
| resource_name | 便于人工核对 |
| difficulty / resource_type / skill_tag | 资源属性副本 |
| score | 0–1 推荐分 |
| rank | 同 promotion_id + stage 内排序 |
| rationale | 推荐依据简述 |

## `promotion_competitions.csv` 表头

| 列 | 说明 |
|----|------|
| promotion_id | 对应 JobPromotion |
| job_title | 锚定岗位 |
| stage | 2 或 3 |
| stage_role | 阶段目标称谓 |
| competition_id | Competition 主键 |
| competition_name | 便于核对 |
| difficulty / competition_type / award_level | 竞赛属性副本 |
| score | 推荐分 |
| rank | 同 promotion_id + stage 内排序 |
| match_via | JobTitle直链 / 关联赛道岗位「…」 |
| rationale | 推荐依据 |

## 已知缺口

- **竞赛库**仅覆盖约 22 个 JobTitle，法务/律师/客服等路线可能 **无竞赛行**（仅学习资源）。
- 无学习资源的 JobTitle 不会出现在 promotions 主表（当前 49 个均有资源）。
