# 岗位能力评估离线质检

岗位八维评估、低置信度复核和历史 JSONL 导入已经收口到后端图谱任务队列。禁止从
`tools/` 直接修改 Neo4j；请在管理后台创建“存量岗位八维评估”或“历史能力结果导入”任务。

本目录仅保留对历史 JSONL 生成本地只读质检报告的工具：

```bash
python tools/job_eval/make_qc_report.py --input path/to/results.jsonl --threshold 0.60
```
