"""Graph ETL 域：业务编排层。"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from flask import current_app
from openai import OpenAI

from app.domains.graph.constants import (
    DEFAULT_BATCH_SIZE,
    JOB_EXTRACTION_SYSTEM_PROMPT,
    MAX_RETRIES,
    PROMOTION_SYSTEM_PROMPT,
    REQUIRED_CN_COLUMNS,
    SOURCE_TAG,
    PromotionEdge,
    build_ai_payload,
    build_company_prompt,
    compute_core_templates,
    normalize_key,
    normalize_text,
)
from app.domains.graph.repository import (
    clear_all_graph,
    delete_edges_by_source,
    fetch_all_jobs,
    get_graph_statistics,
    merge_batch_to_neo4j,
    persist_promotion_edges,
)
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings
from app.infrastructure.privacy import privacy_mode_enabled, redact_payload


# ============================================================
# 异常
# ============================================================

class GraphServiceError(Exception):
    """Graph ETL 业务异常。"""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


# ============================================================
# LLM 客户端
# ============================================================

def _build_graph_llm_client() -> OpenAI:
    """构建 graph ETL 专用 OpenAI 兼容客户端。"""
    api_key = str(current_app.config.get("GRAPH_LLM_API_KEY") or "").strip()
    if not api_key:
        raise GraphServiceError("未配置 GRAPH_LLM_API_KEY，无法调用大模型", 500)
    base_url = str(current_app.config.get("GRAPH_LLM_BASE_URL") or "").strip()
    timeout = int(current_app.config.get("GRAPH_LLM_TIMEOUT_SECONDS", 120))
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def _llm_model() -> str:
    return str(current_app.config.get("GRAPH_LLM_MODEL", "doubao-seed-2-0-mini-260215"))


# ============================================================
# LLM JSON 解析
# ============================================================

def _strip_json_fence(text: str) -> str:
    """剥离 ```json ... ``` 围栏。"""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if t.startswith("```"):
        return t.replace("```json", "").replace("```", "").strip()
    return t


def _parse_json_object(text: str) -> Dict[str, Any]:
    """宽松解析 JSON：尝试直接解析 → 剥离围栏 → 扫描首尾花括号。"""
    raw = normalize_text(text)
    if not raw:
        raise ValueError("模型返回为空")

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", raw)
    if fenced:
        raw = fenced.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


# ============================================================
# 岗位批量提取 LLM 调用
# ============================================================

def _call_llm_batch_extract(payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """调用 LLM 批量提取岗位结构化字段。"""
    client = _build_graph_llm_client()
    model = _llm_model()

    sys_content = JOB_EXTRACTION_SYSTEM_PROMPT
    user_content = json.dumps(payload, ensure_ascii=False)

    # 隐私脱敏
    if privacy_mode_enabled():
        safe_payload = redact_payload(payload)
        user_content = json.dumps(safe_payload, ensure_ascii=False)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_content},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                stream=False,
                response_format={"type": "json_object"},
                timeout=60.0,
            )
            content = _strip_json_fence((resp.choices[0].message.content or "").strip())
            parsed = json.loads(content)
            if not isinstance(parsed, dict) or "records" not in parsed:
                raise ValueError("LLM 返回格式不符合预期，缺少 records 字段")
            if not isinstance(parsed["records"], list):
                raise ValueError("LLM 返回 records 不是数组")
            return parsed["records"]
        except Exception as exc:
            if attempt == MAX_RETRIES:
                print(f"[WARN] 批量提取 LLM 调用失败（第 {attempt} 次）: {exc}，返回空结构兜底")
                return []
            wait_seconds = attempt * 2
            print(f"[WARN] 批量提取 LLM 调用失败，第 {attempt} 次重试: {exc}")
            time.sleep(wait_seconds)
    return []


# ============================================================
# 晋升边推断 LLM 调用
# ============================================================

def _call_llm_for_promotions(
    company: str, jobs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """调用 LLM 推断单个公司的晋升边。"""
    client = _build_graph_llm_client()
    model = _llm_model()

    prompt = build_company_prompt(company, jobs)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": PROMOTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                timeout=60.0,
            )
            content = normalize_text(resp.choices[0].message.content)
            obj = _parse_json_object(content)
            edges = obj.get("edges", []) if isinstance(obj, dict) else []
            if isinstance(edges, list):
                return [x for x in edges if isinstance(x, dict)]
            return []
        except Exception as exc:
            if attempt == MAX_RETRIES:
                print(f"[WARN] 公司 {company} 晋升推断失败: {exc}")
                return []
            print(f"[WARN] 公司 {company} 晋升推断失败，第 {attempt} 次重试: {exc}")
    return []


# ============================================================
# 晋升边校验
# ============================================================

def _build_edges_with_validation(
    company: str,
    jobs: List[Dict[str, Any]],
    model_edges: List[Dict[str, Any]],
    min_confidence: float,
) -> List[PromotionEdge]:
    """校验并构建 PromotionEdge 列表。"""
    title_to_job: Dict[str, Dict[str, Any]] = {
        normalize_key(j["title"]): j for j in jobs
    }

    edges: List[PromotionEdge] = []
    seen: set = set()
    for item in model_edges:
        from_title = normalize_text(item.get("from_title"))
        to_title = normalize_text(item.get("to_title"))
        reason = normalize_text(item.get("reason")) or "模型推断"

        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))
        if confidence < min_confidence:
            continue

        src = title_to_job.get(normalize_key(from_title))
        dst = title_to_job.get(normalize_key(to_title))
        if not src or not dst:
            continue
        if src.get("job_key") == dst.get("job_key"):
            continue

        # 防止逆转方向：目标 career_score 应大于源
        if float(dst.get("career_score", 0)) <= float(src.get("career_score", 0)):
            continue

        pair_key = (src["job_key"], dst["job_key"])
        if pair_key in seen:
            continue
        seen.add(pair_key)

        edges.append(
            PromotionEdge(
                from_key=src["job_key"],
                to_key=dst["job_key"],
                company=company,
                from_title=src["title"],
                to_title=dst["title"],
                reason=reason,
                confidence=round(confidence, 4),
            )
        )

    return edges


# ============================================================
# 晋升边备份
# ============================================================

def _backup_edges_json(
    backup_dir: str,
    edges: List[PromotionEdge],
    metadata: Dict[str, Any],
) -> str:
    """将晋升边备份为 JSON 文件，返回文件路径。"""
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(backup_dir, f"promotion_edges_backup_{timestamp}.json")
    payload = {
        "metadata": metadata,
        "edges": [
            {
                "from_key": e.from_key,
                "to_key": e.to_key,
                "company": e.company,
                "from_title": e.from_title,
                "to_title": e.to_title,
                "reason": e.reason,
                "confidence": e.confidence,
            }
            for e in edges
        ],
    }
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return file_path


# ============================================================
# job_titles 表同步
# ============================================================

def _sync_job_titles(df: pd.DataFrame) -> None:
    """根据导入的 DataFrame 更新 MySQL job_titles 表。"""
    from app.db import db_cursor

    col_name = "name"  # COLUMN_ALIASES 已将"岗位名称"映射为 name
    col_company = "company"
    col_code = "job_code"

    titles_series = df[col_name].astype(str).str.strip()
    titles_series = titles_series.replace({"nan": "", "None": "", "NaT": ""})
    valid = df[titles_series != ""].copy()
    if valid.empty:
        return

    valid["_title"] = valid[col_name].astype(str).str.strip()

    stats = (
        valid.groupby("_title", dropna=False)
        .agg(
            record_count=(col_name, "size"),
            company_count=(col_company, lambda s: s.astype(str).str.strip().nunique()),
            job_code_count=(col_code, lambda s: s.astype(str).str.strip().nunique()),
        )
        .reset_index()
        .rename(columns={"_title": "title"})
    )

    with db_cursor() as (conn, cur):
        for _, row in stats.iterrows():
            cur.execute(
                """
                INSERT INTO job_titles (title, record_count, company_count, job_code_count)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    record_count = VALUES(record_count),
                    company_count = VALUES(company_count),
                    job_code_count = VALUES(job_code_count)
                """,
                (
                    row["title"],
                    int(row["record_count"]),
                    int(row["company_count"]),
                    int(row["job_code_count"]),
                ),
            )
        conn.commit()


# ============================================================
# 公共服务函数
# ============================================================

def import_jobs_from_excel(
    excel_path: str | None = None,
    uploaded_file=None,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    clear_all: bool = False,
) -> Dict[str, Any]:
    """
    从 Excel 导入岗位到 Neo4j。

    Args:
        excel_path: 服务器上的 Excel 文件路径（与 uploaded_file 二选一）
        uploaded_file: Flask FileStorage 上传文件对象
        batch_size: 每批处理条数
        clear_all: 是否先清空图谱再导入
    """
    if batch_size <= 0:
        raise GraphServiceError("batch_size 必须大于 0")

    # 1. 加载 Excel
    try:
        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file)
        elif excel_path:
            df = pd.read_excel(excel_path)
        else:
            raise GraphServiceError("请提供 excel_path 或 uploaded_file")
    except ImportError:
        raise GraphServiceError("读取 .xls 需要安装依赖：pip install xlrd>=2.0.1", 500)
    except FileNotFoundError:
        raise GraphServiceError(f"未找到数据文件: {excel_path}", 400)
    except Exception as exc:
        raise GraphServiceError(f"读取 Excel 失败: {exc}", 500)

    # 2. 校验列名
    missing_cols = [c for c in REQUIRED_CN_COLUMNS if c not in df.columns]
    if missing_cols:
        raise GraphServiceError(f"Excel 缺少必要字段: {missing_cols}")

    from app.domains.graph.constants import COLUMN_ALIASES

    df = df.rename(columns=COLUMN_ALIASES)

    # 3. 获取 Neo4j 连接
    uri, user, password, database = neo4j_settings()
    if not password:
        raise GraphServiceError("未配置 NEO4J_PASSWORD", 500)
    driver = neo4j_driver(uri, user, password)

    # 4. 可选清空
    if clear_all:
        clear_all_graph(driver, database)

    # 5. 计算 core_templates
    core_templates = compute_core_templates(df)

    # 6. 分批处理
    total = len(df)
    batches_completed = 0
    batches_failed = 0
    errors: List[str] = []

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_df = df.iloc[start:end].copy()
        print(f"[INFO] 处理批次 {start}-{end - 1} / {total - 1}")

        # LLM 提取
        try:
            payload = build_ai_payload(batch_df)
            ai_records = _call_llm_batch_extract(payload)
        except Exception as exc:
            errors.append(f"批次 {start}-{end - 1} LLM 调用失败: {exc}")
            batches_failed += 1
            continue

        # Neo4j 写入
        try:
            merge_batch_to_neo4j(
                driver=driver,
                database=database,
                batch_df=batch_df,
                ai_records=ai_records,
                core_templates=core_templates,
            )
            batches_completed += 1
        except Exception as exc:
            errors.append(f"批次 {start}-{end - 1} 写入 Neo4j 失败: {exc}")
            batches_failed += 1

    # 7. 同步 job_titles 表
    try:
        _sync_job_titles(df)
    except Exception as exc:
        errors.append(f"同步 job_titles 表失败: {exc}")

    return {
        "total_jobs": total,
        "batches_completed": batches_completed,
        "batches_failed": batches_failed,
        "core_templates": sorted(core_templates),
        "errors": errors,
    }


def generate_promotion_edges(
    *,
    min_confidence: float = 0.55,
    min_company_jobs: int = 2,
    clear_existing: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    生成晋升边（VERTICAL_UP）。

    Args:
        min_confidence: 最低置信度阈值
        min_company_jobs: 每公司最少岗位数
        clear_existing: 是否先删除已有晋升边
        dry_run: True 时只预览不写入
    """
    min_confidence = max(0.0, min(1.0, min_confidence))

    uri, user, password, database = neo4j_settings()
    if not password:
        raise GraphServiceError("未配置 NEO4J_PASSWORD", 500)
    driver = neo4j_driver(uri, user, password)

    # 1. 获取所有 Job
    jobs = fetch_all_jobs(driver, database)

    # 2. 按公司分组
    company_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for j in jobs:
        company_groups[j.company].append(
            {
                "job_key": j.job_key,
                "title": j.title,
                "experience_years": j.experience_years,
                "location": j.location,
                "career_score": j.career_score,
            }
        )

    # 3. 逐公司推断
    all_edges: List[PromotionEdge] = []
    checked_companies = 0

    for company, group in sorted(
        company_groups.items(), key=lambda x: len(x[1]), reverse=True
    ):
        # 去重标题（保留 career_score 最高的）
        best: Dict[str, Dict[str, Any]] = {}
        for job in group:
            key = normalize_key(job["title"])
            old = best.get(key)
            if old is None or job["career_score"] > old["career_score"]:
                best[key] = job
        compact_group = list(best.values())

        if len(compact_group) < max(2, min_company_jobs):
            continue

        checked_companies += 1
        subset = sorted(compact_group, key=lambda x: x["career_score"])

        raw_edges = _call_llm_for_promotions(company, subset)
        validated = _build_edges_with_validation(
            company=company,
            jobs=subset,
            model_edges=raw_edges,
            min_confidence=min_confidence,
        )
        all_edges.extend(validated)

        print(
            f"[INFO] {company}: 输入岗位 {len(subset)}，"
            f"模型输出 {len(raw_edges)}，校验后 {len(validated)}"
        )

    # 4. 备份
    backup_dir = str(
        current_app.config.get("GRAPH_PROMOTION_BACKUP_DIR") or "promotion_backups"
    )
    backup_file = _backup_edges_json(
        backup_dir=backup_dir,
        edges=all_edges,
        metadata={
            "source_tag": SOURCE_TAG,
            "model": _llm_model(),
            "checked_companies": checked_companies,
            "candidate_count": len(all_edges),
            "dry_run": dry_run,
            "min_confidence": min_confidence,
        },
    )

    # 5. Dry-run 模式：返回预览
    if dry_run:
        preview = [
            {
                "company": e.company,
                "from_title": e.from_title,
                "to_title": e.to_title,
                "confidence": e.confidence,
                "reason": e.reason,
            }
            for e in all_edges[:50]  # 只返回前 50 条预览
        ]
        return {
            "checked_companies": checked_companies,
            "candidate_edges": len(all_edges),
            "preview": preview,
            "backup_file": backup_file,
            "dry_run": True,
        }

    # 6. 写入 Neo4j
    if clear_existing:
        deleted = delete_edges_by_source(driver, database, SOURCE_TAG)
        print(f"[INFO] 删除旧晋升边 (source={SOURCE_TAG}): {deleted}")

    created = persist_promotion_edges(driver, database, all_edges, SOURCE_TAG)
    print(f"[INFO] 已写入/更新 VERTICAL_UP 关系: {created}")

    return {
        "checked_companies": checked_companies,
        "candidate_edges": len(all_edges),
        "created_edges": created,
        "backup_file": backup_file,
        "dry_run": False,
    }


def clear_graph() -> Dict[str, Any]:
    """清空整个 Neo4j 图谱。"""
    uri, user, password, database = neo4j_settings()
    if not password:
        raise GraphServiceError("未配置 NEO4J_PASSWORD", 500)
    driver = neo4j_driver(uri, user, password)
    return clear_all_graph(driver, database)


def get_stats() -> Dict[str, Any]:
    """返回图谱统计信息。"""
    uri, user, password, database = neo4j_settings()
    if not password:
        raise GraphServiceError("未配置 NEO4J_PASSWORD", 500)
    driver = neo4j_driver(uri, user, password)
    return get_graph_statistics(driver, database)


def get_job_titles() -> List[Dict[str, Any]]:
    """查询 MySQL job_titles 表，返回所有岗位名称统计。"""
    from app.db import db_cursor

    with db_cursor() as (_, cur):
        cur.execute(
            """
            SELECT id, title, record_count, company_count, job_code_count, updated_at
            FROM job_titles
            ORDER BY record_count DESC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "record_count": r["record_count"],
                "company_count": r["company_count"],
                "job_code_count": r["job_code_count"],
                "updated_at": str(r["updated_at"]) if r.get("updated_at") else "",
            }
            for r in rows
        ]


def generate_qc_report(input_file: str = "", threshold: float = 0.60) -> Dict[str, Any]:
    """
    从 job_eval_results JSONL 文件生成质检报告。

    Args:
        input_file: JSONL 文件路径（每行一个 {job_id, scores, confidence, evidence, risk_flags} 或 {job_id, error}）
        threshold: 低置信度阈值，默认 0.60
    """
    import csv
    import glob
    import io
    from collections import Counter
    from statistics import mean

    from app.infrastructure.neo4j import CONF_KEYS, DIM_KEYS

    # 查找输入文件
    if not input_file:
        candidates = sorted(
            glob.glob("job_eval_results_*.jsonl"),
            key=os.path.getmtime,
            reverse=True,
        )
        if not candidates:
            raise GraphServiceError("未找到 job_eval_results_*.jsonl 文件，请指定 input_file", 400)
        input_file = candidates[0]

    # 加载
    ok_rows: List[Dict[str, Any]] = []
    err_rows: List[Dict[str, Any]] = []
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if "error" in obj:
                    err_rows.append(obj)
                else:
                    ok_rows.append(obj)
    except FileNotFoundError:
        raise GraphServiceError(f"未找到文件: {input_file}", 400)

    if not ok_rows and not err_rows:
        raise GraphServiceError("输入文件为空，没有可分析数据", 400)

    # 分数分布
    def _bucket(v: float) -> str:
        if v < 40: return "0-39"
        if v < 60: return "40-59"
        if v < 80: return "60-79"
        return "80-100"

    dist: Dict[str, Dict[str, int]] = {}
    for k in DIM_KEYS:
        c = Counter()
        for row in ok_rows:
            c[_bucket(float(row.get("scores", {}).get(k, 0)))] += 1
        dist[k] = {b: c.get(b, 0) for b in ["0-39", "40-59", "60-79", "80-100"]}

    # 平均分
    avg_scores = {
        k: round(mean(float(r.get("scores", {}).get(k, 0)) for r in ok_rows), 2)
        if ok_rows else 0.0
        for k in DIM_KEYS
    }

    # 低置信度
    low_rows: List[Dict[str, Any]] = []
    for row in ok_rows:
        conf = row.get("confidence", {})
        min_k, min_v = None, 1.0
        low_dims: List[str] = []
        for k in CONF_KEYS:
            v = float(conf.get(k, 0))
            if v < threshold:
                low_dims.append(k)
            if v < min_v:
                min_v, min_k = v, k
        if low_dims:
            low_rows.append({
                "job_id": row.get("job_id", ""),
                "min_conf_key": min_k or "",
                "min_conf_value": round(min_v, 4),
                "low_conf_dims": ",".join(low_dims),
                "risk_flags": ",".join(row.get("risk_flags", [])),
            })
    low_rows.sort(key=lambda x: x["min_conf_value"])

    # 失败统计
    fail_counter = Counter()
    for e in err_rows:
        msg = str(e.get("error", "unknown"))
        fail_counter[msg.split(":", 1)[0][:120]] += 1

    total = len(ok_rows) + len(err_rows)
    success_rate = (len(ok_rows) / total * 100) if total else 0

    # 生成 Markdown 报告
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"qc_report_{ts}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Job评估质检报告\n\n")
        f.write(f"- 输入文件: `{input_file}`\n")
        f.write(f"- 生成时间: `{datetime.now().isoformat(timespec='seconds')}`\n")
        f.write(f"- 低置信度阈值: `{threshold}`\n\n")
        f.write("## 1. 总体统计\n\n")
        f.write(f"- 总条数: `{total}`\n")
        f.write(f"- 成功: `{len(ok_rows)}`\n")
        f.write(f"- 失败: `{len(err_rows)}`\n")
        f.write(f"- 成功率: `{success_rate:.2f}%`\n")
        f.write(f"- 低置信度: `{len(low_rows)}`\n\n")
        f.write("## 2. 八维平均分\n\n")
        for k in DIM_KEYS:
            f.write(f"- `{k}`: `{avg_scores[k]}`\n")
        f.write("\n## 3. 分数分布\n\n")
        f.write("| 维度 | 0-39 | 40-59 | 60-79 | 80-100 |\n")
        f.write("|---|---:|---:|---:|---:|\n")
        for k in DIM_KEYS:
            d = dist[k]
            f.write(f"| `{k}` | {d['0-39']} | {d['40-59']} | {d['60-79']} | {d['80-100']} |\n")
        f.write("\n## 4. 低置信度名单（Top 30）\n\n")
        f.write("| job_id | 最低维度 | 值 | 低置信度维度 |\n")
        f.write("|---|---|---:|---|\n")
        for r in low_rows[:30]:
            f.write(f"| `{r['job_id']}` | `{r['min_conf_key']}` | {r['min_conf_value']} | `{r['low_conf_dims']}` |\n")
        f.write("\n## 5. 失败原因（Top 20）\n\n")
        if fail_counter:
            for reason, cnt in fail_counter.most_common(20):
                f.write(f"- `{reason}`: `{cnt}`\n")
        else:
            f.write("- 无失败\n")

    # 低置信度 CSV
    csv_path = f"low_confidence_{ts}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["job_id", "min_conf_key", "min_conf_value", "low_conf_dims", "risk_flags"])
        writer.writeheader()
        for r in low_rows:
            writer.writerow(r)

    return {
        "total": total,
        "success": len(ok_rows),
        "failed": len(err_rows),
        "success_rate": round(success_rate, 2),
        "low_confidence_count": len(low_rows),
        "avg_scores": avg_scores,
        "distribution": dist,
        "top_low_confidence": low_rows[:10],
        "top_failures": [{"reason": r, "count": c} for r, c in fail_counter.most_common(10)],
        "report_path": report_path,
        "csv_path": csv_path,
    }
