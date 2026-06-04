# JobPromotion 数据集说明

对应 Neo4j 规划实体 **`JobPromotion`**（节点标签建议 `JobPromotion`），与 `JobTitle` 通过关系关联（导入脚本可定义，例如 `(JobPromotion)-[:FOR_JOB_TITLE]->(JobTitle)`）。

## CSV 文件

| 文件 | 用途 |
|------|------|
| `job_title_promotions.csv` | 有晋升路线的 JobPromotion 定义 |
| `job_title_promotions_excluded.csv` | 暂不配置路线（偏终端岗位）及原因 |

## 表头字段

| 列名 | 必填 | 说明 |
|------|------|------|
| `promotion_id` | 是 | 节点唯一键：**`{岗位名}_promotion{N}`**，N 从 1 递增。同岗位多路线必须拆成多行 |
| `job_title` | 是 | 锚定 `JobTitle.name`，须与 `../master/job_title_record_counts.csv` 完全一致 |
| `title` | 是 | 路线短标题（前端/报告展示），如「Java 后端业务线」 |
| `promotion` | 是 | **完整三段晋升文案**，用 ` → ` 连接；第三段可多选，用 ` / ` 分隔 |
| `stage1` | 是 | 第一阶段岗位称谓（执行/助理层） |
| `stage2` | 是 | 第二阶段岗位称谓（独立专业层） |
| `stage3` | 是 | 第三阶段岗位称谓（负责/专家层）；多选用 ` / ` |
| `stage3_job_title` | 否 | 若 L3 对应图谱已有 `JobTitle`，填其名（如 `项目经理/主管`）；否则留空 |
| `notes` | 否 | 维护备注 |

展示顺序由 **`promotion_id` 后缀数字**（`_promotion1`、`_promotion2`…）及 CSV 行序决定，无需单独排序字段。

## 命名约定

- **默认**：`promotion_id` = `job_title` + `_promotion` + 序号，例：`测试工程师_promotion2`。
- **含 `/` 的 job_title**（仅 `promotion_id`）：`/` → `_`，`job_title` 列仍保留原文。
  - `C/C++` → `C_C++_promotion1`
  - `法务专员/助理` → `法务专员_助理_promotion1`
  - `管培生/储备干部` → `管培生_储备干部_promotion1`
- **英文岗位名**（如 `Java`）：可用 `Java_promotion1`。
- **多路线**：每条路线独立一行，禁止合并为一行。

## 暂不配置路线（见 excluded 文件）

- 已是高管/董事长周边职能，难以再抽象统一 L3。
- 仅为管培生体系 **终点** 称谓、上游由「储备干部」等覆盖。

## 导入 Neo4j

```bash
python tools/neo4j/sync_neo4j_job_promotions.py --dry-run
python tools/neo4j/sync_neo4j_job_promotions.py --clear-orphans
```

- 节点：`JobPromotion`，唯一键 `promotion_id`，`name` 与 `promotion_id` 相同
- 关系：`(JobPromotion)-[:FOR_JOB_TITLE]->(JobTitle)`
