"""Graph ETL 域：业务编排层。"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

import pandas as pd
from flask import current_app
from openai import OpenAI

from app.domains.graph.constants import (
    DEFAULT_BATCH_SIZE,
    JOB_EXTRACTION_SYSTEM_PROMPT,
    MAX_RETRIES,
    PROMOTION_SYSTEM_PROMPT,
    REQUIRED_CN_COLUMNS,
    PromotionEdge,
    build_ai_payload,
    build_company_prompt,
    compute_core_templates,
    normalize_key,
    normalize_text,
)
from app.domains.graph.repository import (
    clear_all_graph,
    fetch_job_import_fingerprints,
    finish_import_run,
    get_graph_statistics,
    mark_existing_jobs_seen,
    merge_batch_to_neo4j,
    prune_missing_jobs,
    start_import_run,
    list_import_runs,
)
from app.domains.graph.incremental import (
    deduplicate_jobs,
    import_keys,
    normalize_source_id,
    plan_incremental_rows,
)
from app.domains.settings.service import setting
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
    timeout = int(setting("GRAPH_LLM_TIMEOUT_SECONDS", 120))
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def _llm_model() -> str:
    return str(setting("GRAPH_LLM_MODEL", "doubao-seed-2-0-mini-260215"))


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

    retry_count = max(1, int(setting("GRAPH_MAX_RETRIES", MAX_RETRIES)))
    timeout = float(setting("GRAPH_LLM_TIMEOUT_SECONDS", 120))
    for attempt in range(1, retry_count + 1):
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
                timeout=timeout,
            )
            content = _strip_json_fence((resp.choices[0].message.content or "").strip())
            parsed = json.loads(content)
            if not isinstance(parsed, dict) or "records" not in parsed:
                raise ValueError("LLM 返回格式不符合预期，缺少 records 字段")
            if not isinstance(parsed["records"], list):
                raise ValueError("LLM 返回 records 不是数组")
            return parsed["records"]
        except Exception as exc:
            if attempt == retry_count:
                raise GraphServiceError(
                    f"批量提取 LLM 调用失败（已重试 {attempt} 次）: {exc}",
                    502,
                ) from exc
            wait_seconds = min(2 ** (attempt - 1), 8)
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

    max_retries = max(1, int(setting("GRAPH_MAX_RETRIES", MAX_RETRIES)))
    timeout = float(setting("GRAPH_LLM_TIMEOUT_SECONDS", 120))
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": PROMOTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                timeout=timeout,
            )
            content = normalize_text(resp.choices[0].message.content)
            obj = _parse_json_object(content)
            edges = obj.get("edges", []) if isinstance(obj, dict) else []
            if isinstance(edges, list):
                return [x for x in edges if isinstance(x, dict)]
            return []
        except Exception as exc:
            if attempt == max_retries:
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

def _sync_job_titles_from_graph(titles: List[Dict[str, Any]]) -> None:
    """Mirror Neo4j's post-commit JobTitle statistics into MySQL."""
    from app.db import db_cursor

    with db_cursor() as (conn, cur):
        for row in titles:
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
                    row["name"],
                    int(row["count"]),
                    int(row["company_count"]),
                    int(row["job_code_count"]),
                ),
            )
        names = [str(row["name"]) for row in titles]
        if names:
            placeholders = ",".join(["%s"] * len(names))
            cur.execute(f"DELETE FROM job_titles WHERE title NOT IN ({placeholders})", names)
        else:
            cur.execute("DELETE FROM job_titles")
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
    mode: str = "merge",
    source_id: str | None = None,
) -> Dict[str, Any]:
    """
    从 Excel 导入岗位到 Neo4j。

    Args:
        excel_path: 服务器上的 Excel 文件路径（与 uploaded_file 二选一）
        uploaded_file: Flask FileStorage 上传文件对象
        batch_size: 每批处理条数
        clear_all: 兼容旧接口；是否先清空图谱再导入
        mode: merge 仅新增/更新，snapshot 还会删除同 source_id 中未出现的岗位
        source_id: 数据源稳定标识；snapshot 模式必须显式提供
    """
    raise GraphServiceError("直接图谱写入已停用，请创建 graph_update_task", 410)
    if batch_size <= 0 or batch_size > 1000:
        raise GraphServiceError("batch_size 必须在 1 到 1000 之间")
    mode = str(mode or "merge").strip().lower()
    if mode not in {"merge", "snapshot"}:
        raise GraphServiceError("mode 仅支持 merge 或 snapshot")
    if mode == "snapshot" and not str(source_id or "").strip():
        raise GraphServiceError("snapshot 模式必须显式提供 source_id")

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
    df, duplicate_rows = deduplicate_jobs(df)
    resolved_source_id = normalize_source_id(source_id or excel_path or getattr(uploaded_file, "filename", None))
    run_id = uuid4().hex

    # 3. 获取 Neo4j 连接
    uri, user, password, database = neo4j_settings()
    if not password:
        raise GraphServiceError("未配置 NEO4J_PASSWORD", 500)
    driver = neo4j_driver(uri, user, password)
    from app.domains.graph.repository import ensure_graph_schema
    ensure_graph_schema(driver, database)

    # 4. 规划真正的增量：只有新增或内容指纹变化的岗位进入 LLM。
    keys = import_keys(df)
    existing = fetch_job_import_fingerprints(driver, database, keys)
    extraction_version = f"{_llm_model()}:v1"
    changed_df, unchanged_keys, fingerprints = plan_incremental_rows(
        df,
        existing,
        extraction_version=extraction_version,
    )

    # 5. 可选清空（仅保留旧接口兼容；新调用应使用 source-scoped snapshot）。
    if clear_all:
        clear_all_graph(driver, database)
        existing = {}
        changed_df = df
        unchanged_keys = []

    start_import_run(
        driver,
        database,
        run_id=run_id,
        source_id=resolved_source_id,
        mode=mode,
        input_rows=len(df),
        changed_jobs=len(changed_df),
    )

    # 6. 在处理前标记已存在输入，避免某批更新失败后被 snapshot 误删。
    mark_existing_jobs_seen(
        driver,
        database,
        job_keys=keys,
        run_id=run_id,
        source_id=resolved_source_id,
    )

    # 7. 计算 core_templates
    core_templates = compute_core_templates(df)

    # 8. 只处理发生变化的行
    total = len(df)
    changed_total = len(changed_df)
    batches_completed = 0
    batches_failed = 0
    jobs_written = 0
    errors: List[str] = []

    for start in range(0, changed_total, batch_size):
        end = min(start + batch_size, changed_total)
        batch_df = changed_df.iloc[start:end].copy()
        print(f"[INFO] 处理增量批次 {start}-{end - 1} / {changed_total - 1}")

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
            write_result = merge_batch_to_neo4j(
                driver=driver,
                database=database,
                batch_df=batch_df,
                ai_records=ai_records,
                core_templates=core_templates,
                run_id=run_id,
                source_id=resolved_source_id,
                fingerprints=fingerprints,
            )
            jobs_written += int(write_result.get("written", 0))
            batches_completed += 1
        except Exception as exc:
            errors.append(f"批次 {start}-{end - 1} 写入 Neo4j 失败: {exc}")
            batches_failed += 1

    # 9. snapshot 删除严格限定在 source_id，且有批次失败时禁止 prune。
    pruned_jobs = 0
    if mode == "snapshot" and batches_failed == 0:
        pruned_jobs = prune_missing_jobs(
            driver,
            database,
            run_id=run_id,
            source_id=resolved_source_id,
        )

    # 10. 从 Neo4j 实际状态重建 JobTitle，再同步 MySQL 统计。
    try:
        from app.domains.graph.sync_service import sync_job_titles

        title_result = sync_job_titles()
        _sync_job_titles_from_graph(title_result.get("titles", []))
    except Exception as exc:
        errors.append(f"同步 JobTitle 统计失败: {exc}")

    finish_import_run(
        driver,
        database,
        run_id=run_id,
        status="succeeded" if not errors else "partial",
        jobs_written=jobs_written,
        unchanged_jobs=len(unchanged_keys),
        pruned_jobs=pruned_jobs,
        error_count=len(errors),
    )

    return {
        "run_id": run_id,
        "source_id": resolved_source_id,
        "mode": mode,
        "total_jobs": total,
        "duplicate_rows": duplicate_rows,
        "new_or_changed_jobs": changed_total,
        "unchanged_jobs": len(unchanged_keys),
        "jobs_written": jobs_written,
        "pruned_jobs": pruned_jobs,
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
) -> Dict[str, Any]:
    """旧 Job 层晋升边生成逻辑已废弃。"""
    raise GraphServiceError(
        "generate_promotion_edges 已废弃；请使用 JobTitle 层的 "
        "/api/graph/sync/job-titles 和 /api/graph/generate/promotion-paths。",
        410,
    )


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
    stats = get_graph_statistics(driver, database)
    with driver.session(database=database) as session:
        row = session.run("""
        MATCH (j:Job)
        WITH count(j) AS jobs,
             sum(CASE WHEN j.cap_version IS NULL OR j.cap_req_theory IS NULL OR j.cap_conf_theory IS NULL THEN 1 ELSE 0 END) AS capability_missing,
             sum(CASE WHEN j.cap_version IS NOT NULL AND j.cap_version <> $cap_version THEN 1 ELSE 0 END) AS capability_stale,
             sum(CASE WHEN j.cap_conf_theory < 0.6 OR j.cap_conf_cross < 0.6 OR j.cap_conf_practice < 0.6 OR j.cap_conf_digital < 0.6 OR j.cap_conf_innovation < 0.6 OR j.cap_conf_teamwork < 0.6 OR j.cap_conf_social < 0.6 OR j.cap_conf_growth < 0.6 THEN 1 ELSE 0 END) AS low_confidence,
             sum(CASE WHEN j.salary_parse_version IS NULL OR j.salary_parse_version <> $salary_version THEN 1 ELSE 0 END) AS salary_stale,
             sum(CASE WHEN j.source='inferred' THEN 1 ELSE 0 END) AS inferred_jobs
        OPTIONAL MATCH (jt:JobTitle)
        WITH jobs,capability_missing,capability_stale,low_confidence,salary_stale,inferred_jobs,
             sum(CASE WHEN coalesce(jt.job_count,0)<2 THEN 1 ELSE 0 END) AS low_frequency_titles
        OPTIONAL MATCH ()-[l:SIMILAR_FOR_LATERAL]->()
        WITH *,sum(CASE WHEN l.generation_source='curated' THEN 1 ELSE 0 END) AS curated_lateral,
             sum(CASE WHEN l.generation_source<>'curated' OR l.generation_source IS NULL THEN 1 ELSE 0 END) AS auto_lateral
        OPTIONAL MATCH (p:JobPromotion)
        RETURN jobs,capability_missing,capability_stale,low_confidence,salary_stale,inferred_jobs,low_frequency_titles,
               curated_lateral,auto_lateral,
               sum(CASE WHEN p.generation_source='curated' THEN 1 ELSE 0 END) AS curated_promotions,
               sum(CASE WHEN p.generation_source<>'curated' OR p.generation_source IS NULL THEN 1 ELSE 0 END) AS auto_promotions
        """, cap_version=str(setting("GRAPH_CAP_VERSION", "job-cap-v2")), salary_version="v1").single()
        if row:
            stats.update({key: int(value or 0) for key, value in dict(row).items()})
        workstyle_row = session.run("""
        MATCH (j:Job)
        OPTIONAL MATCH (j)-[:HAS_TITLE]->(jt:JobTitle)
        WITH j, head(collect(jt)) AS jt
        WITH j, jt,
          CASE WHEN (j.workstyle_evidence_json IS NOT NULL OR jt.workstyle_evidence_json IS NOT NULL) THEN 1 ELSE 0 END AS evidenced,
          CASE WHEN j.workstyle_evidence_json IS NULL AND jt.workstyle_evidence_json IS NOT NULL THEN 1 ELSE 0 END AS inherited,
          reduce(axis_count = 0, present IN [
            coalesce(j.workstyle_interaction, jt.workstyle_interaction) IS NOT NULL AND coalesce(j.workstyle_conf_interaction, jt.workstyle_conf_interaction) IS NOT NULL,
            coalesce(j.workstyle_abstraction, jt.workstyle_abstraction) IS NOT NULL AND coalesce(j.workstyle_conf_abstraction, jt.workstyle_conf_abstraction) IS NOT NULL,
            coalesce(j.workstyle_analytical, jt.workstyle_analytical) IS NOT NULL AND coalesce(j.workstyle_conf_analytical, jt.workstyle_conf_analytical) IS NOT NULL,
            coalesce(j.workstyle_structure, jt.workstyle_structure) IS NOT NULL AND coalesce(j.workstyle_conf_structure, jt.workstyle_conf_structure) IS NOT NULL
          ] | axis_count + CASE WHEN present THEN 1 ELSE 0 END) AS axis_count
        RETURN count(j) AS workstyle_total,
               sum(evidenced) AS workstyle_evidenced,
               sum(CASE WHEN evidenced = 1 AND axis_count >= 2 THEN 1 ELSE 0 END) AS workstyle_ready,
               sum(inherited) AS workstyle_inherited
        """).single()
        if workstyle_row:
            workstyle_stats = {key: int(value or 0) for key, value in dict(workstyle_row).items()}
            total = workstyle_stats.get("workstyle_total", 0)
            ready = workstyle_stats.get("workstyle_ready", 0)
            workstyle_stats["workstyle_missing"] = max(0, total - workstyle_stats.get("workstyle_evidenced", 0))
            workstyle_stats["workstyle_coverage_percent"] = round(ready * 100 / total) if total else 0
            stats.update(workstyle_stats)
    return stats


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


def get_import_runs(limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent persisted graph import runs for operational diagnosis."""
    uri, user, password, database = neo4j_settings()
    if not password:
        raise GraphServiceError("未配置 NEO4J_PASSWORD", 500)
    driver = neo4j_driver(uri, user, password)
    return list_import_runs(driver, database, limit=limit)


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
