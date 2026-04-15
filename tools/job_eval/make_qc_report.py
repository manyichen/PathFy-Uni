import argparse
import csv
import glob
import json
import os
from collections import Counter
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Tuple


DIM_KEYS = [
    "cap_req_theory",
    "cap_req_cross",
    "cap_req_practice",
    "cap_req_digital",
    "cap_req_innovation",
    "cap_req_teamwork",
    "cap_req_social",
    "cap_req_growth",
]

CONF_KEYS = [
    "cap_conf_theory",
    "cap_conf_cross",
    "cap_conf_practice",
    "cap_conf_digital",
    "cap_conf_innovation",
    "cap_conf_teamwork",
    "cap_conf_social",
    "cap_conf_growth",
]


def infer_latest_jsonl(pattern: str) -> str:
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"未找到结果文件，匹配模式: {pattern}")
    return files[0]


def load_jsonl(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ok_rows: List[Dict[str, Any]] = []
    err_rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "error" in obj:
                err_rows.append(obj)
            else:
                ok_rows.append(obj)
    return ok_rows, err_rows


def bucket_score(v: float) -> str:
    if v < 40:
        return "0-39"
    if v < 60:
        return "40-59"
    if v < 80:
        return "60-79"
    return "80-100"


def dim_distribution(ok_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    for k in DIM_KEYS:
        c = Counter()
        for row in ok_rows:
            score = float(row.get("scores", {}).get(k, 0))
            c[bucket_score(score)] += 1
        result[k] = {b: c.get(b, 0) for b in ["0-39", "40-59", "60-79", "80-100"]}
    return result


def collect_low_confidence(
    ok_rows: List[Dict[str, Any]], threshold: float
) -> List[Dict[str, Any]]:
    low: List[Dict[str, Any]] = []
    for row in ok_rows:
        conf = row.get("confidence", {})
        min_k = None
        min_v = 1.0
        low_dims: List[str] = []
        for k in CONF_KEYS:
            v = float(conf.get(k, 0))
            if v < threshold:
                low_dims.append(k)
            if v < min_v:
                min_v = v
                min_k = k
        if low_dims:
            low.append(
                {
                    "job_id": row.get("job_id", ""),
                    "min_conf_key": min_k or "",
                    "min_conf_value": round(min_v, 4),
                    "low_conf_dims": ",".join(low_dims),
                    "risk_flags": ",".join(row.get("risk_flags", [])),
                }
            )
    low.sort(key=lambda x: x["min_conf_value"])
    return low


def summarize_failures(err_rows: List[Dict[str, Any]]) -> Counter:
    c = Counter()
    for e in err_rows:
        msg = str(e.get("error", "unknown"))
        short = msg.split(":", 1)[0][:120]
        c[short] += 1
    return c


def write_low_conf_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    fields = ["job_id", "min_conf_key", "min_conf_value", "low_conf_dims", "risk_flags"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def write_report_md(
    report_path: str,
    input_path: str,
    ok_rows: List[Dict[str, Any]],
    err_rows: List[Dict[str, Any]],
    dist: Dict[str, Dict[str, int]],
    low_rows: List[Dict[str, Any]],
    fail_stats: Counter,
    threshold: float,
) -> None:
    total = len(ok_rows) + len(err_rows)
    success = len(ok_rows)
    failed = len(err_rows)
    success_rate = (success / total * 100) if total else 0

    avg_scores = {
        k: round(mean(float(r.get("scores", {}).get(k, 0)) for r in ok_rows), 2)
        if ok_rows
        else 0.0
        for k in DIM_KEYS
    }

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Job评估质检报告\n\n")
        f.write(f"- 输入文件: `{input_path}`\n")
        f.write(f"- 生成时间: `{datetime.now().isoformat(timespec='seconds')}`\n")
        f.write(f"- 低置信度阈值: `{threshold}`\n\n")

        f.write("## 1. 总体统计\n\n")
        f.write(f"- 总条数: `{total}`\n")
        f.write(f"- 成功条数: `{success}`\n")
        f.write(f"- 失败条数: `{failed}`\n")
        f.write(f"- 成功率: `{success_rate:.2f}%`\n")
        f.write(f"- 低置信度条数: `{len(low_rows)}`\n\n")

        f.write("## 2. 八维平均分\n\n")
        for k in DIM_KEYS:
            f.write(f"- `{k}`: `{avg_scores[k]}`\n")
        f.write("\n")

        f.write("## 3. 分数分布\n\n")
        f.write("| 维度 | 0-39 | 40-59 | 60-79 | 80-100 |\n")
        f.write("|---|---:|---:|---:|---:|\n")
        for k in DIM_KEYS:
            d = dist[k]
            f.write(f"| `{k}` | {d['0-39']} | {d['40-59']} | {d['60-79']} | {d['80-100']} |\n")
        f.write("\n")

        f.write("## 4. 低置信度名单（Top 30）\n\n")
        f.write("| job_id | 最低置信度维度 | 最低置信度 | 低置信度维度列表 |\n")
        f.write("|---|---|---:|---|\n")
        for r in low_rows[:30]:
            f.write(
                f"| `{r['job_id']}` | `{r['min_conf_key']}` | {r['min_conf_value']} | `{r['low_conf_dims']}` |\n"
            )
        f.write("\n")

        f.write("## 5. 失败原因统计\n\n")
        if not fail_stats:
            f.write("- 无失败记录\n")
        else:
            for reason, cnt in fail_stats.most_common(20):
                f.write(f"- `{reason}`: `{cnt}`\n")
        f.write("\n")

        f.write("## 6. 建议\n\n")
        f.write("- 对低置信度样本优先进行Qwen复核或人工抽检。\n")
        f.write("- 对高频失败原因补充重试与输入清洗策略。\n")
        f.write("- 将低置信度清单与证据不足维度用于词典和权重迭代。\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="从 job_eval_results_*.jsonl 生成质检报告")
    parser.add_argument("--input", type=str, default="", help="输入 jsonl 文件路径（可选）")
    parser.add_argument(
        "--glob",
        type=str,
        default="job_eval_results_*.jsonl",
        help="未传 --input 时用于查找最新文件",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.60, help="低置信度阈值，默认0.60"
    )
    parser.add_argument(
        "--out-prefix", type=str, default="qc_report", help="输出文件名前缀"
    )
    args = parser.parse_args()

    input_path = args.input or infer_latest_jsonl(args.glob)
    ok_rows, err_rows = load_jsonl(input_path)
    if not ok_rows and not err_rows:
        raise RuntimeError("输入文件为空，没有可分析数据")

    dist = dim_distribution(ok_rows)
    low_rows = collect_low_confidence(ok_rows, args.threshold)
    fail_stats = summarize_failures(err_rows)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{args.out_prefix}_{ts}.md"
    low_csv = f"low_confidence_{ts}.csv"

    write_report_md(
        report_path=report_path,
        input_path=input_path,
        ok_rows=ok_rows,
        err_rows=err_rows,
        dist=dist,
        low_rows=low_rows,
        fail_stats=fail_stats,
        threshold=args.threshold,
    )
    write_low_conf_csv(low_csv, low_rows)

    print(f"报告已生成: {report_path}")
    print(f"低置信度清单: {low_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

