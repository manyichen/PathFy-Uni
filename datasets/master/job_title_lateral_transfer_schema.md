# JobTitle 水平换岗相似关系

## 业务目标

在 **JobTitle**（岗位类别）之间建立 **水平换岗** 关系，用于：

- 学生当前目标岗位相近的 **平行赛道** 推荐（非晋升、非降级）
- 报告/图谱展示「你还可以考虑的这些岗位」
- 与 `JobPromotion`（纵向晋升）区分：`VERTICAL_UP` / `JobPromotion` 管「往上走」，本关系管「横着换」

## 图谱设计

```
(JobTitle)-[:SIMILAR_FOR_LATERAL {
  score,              // 0–1 综合相似度
  rank,               // 在 from 岗位下的排序（1 最相似）
  track_from, track_to,
  cap_similarity,
  same_track,         // bool
  promotion_linked,   // 是否因晋升 stage3_job_title 互指
  rationale
}]->(JobTitle)
```

| 设计点 | 说明 |
|--------|------|
| 有向边 | `from_job_title → to_job_title`；A→B 与 B→A 分别计算（相似度可不对称） |
| 仅存 Top-K | 每个来源岗位保留得分最高的 K 条（默认 8），避免完全图过密 |
| 与现有边区分 | 不用 `TRANSFER_TO`（该类型挂在 **Job** 实例上）；JobTitle 层用 `SIMILAR_FOR_LATERAL` |

### 相似度信号（生成脚本权重）

| 信号 | 权重 | 数据来源 |
|------|------|----------|
| 八维能力余弦 | 0.65 | Neo4j：`Job-[:HAS_TITLE]->JobTitle` 上 `cap_req_*` 均值 |
| 同职业赛道 | 0.25 | 脚本内 `TRACK_GROUPS` 规则表 |
| 晋升终点互指 | 0.10 | `promotion/job_title_promotions.csv` 的 `stage3_job_title` |

（不再使用学习资源 / 竞赛池 Jaccard，避免 `ALL` 面试资源与竞赛直链过少带来的偏差。）

默认 `min_score = 0.15`，可通过命令行调整。

### 职业赛道（`TRACK_GROUPS`）

| 赛道 | 示例岗位 |
|------|----------|
| 技术研发 | Java、C/C++、前端开发、科研人员… |
| 测试质量 | 测试工程师、软件测试、硬件测试、质量管理/测试… |
| 实施运维 | 实施工程师、技术支持工程师 |
| 产品项目 | 产品专员/助理、项目经理/主管、咨询顾问… |
| 市场销售 | 销售助理、BD经理、商务专员、销售工程师… |
| 运营增长 | 运营助理/专员、游戏运营、内容审核… |
| 人力培训 | 招聘专员/助理、猎头顾问、管培生/储备干部… |
| 法务知产 | 律师、法务专员/助理、知识产权/专利代理 |
| 语言翻译 | 英语翻译、日语翻译 |
| 客服支持 | 售后/网络/电话客服 |
| 行政档案 | 档案管理、资料管理 |
| 数据分析 | 统计员 |

## CSV 文件

| 文件 | 说明 |
|------|------|
| `job_title_lateral_transfer.csv` | 水平换岗相似边列表（主交付物） |

### 表头

| 列 | 说明 |
|----|------|
| `from_job_title` | 来源 JobTitle.name |
| `to_job_title` | 相似目标 JobTitle.name |
| `score` | 综合相似分 0–1 |
| `rank` | 同 `from` 下排序，1 为最相似 |
| `track_from` / `track_to` | 职业赛道名称 |
| `cap_similarity` | 八维能力向量余弦相似（无 Neo4j 时为 0） |
| `same_track` | `1`/`0` 是否同赛道 |
| `promotion_linked` | `1`/`0` 是否晋升表互指 |
| `rationale` | 推荐依据简述 |

## 生成与导入

```bash
# 生成 CSV（需 backend/.env 以聚合 cap；无 Neo4j 时仅用 CSV 信号）
python tools/csv/build_job_title_lateral_similarity.py
python tools/csv/build_job_title_lateral_similarity.py --top 10 --min-score 0.18

# 导入 Neo4j（可选）
python tools/neo4j/sync_neo4j_job_title_lateral.py --dry-run
python tools/neo4j/sync_neo4j_job_title_lateral.py
```

## 查询示例（Cypher）

```cypher
// 某岗位可水平换岗的去向 Top5
MATCH (a:JobTitle {name: $title})-[r:SIMILAR_FOR_LATERAL]->(b:JobTitle)
RETURN b.name AS target, r.score AS score, r.rationale AS rationale
ORDER BY r.rank ASC
LIMIT 5
```

## 已知限制

- 能力画像依赖 Neo4j 中 `Job` 的 `cap_req_*` 字段覆盖率。
- `TRACK_GROUPS` 需随岗位扩充手工维护。
- 未使用 Skill 节点共现（可后续从 `Job-[:REQUIRES]->Skill` 增加 Jaccard 信号）。
