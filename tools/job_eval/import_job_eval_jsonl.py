import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from neo4j import GraphDatabase

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


def load_dotenv_if_exists(env_path: str) -> None:
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    out: List[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        else:
            text = json.dumps(item, ensure_ascii=False)
        if text:
            out.append(text[:500])
    return out


def parse_result_line(line: str) -> Tuple[bool, Dict[str, Any], str]:
    try:
        row = json.loads(line)
    except json.JSONDecodeError as exc:
        return False, {}, f"json_decode_error:{exc}"

    if not isinstance(row, dict):
        return False, {}, "not_json_object"

    if "error" in row and "scores" not in row:
        return False, {}, f"skip_error_line:{row.get('error')}"

    job_id = str(row.get("job_id") or "").strip()
    if not job_id:
        return False, {}, "missing_job_id"

    scores = row.get("scores")
    conf = row.get("confidence")
    if not isinstance(scores, dict) or not isinstance(conf, dict):
        return False, {}, "missing_scores_or_confidence"

    normalized_scores: Dict[str, float] = {}
    normalized_conf: Dict[str, float] = {}

    for k in DIM_KEYS:
        normalized_scores[k] = round(_safe_float(scores.get(k), 0.0), 2)
    for k in CONF_KEYS:
        v = _safe_float(conf.get(k), 0.0)
        if v < 0:
            v = 0.0
        if v > 1:
            v = 1.0
        normalized_conf[k] = round(v, 4)

    evidence_list = _to_string_list(row.get("evidence"))
    risk_flags_list = _to_string_list(row.get("risk_flags"))

    return (
        True,
        {
            "job_id": job_id,
            "scores": normalized_scores,
            "confidence": normalized_conf,
            "evidence": evidence_list[:16],
            "risk_flags": risk_flags_list[:32],
        },
        "",
    )


def write_batch(
    driver: Any,
    database: str,
    rows: List[Dict[str, Any]],
    cap_version: str,
) -> Tuple[int, List[str]]:
    if not rows:
        return 0, []

    query = """
    UNWIND $rows AS row
    OPTIONAL MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = row.job_id
    FOREACH (_ IN CASE WHEN j IS NULL THEN [] ELSE [1] END |
      SET
        j.cap_req_theory = toFloat(row.scores.cap_req_theory),
        j.cap_req_cross = toFloat(row.scores.cap_req_cross),
        j.cap_req_practice = toFloat(row.scores.cap_req_practice),
        j.cap_req_digital = toFloat(row.scores.cap_req_digital),
        j.cap_req_innovation = toFloat(row.scores.cap_req_innovation),
        j.cap_req_teamwork = toFloat(row.scores.cap_req_teamwork),
        j.cap_req_social = toFloat(row.scores.cap_req_social),
        j.cap_req_growth = toFloat(row.scores.cap_req_growth),
        j.cap_conf_theory = toFloat(row.confidence.cap_conf_theory),
        j.cap_conf_cross = toFloat(row.confidence.cap_conf_cross),
        j.cap_conf_practice = toFloat(row.confidence.cap_conf_practice),
        j.cap_conf_digital = toFloat(row.confidence.cap_conf_digital),
        j.cap_conf_innovation = toFloat(row.confidence.cap_conf_innovation),
        j.cap_conf_teamwork = toFloat(row.confidence.cap_conf_teamwork),
        j.cap_conf_social = toFloat(row.confidence.cap_conf_social),
        j.cap_conf_growth = toFloat(row.confidence.cap_conf_growth),
        j.cap_evidence = row.evidence,
        j.cap_risk_flags = row.risk_flags,
        j.cap_version = $cap_version,
        j.cap_updated_at = datetime()
    )
    RETURN row.job_id AS job_id, j IS NOT NULL AS matched
    """

    with driver.session(database=database) as session:
        res = list(session.run(query, {"rows": rows, "cap_version": cap_version}))

    matched = sum(1 for r in res if bool(r["matched"]))
    unmatched = [str(r["job_id"]) for r in res if not bool(r["matched"])]
    return matched, unmatched


def main() -> int:
    parser = argparse.ArgumentParser(description="将 --dry-run 产出的 job_eval jsonl 回灌到 Neo4j")
    parser.add_argument("--input", required=True, help="jsonl 文件路径")
    parser.add_argument("--env", default=".env", help="环境变量文件路径")
    parser.add_argument("--batch-size", type=int, default=300, help="每批写入数量")
    parser.add_argument("--database", default=None, help="Neo4j database，默认读 NEO4J_DATABASE")
    parser.add_argument(
        "--cap-version",
        default=None,
        help="写回 cap_version，默认使用 CAP_VERSION 或 replay_<UTC时间>",
    )
    parser.add_argument(
        "--include-inferred",
        action="store_true",
        help="默认跳过 job_id 以 ::inferred 结尾的全零占位数据；加此参数则写入",
    )
    parser.add_argument(
        "--unmatched-output",
        default=None,
        help="未命中的 job_id 输出文件（默认 unmatched_<时间>.txt）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"输入文件不存在: {args.input}")
        return 1

    load_dotenv_if_exists(args.env)

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")
    neo4j_database = args.database or os.getenv("NEO4J_DATABASE", "neo4j")
    cap_version = args.cap_version or os.getenv("CAP_VERSION") or (
        "replay_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )

    if not neo4j_password:
        print("缺少 NEO4J_PASSWORD，无法连接 Neo4j")
        return 1

    rows: List[Dict[str, Any]] = []
    parsed_total = 0
    skip_total = 0
    parse_fail_total = 0
    unmatched_total: List[str] = []
    matched_total = 0

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue

                ok, parsed, reason = parse_result_line(line)
                if not ok:
                    parse_fail_total += 1
                    if line_no <= 5:
                        print(f"[line {line_no}] 跳过: {reason}")
                    continue

                parsed_total += 1
                if (not args.include_inferred) and parsed["job_id"].endswith("::inferred"):
                    skip_total += 1
                    continue

                rows.append(parsed)
                if len(rows) >= max(1, int(args.batch_size)):
                    matched, unmatched = write_batch(driver, neo4j_database, rows, cap_version)
                    matched_total += matched
                    unmatched_total.extend(unmatched)
                    print(
                        f"已写入批次: batch={len(rows)} matched={matched} unmatched={len(unmatched)}"
                    )
                    rows = []

        if rows:
            matched, unmatched = write_batch(driver, neo4j_database, rows, cap_version)
            matched_total += matched
            unmatched_total.extend(unmatched)
            print(f"已写入批次: batch={len(rows)} matched={matched} unmatched={len(unmatched)}")

    finally:
        driver.close()

    unmatched_output = args.unmatched_output or (
        f"unmatched_job_ids_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    )
    if unmatched_total:
        with open(unmatched_output, "w", encoding="utf-8") as fw:
            for job_id in unmatched_total:
                fw.write(job_id + "\n")

    print(
        "回灌完成: "
        f"parsed={parsed_total}, skipped_inferred={skip_total}, parse_fail={parse_fail_total}, "
        f"matched={matched_total}, unmatched={len(unmatched_total)}, cap_version={cap_version}, "
        f"database={neo4j_database}"
    )
    if unmatched_total:
        print(f"未命中列表已输出: {unmatched_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
