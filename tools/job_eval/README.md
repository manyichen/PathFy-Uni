# Job 批量评估（200条先行）

该工具用于按《能力画像图谱-职业评估依据（最终版）》先跑 200 条 `Job`：

- 从 Neo4j 抽取岗位证据
- 调用 LLM 生成 8 维分数 + 置信度 + 证据
- 低置信度触发复核（可配置）
- 可选写回 Neo4j

## 1. 安装依赖

```bash
cd tools/job_eval
pip install -r requirements.txt
```

## 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写：

- `NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD / NEO4J_DATABASE`
- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`

可选配置：

- `PRIMARY_PROVIDER=deepseek`
- `REVIEW_PROVIDER=qwen`
- `REVIEW_CONFIDENCE_THRESHOLD=0.60`
- `CAP_VERSION=v1.0.0-pilot200`
- **`JOB_EVAL_LIMIT`**：处理条数（默认 200）；命令行 **`--limit`** 可覆盖
- **`JOB_EVAL_START`**：从排序后第几条开始（**1-based**，默认 1）；命令行 **`--start`** 可覆盖
- `JOB_EVAL_WORKERS`：并发线程数（默认 3）

## 3. 运行方式

### 3.1 先试跑（不写回图谱）

条数与起点由 **`.env` 的 `JOB_EVAL_LIMIT`、`JOB_EVAL_START`** 控制；也可在命令行用 **`--limit` / `--start`** 临时覆盖。

```bash
python run_job_eval_batch.py --dry-run --env .env
python run_job_eval_batch.py --dry-run --env .env --limit 12 --start 5
```

并发由 **`JOB_EVAL_WORKERS`**（默认 3）；命令行 **`--workers`** 可覆盖。过大易触发 API 限流。

```bash
python run_job_eval_batch.py --dry-run --env .env --workers 5
```

### 3.2 正式写回

```bash
python run_job_eval_batch.py --limit 200 --env .env
```

### 3.3 输出文件

默认输出 `job_eval_results_YYYYMMDD_HHMMSS.jsonl`，每行一个岗位结果或错误信息。

### 3.4 回灌 `--dry-run` 结果到 Neo4j

如果你已经有历史 `jsonl`（例如 `job_eval_results_20260412_043102.jsonl`），可直接回灌：

```bash
python import_job_eval_jsonl.py --env .env --input job_eval_results_20260412_043102.jsonl
```

可选参数：

- `--batch-size 300`：每批写入条数
- `--cap-version v1.0.0-replay`：覆盖写回版本号
- `--include-inferred`：默认跳过 `job_id` 以 `::inferred` 结尾的全零占位数据；加此参数则写入
- `--unmatched-output unmatched.txt`：导出未命中 `Job` 的 `job_id`

## 4. 输出字段说明

- `scores`: 8维分数（0~100）
- `confidence`: 8维置信度（0~1）
- `evidence`: 证据列表（规范要求简短，融合后最多保留 8 条）
- `risk_flags`: 风险标记（规范要求每项短句）
- `fusion`: 复核融合信息（触发复核时）

## 5. 当前脚本的默认策略

- 主评：`PRIMARY_PROVIDER`（推荐 `deepseek`）
- 复核：`REVIEW_PROVIDER`（推荐 `qwen`）
- 触发条件：任一维置信度 `< REVIEW_CONFIDENCE_THRESHOLD`
- 融合策略：`0.4 * 主评 + 0.6 * 复核`

## 6. 注意事项

- 本脚本假设标签为 `Job`、`Skill`，关系为 `REQUIRES`、`TRANSFER_TO`、`VERTICAL_UP`。
- 若你的图谱字段命名不同，请修改 `run_job_eval_batch.py` 中 `fetch_jobs_payload` 查询。
- 建议先 `--dry-run` 看输出质量，再执行写回。

## 7. 自动生成质检报告

在得到 `job_eval_results_*.jsonl` 后，执行：

```bash
python make_qc_report.py
```

可选参数：

```bash
python make_qc_report.py --input job_eval_results_xxx.jsonl --threshold 0.60
```

输出文件：

- `qc_report_YYYYMMDD_HHMMSS.md`
- `low_confidence_YYYYMMDD_HHMMSS.csv`

报告包含：

- 分数分布（8维分档）
- 低置信度名单（Top 30）
- 失败原因统计

