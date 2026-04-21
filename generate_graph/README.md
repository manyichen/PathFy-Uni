# generate_graph

本目录用于从招聘数据构建职业发展知识图谱（Jobs/Company/Skill/Certificate 等节点），并基于 LLM 推断公司内部的晋升（`VERTICAL_UP`）关系。

**主要目标**
- 提取并结构化招聘岗位数据写入 Neo4j。
- 使用本地或云端 LLM（Ollama / Gemini / OpenAI 兼容接口）批量抽取岗位属性（技能、经验、软技能等）。
- 使用另一个脚本基于岗位列表为同一公司生成晋升边（promotion edges），并以 `source` 标签标记（默认 `openai_lmstudio`）。

**目录说明**
- `script.py` — 主 ETL 脚本：读取 Excel (.xls) 招聘表，调用 LLM 批量抽取结构化字段，并将 Job / Company / Skill / Certificate / CareerLevel 等节点写入 Neo4j。
  - 支持 LLM 提供方：`gemini`（Google GenAI client）或 `ollama`（本地 Ollama）。
  - 会把岗位以 `job_key`（title::company）形式 MERGE 到图谱中，并建立 `BELONGS_TO`、`REQUIRES` 等关系。
- `openai_lmstudio_promotion_update.py` — 基于 OpenAI 兼容接口（也可指向 LM Studio 的 OpenAI gateway）为每个公司推断内部晋升路径，并把 `VERTICAL_UP` 边写入 Neo4j。
  - 会对模型返回的边做验证（置信度阈值、career_score 单调性、去重、避免自环等）。
  - 提供 `--dry-run`、`--backup-dir`、`--clear-existing` 等选项，并会把备份 JSON 写入 `promotion_backups/`（该目录已被 `.gitignore` 忽略）。
- `requirements.txt` — 运行时依赖清单（见下文）。
- `.env.example` — 常用环境变量示例。

**关键实现要点（阅读与审计提示）**
- `script.py` 的 LLM prompt 要求模型返回严格的 JSON 对象 `{ "records": [...] }`，脚本有容错与重试逻辑（MAX_RETRIES）。
- `merge_batch_to_neo4j()` 会把 LLM 抽取结果映射为节点与关系；`is_core_template` 通过岗位出现频率判断是否为模板。
- `openai_lmstudio_promotion_update.py` 中通过 `calc_career_score(title, experience_years)` 计算岗位的“career_score”，并只接受模型返回的、置信度>=`--min-confidence` 的边，且要求目标岗位的 `career_score` 高于源岗位以避免错误方向。
- 模型输出解析具备宽松解析（支持代码块包裹 JSON、尝试找第一个 `{...}`），但仍可能遇到解析错误；建议先用小规模公司跑 `--dry-run` 验证。

**环境与依赖**
1. 建议使用 Python 3.11+ 虚拟环境。
2. 安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r generate_graph/requirements.txt
```

3. 常用环境变量（可参考 `.env.example`）：
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- 若使用 Ollama：`OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- 若使用 Gemini/OpenAI：`GEMINI_API_KEY` 或 `OPENAI_API_KEY`（视脚本而定）
- `EXCEL_PATH` 可用来覆盖默认数据文件

**运行示例**

1) 用 `script.py` 将 Excel 导入 Neo4j（示例使用 Ollama）：

```bash
# 从仓库根目录运行
cd /path/to/PathFy-Uni
# 激活虚拟环境后：
python generate_graph/script.py \
  --excel-path generate_graph/20260226105856_457.xls \
  --llm-provider ollama \
  --ollama-base-url http://localhost:11434 \
  --ollama-model qwen3.5:9b \
  --batch-size 128
```

- 若需清空 Neo4j（慎用）：添加 `--clear-all`。

2) 用 `openai_lmstudio_promotion_update.py` 生成并写入晋升边（先做 dry-run 验证）：

```bash
# 先 dry-run 并输出备份到 promotion_backups/
python generate_graph/openai_lmstudio_promotion_update.py \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password yourpass \
  --openai-base-url http://121.249.146.100:1234/v1 \
  --openai-api-key $OPENAI_API_KEY \
  --min-confidence 0.55 \
  --dry-run \
  --backup-dir promotion_backups

# 确认备份并人工复核后，移除 --dry-run 写入边
python generate_graph/openai_lmstudio_promotion_update.py --neo4j-uri ... --openai-api-key ...
```

常用参数说明（`openai_lmstudio_promotion_update.py`）：
- `--min-confidence`：接受模型边的最低置信度（默认 0.55）。
- `--min-company-jobs`：单家公司至少保有的岗位数，低于则跳过（默认 2）。
- `--max-jobs-per-company` / `--max-companies`：用于控制批量大小。
- `--include-inferred`：是否包含已标记为 `inferred` 的岗位。
- `--clear-existing`：先删除已有 `VERTICAL_UP` 且 `source=openai_lmstudio` 的边后再写入。

**输出与备份**
- `openai_lmstudio_promotion_update.py` 在 `--dry-run` 下仍会生成备份 JSON（默认写入 `promotion_backups/`），备份包含 metadata 与模型生成的边，方便人工审核。
- 该目录已在 `.gitignore` 中忽略，避免将备份提交到版本库。

**审查与安全建议**
- LLM 会发生幻觉或给出不合逻辑的晋升路径；强烈建议先在小规模公司上运行 `--dry-run`，人工检查 `promotion_backups` 中的 JSON，再批量写入。
- 对写库操作（`--clear-existing`、去重、持久化）务必在备份、审查、确认后执行。
- 请确保 Neo4j 的凭证安全、并在生产环境对 API keys 做好权限与速率控制。

**故障排查**
- 若遇到模型解析错误，检查模型返回文本是否为有效 JSON（脚本会尝试从首尾大括号截取）。
- 若 Neo4j 写入报错，先在 Neo4j Browser 中检查节点是否存在，确认 `elementId()` 行为符合当前驱动版本。
- 若依赖安装失败，核对 `requirements.txt` 中的 package 版本与 Python 版本兼容性。

**扩展与改进建议**
- 增加可复现的单公司“评估模式”，将模型返回的边与图中已有 KPI（例如岗位数量、平均经验）做匹配评分后再写入。
- 将 LLM 调用拆出为可 mock 的适配层，便于本地离线测试与回放。
- 添加更完善的日志与追踪（例如记录请求 token 数、模型返回原文、耗时）。
