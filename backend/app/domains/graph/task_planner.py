"""Build reviewable graph change sets without mutating Neo4j."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from app.domains.graph.constants import COLUMN_ALIASES, REQUIRED_CN_COLUMNS, build_ai_payload, normalize_text, normalize_title
from app.domains.graph.incremental import deduplicate_jobs, import_keys, job_key_for_row, plan_incremental_rows
from app.domains.graph.repository import fetch_job_import_fingerprints
from app.domains.graph.capability_service import CAP_VERSION, CONF_FIELDS, REQ_FIELDS, capability_fingerprint, evaluate_jobs, normalize_imported_result
from app.domains.graph.task_registry import TASK_HANDLERS
from app.domains.graph.services import _call_llm_batch_extract, _llm_model
from app.domains.graph.sync_service import LATERAL_SYSTEM, PROMOTION_PATH_SYSTEM, _call_llm_json, _parse_confidence
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings
from app.infrastructure.salary import SALARY_PARSE_VERSION, neo4j_salary_properties
from app.domains.jobs.workstyle import WORKSTYLE_AXES, WORKSTYLE_SCORING_VERSION
from app.domains.jobs.workstyle_extraction import WORKSTYLE_TEXT_VERSION, extract_workstyle_profile, workstyle_input_fingerprint


class TaskPlanningError(ValueError):
    pass


def _clean(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): _clean(v) for k, v in row.items()} for row in df.to_dict("records")]


def _driver():
    uri, user, password, database = neo4j_settings()
    if not password:
        raise TaskPlanningError("未配置 NEO4J_PASSWORD")
    return neo4j_driver(uri, user, password), database


def _file_path(task: dict[str, Any], role: str = "file") -> str:
    for item in task.get("files", []):
        if item.get("role") == role and item.get("private_path"):
            return str(item["private_path"])
    if role == "file" and task.get("input_file_path"):
        return str(task["input_file_path"])
    raise TaskPlanningError(f"任务缺少输入文件: {role}")


def _cap_payload(job: dict[str, Any]) -> dict[str, Any]:
    row, ai = job.get("row", {}), job.get("ai", {})
    return {"job_key": job.get("job_key"), "title": row.get("name") or row.get("title"),
            "company": row.get("company"), "industry": row.get("industry"),
            "demand": row.get("demand"), "company_detail": row.get("company_detail"),
            "hard_skills": ai.get("hard_skills", []), "soft_skills": ai.get("soft_skills", {}),
            "certificates": ai.get("certificates", []), "experience": ai.get("experience_req", "未知")}


def _plan_promotions(titles: list[str]) -> list[dict[str, Any]]:
    valid = set(titles); output = []
    for start in range(0, len(titles), 30):
        result = _call_llm_json(PROMOTION_PATH_SYSTEM, json.dumps({"job_titles": titles[start:start + 30]}, ensure_ascii=False), label=f"晋升路径 batch {start // 30 + 1}")
        for item in result.get("paths", []):
            if not isinstance(item, dict): continue
            frm, to = str(item.get("from_title") or "").strip(), str(item.get("to_title") or "").strip()
            confidence = _parse_confidence(item.get("confidence"))
            if frm and to and frm != to and frm in valid and to in valid and confidence >= 0.5:
                row = dict(item); row.update(from_title=frm, to_title=to, confidence=confidence); output.append(row)
    return output


def _plan_lateral(titles: list[str]) -> list[dict[str, Any]]:
    titles = titles[:50]; valid = set(titles); output, seen = [], set()
    for start in range(0, len(titles), 15):
        batch = titles[start:start + 15]
        result = _call_llm_json(LATERAL_SYSTEM, json.dumps({"job_titles": batch, "task": "评估这些岗位两两之间的横向转岗可行性"}, ensure_ascii=False), label=f"换岗关系 batch {start // 15 + 1}")
        for item in result.get("pairs", []):
            if not isinstance(item, dict): continue
            frm, to = str(item.get("from") or "").strip(), str(item.get("to") or "").strip()
            score = _parse_confidence(item.get("score")); pair = (frm, to)
            if frm and to and frm != to and frm in valid and to in valid and score > 0.4 and pair not in seen:
                seen.add(pair); row = dict(item); row.update({"from": frm, "to": to, "score": score, "cap_similarity": _parse_confidence(item.get("cap_similarity"))}); output.append(row)
    return output


def plan_job_import(task: dict[str, Any], emit=lambda *_args, **_kwargs: None) -> tuple[dict[str, Any], dict[str, Any]]:
    path = _file_path(task)
    df = pd.read_excel(path)
    missing = [column for column in REQUIRED_CN_COLUMNS if column not in df.columns]
    if missing: raise TaskPlanningError(f"Excel 缺少必要字段: {missing}")
    df = df.rename(columns=COLUMN_ALIASES)
    df, duplicates = deduplicate_jobs(df)
    emit("parsed", "岗位文件解析完成", {"unique_jobs": len(df), "duplicate_rows": duplicates})
    driver, database = _driver()
    keys = import_keys(df)
    existing = fetch_job_import_fingerprints(driver, database, keys)
    extraction_version = f"{_llm_model()}:v1"
    changed, unchanged, fingerprints = plan_incremental_rows(df, existing, extraction_version=extraction_version)
    emit("incremental", "岗位增量规划完成", {"changed": len(changed), "unchanged": len(unchanged)})
    jobs = []
    batch_size = max(1, min(int(task["options"].get("batch_size", 128)), 1000))
    for start in range(0, len(changed), batch_size):
        batch = changed.iloc[start:start + batch_size].copy()
        emit("llm", f"正在提取岗位批次 {start // batch_size + 1}", {"rows": len(batch)})
        ai = _call_llm_batch_extract(build_ai_payload(batch))
        by_index = {x.get("idx"): x for x in ai if isinstance(x, dict) and isinstance(x.get("idx"), int)}
        for index, row in batch.reset_index(drop=True).iterrows():
            raw = {str(k): _clean(v) for k, v in row.to_dict().items()}
            key = job_key_for_row(row)
            jobs.append({"job_key": key, "row": raw, "ai": by_index.get(index, {}), "fingerprint": fingerprints[key]})

    capability_batch_size = max(1, min(int(task["options"].get("capability_batch_size", 8)), 50))
    for start in range(0, len(jobs), capability_batch_size):
        group = jobs[start:start + capability_batch_size]
        emit("capability", f"正在评估岗位八维能力批次 {start // capability_batch_size + 1}", {"start": start + 1, "rows": len(group), "total": len(jobs)})
        results = evaluate_jobs([_cap_payload(job) for job in group])
        for job, result in zip(group, results, strict=True): job["capability"] = result

    with driver.session(database=database) as session:
        rows = session.run("MATCH (j:Job) RETURN j.job_key AS job_key,j.title AS title,j.import_source_id AS source_id")
        projected = {str(x["job_key"]): {"title": normalize_title(x["title"]), "source_id": str(x["source_id"] or "")} for x in rows}
    if task.get("mode") == "snapshot":
        input_set, source = set(keys), str(task.get("source_id") or "")
        projected = {key: value for key, value in projected.items() if value["source_id"] != source or key in input_set}
    for job in jobs:
        projected[job["job_key"]] = {"title": normalize_title(job["row"].get("name")), "source_id": str(task.get("source_id") or "")}
    counts: dict[str, int] = {}
    for value in projected.values():
        if value["title"]: counts[value["title"]] = counts.get(value["title"], 0) + 1
    titles = [name for name, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0])) if name]
    emit("job_titles", "岗位名称投影完成", {"job_titles": len(titles)})
    promotions = _plan_promotions(titles) if task["options"].get("generate_promotions", True) and len(titles) > 1 else []
    if task["options"].get("generate_promotions", True): emit("promotions", "晋升路径规划完成", {"promotions": len(promotions)})
    lateral = _plan_lateral(titles) if task["options"].get("generate_lateral", True) and len(titles) > 1 else []
    if task["options"].get("generate_lateral", True): emit("lateral", "换岗关系规划完成", {"lateral_transfers": len(lateral)})
    change_set = {"version": 2, "kind": "job_import", "source_id": task.get("source_id") or "manual", "mode": task.get("mode") or "merge", "input_keys": keys, "jobs": jobs, "job_titles": [{"name": n, "count": counts[n]} for n in sorted(counts)], "promotions": promotions, "lateral": lateral, "replace_auto_promotions": bool(task["options"].get("generate_promotions", True)), "replace_auto_lateral": bool(task["options"].get("generate_lateral", True))}
    low_confidence = sum(1 for x in jobs if min(float(x["capability"][f]) for f in CONF_FIELDS) < 0.6)
    summary = {"input_rows": len(df) + duplicates, "unique_jobs": len(df), "duplicate_rows": duplicates, "new_or_changed_jobs": len(jobs), "evaluated_jobs": len(jobs), "low_confidence_jobs": low_confidence, "unchanged_jobs": len(unchanged), "job_titles": len(titles), "promotions": len(promotions), "lateral_transfers": len(lateral), "snapshot_prune": task.get("mode") == "snapshot", "preview": {"jobs": [{"job_key": x["job_key"], "title": x["row"].get("name"), "company": x["row"].get("company"), "capability": x["capability"]} for x in jobs[:10]], "promotions": promotions[:10], "lateral": lateral[:10]}}
    return change_set, summary


RESOURCE_COLUMNS = {"resource_id", "job_name", "resource_name", "resource_desc", "resource_url", "resource_type", "difficulty", "source", "skill_tag"}
COMPETITION_COLUMNS = {"competition_id", "job_name", "competition_name", "competition_desc", "official_url", "competition_type", "organizer", "target_audience", "team_mode", "frequency", "difficulty", "cap_tags", "skill_tags", "award_level"}
PROMOTION_COLUMNS = {"promotion_id", "job_title", "title", "promotion", "stage1", "stage2", "stage3", "stage3_job_title", "notes"}
LATERAL_COLUMNS = {"from_job_title", "to_job_title", "score", "rank", "track_from", "track_to", "cap_similarity", "same_track", "promotion_linked", "rationale"}
RECOMMENDATION_RESOURCE_COLUMNS = {"promotion_id", "resource_id", "stage", "stage_role", "rank", "score", "rationale"}
RECOMMENDATION_COMPETITION_COLUMNS = {"promotion_id", "competition_id", "stage", "stage_role", "rank", "score", "match_via", "rationale"}
WORKSTYLE_COLUMNS = {
    "target_type", "target_id", "workstyle_source", "workstyle_scoring_version",
    "workstyle_evidence_json",
    *{key for _code, value_key, confidence_key, _low, _high in WORKSTYLE_AXES for key in (value_key, confidence_key)},
}


def _plan_csv(task: dict[str, Any], *, kind: str, required: set[str], id_column: str, emit=lambda *_args, **_kwargs: None):
    df = pd.read_csv(_file_path(task), encoding="utf-8-sig", dtype=str).fillna("")
    missing = sorted(required - set(df.columns))
    if missing: raise TaskPlanningError(f"CSV 缺少必要字段: {missing}")
    if (df[id_column].str.strip() == "").any(): raise TaskPlanningError(f"{id_column} 不能为空")
    duplicates = int(df[id_column].duplicated().sum())
    if duplicates: raise TaskPlanningError(f"{id_column} 存在 {duplicates} 个重复值")
    records = _records(df[list(sorted(required))])
    driver, database = _driver()
    with driver.session(database=database) as session:
        known_titles = {str(row["name"]) for row in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name")}
    if not known_titles: raise TaskPlanningError("图谱中没有 JobTitle，请先完成岗位导入")
    allowed_difficulty = {"入门", "进阶", "高阶", ""}
    for row in records:
        row["job_titles"] = [x.strip() for x in str(row.pop("job_name", "")).split("|") if x.strip()]
        if not row["job_titles"]: raise TaskPlanningError(f"{row[id_column]} 至少需要一个 job_name")
        if "ALL" in row["job_titles"]: row["job_titles"] = sorted(known_titles)
        unknown = sorted(set(row["job_titles"]) - known_titles)
        if unknown: raise TaskPlanningError(f"{row[id_column]} 引用了不存在的 JobTitle: {unknown[:5]}")
        if row.get("difficulty", "") not in allowed_difficulty: raise TaskPlanningError(f"{row[id_column]} difficulty 非法")
        url = str(row.get("resource_url") or row.get("official_url") or "").strip()
        if url and urlparse(url).scheme not in {"http", "https"}: raise TaskPlanningError(f"{row[id_column]} URL 必须使用 http/https")
    change_set = {"version": 2, "kind": kind, "source_id": task.get("source_id") or "master_csv", "mode": task.get("mode") or "snapshot", "items": records}
    emit("validation", "CSV 校验和关系规划完成", {"items": len(records), "job_title_links": sum(len(x["job_titles"]) for x in records)})
    return change_set, {"items": len(records), "job_title_links": sum(len(x["job_titles"]) for x in records), "snapshot_prune": task.get("mode") == "snapshot"}


def _read_csv(task: dict[str, Any], required: set[str], role: str = "file") -> list[dict[str, Any]]:
    df = pd.read_csv(_file_path(task, role), encoding="utf-8-sig", dtype=str).fillna("")
    missing = sorted(required - set(df.columns))
    if missing:
        raise TaskPlanningError(f"{role} CSV 缺少必要字段: {missing}")
    return _records(df[list(sorted(required))])


def plan_capability_evaluation(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    scope = task.get("options", {}).get("scope", "missing")
    source_id = task.get("options", {}).get("source_id")
    driver, database = _driver()
    fields = ",".join([f"j.{field} AS {field}" for field in (*REQ_FIELDS, *CONF_FIELDS)])
    with driver.session(database=database) as session:
        rows = [dict(row) for row in session.run(
            f"MATCH (j:Job) WHERE coalesce(j.source,'') <> 'inferred' "
            f"AND ($source IS NULL OR j.import_source_id=$source) RETURN j.job_key AS job_key,j.title AS title,j.company AS company,j.industry AS industry,j.demand AS demand,j.company_detail AS company_detail,j.experience_text AS experience,[(j)-[:REQUIRES]->(s:Skill) | s.name] AS hard_skills,[(j)-[:REQUIRES]->(c:Certificate) | c.name] AS certificates,j.cap_version AS cap_version,j.cap_input_fingerprint AS cap_input_fingerprint,{fields}",
            source=source_id,
        )]
    selected = []
    for row in rows:
        missing = any(row.get(field) is None for field in (*REQ_FIELDS, *CONF_FIELDS)) or not row.get("cap_version")
        payload = {key: row.get(key) for key in ("job_key", "title", "company", "industry", "demand", "company_detail", "experience", "hard_skills", "certificates")}
        stale = row.get("cap_version") != CAP_VERSION or row.get("cap_input_fingerprint") != capability_fingerprint(payload)
        if scope == "all" or (scope == "missing" and missing) or (scope == "stale" and stale):
            selected.append(row)
    changes = []; batch_size = max(1, min(int(task.get("options", {}).get("capability_batch_size", 8)), 50))
    for start in range(0, len(selected), batch_size):
        group = selected[start:start + batch_size]
        emit("capability", f"正在评估存量岗位批次 {start // batch_size + 1}", {"start": start + 1, "rows": len(group), "total": len(selected)})
        payloads = [{key: row.get(key) for key in ("job_key", "title", "company", "industry", "demand", "company_detail", "experience", "hard_skills", "certificates")} for row in group]
        results = evaluate_jobs(payloads)
        for row, result in zip(group, results, strict=True): changes.append({"job_key": row["job_key"], "old": {field: row.get(field) for field in (*REQ_FIELDS, *CONF_FIELDS, "cap_version")}, "capability": result})
    low = sum(1 for x in changes if min(float(x["capability"][f]) for f in CONF_FIELDS) < 0.6)
    return ({"version": 2, "kind": "job_capability_evaluation", "jobs": changes},
            {"scope": scope, "source_id": source_id, "candidate_jobs": len(rows), "evaluated_jobs": len(changes), "low_confidence_jobs": low, "preview": changes[:10]})


def plan_capability_result_import(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    records: list[dict[str, Any]] = []
    with Path(_file_path(task)).open("r", encoding="utf-8-sig") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try: raw = json.loads(line)
            except json.JSONDecodeError as exc: raise TaskPlanningError(f"JSONL 第 {line_no} 行不是合法 JSON") from exc
            key = str(raw.get("job_key") or raw.get("job_id") or "").strip()
            if not key: raise TaskPlanningError(f"JSONL 第 {line_no} 行缺少 job_key/job_id")
            try: capability = normalize_imported_result(raw.get("result") if isinstance(raw.get("result"), dict) else raw)
            except ValueError as exc: raise TaskPlanningError(f"JSONL 第 {line_no} 行: {exc}") from exc
            records.append({"job_key": key, "capability": capability})
    keys = [x["job_key"] for x in records]
    if len(keys) != len(set(keys)): raise TaskPlanningError("JSONL 存在重复岗位标识")
    driver, database = _driver()
    with driver.session(database=database) as session:
        matches = [dict(row) for row in session.run("UNWIND $keys AS input MATCH (j:Job) WHERE coalesce(j.job_key,j.job_code,j.name,j.title,elementId(j))=input RETURN input,j.job_key AS job_key", keys=keys)]
    mapped: dict[str, list[str]] = {}
    for row in matches: mapped.setdefault(str(row["input"]), []).append(str(row["job_key"]))
    unknown = sorted(set(keys) - set(mapped))
    if unknown: raise TaskPlanningError(f"JSONL 引用了不存在的岗位: {unknown[:10]}")
    ambiguous = sorted(key for key, values in mapped.items() if len(set(values)) != 1)
    if ambiguous: raise TaskPlanningError(f"JSONL 岗位标识不唯一: {ambiguous[:10]}")
    for record in records: record["job_key"] = mapped[record["job_key"]][0]
    emit("validation", "历史能力结果校验完成", {"jobs": len(records)})
    return {"version": 2, "kind": "job_capability_result_import", "jobs": records}, {"jobs": len(records), "preview": records[:10]}


def plan_workstyle_import(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    rows = _read_csv(task, WORKSTYLE_COLUMNS)
    driver, database = _driver()
    with driver.session(database=database) as session:
        job_keys = {str(row["key"]) for row in session.run("MATCH (j:Job) RETURN j.job_key AS key") if row.get("key")}
        title_names = {str(row["name"]) for row in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name") if row.get("name")}
    items: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for line_no, row in enumerate(rows, 2):
        target_type = str(row.get("target_type") or "").strip().lower()
        target_id = str(row.get("target_id") or "").strip()
        identity = (target_type, target_id)
        if target_type not in {"job", "job_title"} or not target_id:
            raise TaskPlanningError(f"CSV 第 {line_no} 行 target_type/target_id 无效")
        if identity in identities:
            raise TaskPlanningError(f"CSV 存在重复目标: {target_type}:{target_id}")
        identities.add(identity)
        known = job_keys if target_type == "job" else title_names
        if target_id not in known:
            raise TaskPlanningError(f"工作环境画像引用不存在的目标: {target_type}:{target_id}")
        source = str(row.get("workstyle_source") or "").strip()
        version = str(row.get("workstyle_scoring_version") or WORKSTYLE_SCORING_VERSION).strip()
        if not source or not version:
            raise TaskPlanningError(f"CSV 第 {line_no} 行必须提供来源和评分版本")
        try:
            evidence = json.loads(str(row.get("workstyle_evidence_json") or "{}"))
        except json.JSONDecodeError as exc:
            raise TaskPlanningError(f"CSV 第 {line_no} 行 workstyle_evidence_json 非法") from exc
        if not isinstance(evidence, dict):
            raise TaskPlanningError(f"CSV 第 {line_no} 行证据必须是 JSON 对象")
        props: dict[str, Any] = {
            "workstyle_source": source[:120],
            "workstyle_scoring_version": version[:64],
            "workstyle_evidence_json": json.dumps(evidence, ensure_ascii=False),
        }
        supplied = 0
        for code, value_key, confidence_key, _low, _high in WORKSTYLE_AXES:
            raw_value, raw_confidence = row.get(value_key), row.get(confidence_key)
            if not str(raw_value or "").strip() and not str(raw_confidence or "").strip():
                continue
            try:
                value, confidence = float(raw_value), float(raw_confidence)
            except (TypeError, ValueError) as exc:
                raise TaskPlanningError(f"CSV 第 {line_no} 行 {code} 数值格式错误") from exc
            if not 0 <= value <= 100 or not 0 <= confidence <= 1:
                raise TaskPlanningError(f"CSV 第 {line_no} 行 {code} 超出 0-100 / 0-1 范围")
            axis_evidence = evidence.get(code) or evidence.get(value_key)
            if not axis_evidence:
                raise TaskPlanningError(f"CSV 第 {line_no} 行 {code} 缺少可审计证据")
            props[value_key], props[confidence_key] = value, confidence
            supplied += 1
        if not supplied:
            raise TaskPlanningError(f"CSV 第 {line_no} 行至少需要一个工作环境轴")
        items.append({"target_type": target_type, "target_id": target_id, "properties": props})
    emit("validation", "岗位工作环境证据校验完成", {"items": len(items)})
    return ({"version": 2, "kind": "job_workstyle_import", "source_id": task.get("source_id"), "items": items},
            {"items": len(items), "jobs": sum(1 for x in items if x["target_type"] == "job"), "job_titles": sum(1 for x in items if x["target_type"] == "job_title"), "preview": items[:10]})


def plan_workstyle_evaluation(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    scope = task.get("options", {}).get("scope", "missing")
    source_id = task.get("options", {}).get("source_id")
    driver, database = _driver()
    with driver.session(database=database) as session:
        rows = [dict(row) for row in session.run("""
        MATCH (j:Job)
        WHERE coalesce(j.source,'') <> 'inferred' AND ($source IS NULL OR j.import_source_id=$source)
        RETURN j.job_key AS job_key,j.title AS title,j.demand AS demand,j.company_detail AS company_detail,
               j.experience_text AS experience,j.workstyle_scoring_version AS workstyle_scoring_version,
               j.workstyle_input_fingerprint AS workstyle_input_fingerprint,
               j.workstyle_interaction AS workstyle_interaction,j.workstyle_abstraction AS workstyle_abstraction,
               j.workstyle_analytical AS workstyle_analytical,j.workstyle_structure AS workstyle_structure
        """, source=source_id)]
    items = []
    for row in rows:
        payload = {key: row.get(key) for key in ("demand", "company_detail", "experience")}
        axis_count = sum(row.get(key) is not None for key in ("workstyle_interaction", "workstyle_abstraction", "workstyle_analytical", "workstyle_structure"))
        missing = axis_count < 2 or not row.get("workstyle_scoring_version")
        stale = row.get("workstyle_scoring_version") != WORKSTYLE_TEXT_VERSION or row.get("workstyle_input_fingerprint") != workstyle_input_fingerprint(payload)
        if scope == "all" or (scope == "missing" and missing) or (scope == "stale" and stale):
            properties = extract_workstyle_profile(payload)
            items.append({"target_type": "job", "target_id": row["job_key"], "properties": properties, "title": row.get("title")})
    ready = sum(1 for item in items if sum(key.startswith("workstyle_") and not key.startswith("workstyle_conf_") and key in {axis[1] for axis in WORKSTYLE_AXES} for key in item["properties"]) >= 2)
    emit("workstyle", "岗位工作环境证据提取完成，等待人工复核", {"items": len(items), "ready": ready})
    return ({"version": 2, "kind": "job_workstyle_evaluation", "items": items},
            {"scope": scope, "source_id": source_id, "candidate_jobs": len(rows), "evaluated_jobs": len(items), "workstyle_ready": ready, "preview": items[:10]})


def plan_promotions_import(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    rows = _read_csv(task, PROMOTION_COLUMNS)
    ids = [row["promotion_id"].strip() for row in rows]
    if not all(ids) or len(ids) != len(set(ids)): raise TaskPlanningError("promotion_id 不能为空或重复")
    excluded_path = Path(__file__).resolve().parents[4] / "datasets/promotion/job_title_promotions_excluded.csv"
    excluded = set()
    if excluded_path.is_file():
        excluded = {str(row.get("job_title") or "").strip() for row in _records(pd.read_csv(excluded_path, encoding="utf-8-sig", dtype=str).fillna(""))}
    bad_excluded = sorted({row["job_title"].strip() for row in rows} & excluded)
    if bad_excluded: raise TaskPlanningError(f"晋升路线包含策展排除岗位: {bad_excluded[:10]}")
    driver, database = _driver()
    with driver.session(database=database) as session:
        titles = {str(row["name"]) for row in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name")}
    unknown = sorted({row["job_title"].strip() for row in rows} - titles)
    if unknown: raise TaskPlanningError(f"晋升路线引用了不存在的 JobTitle: {unknown[:10]}")
    for row in rows:
        if not any(row.get(f"stage{i}", "").strip() for i in range(1, 4)): raise TaskPlanningError(f"{row['promotion_id']} 至少需要一个阶段")
    emit("validation", "晋升路线校验完成", {"items": len(rows)})
    return {"version": 2, "kind": "job_promotion_import", "source_id": task.get("source_id"), "mode": task.get("mode"), "items": rows}, {"items": len(rows), "job_titles": len({x['job_title'] for x in rows}), "preview": rows[:10]}


def plan_lateral_import(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    rows = _read_csv(task, LATERAL_COLUMNS)
    pairs = [(x["from_job_title"].strip(), x["to_job_title"].strip()) for x in rows]
    if any(not a or not b or a == b for a, b in pairs) or len(pairs) != len(set(pairs)): raise TaskPlanningError("换岗关系存在空值、自环或重复有向关系")
    driver, database = _driver()
    with driver.session(database=database) as session:
        titles = {str(row["name"]) for row in session.run("MATCH (jt:JobTitle) RETURN jt.name AS name")}
    unknown = sorted({x for pair in pairs for x in pair} - titles)
    if unknown: raise TaskPlanningError(f"换岗关系引用了不存在的 JobTitle: {unknown[:10]}")
    for row in rows:
        try:
            row["score"] = float(row["score"]); row["cap_similarity"] = float(row["cap_similarity"]); row["rank"] = int(float(row["rank"] or 0))
            row["same_track"] = str(row["same_track"]).lower() in {"1", "true", "yes"}; row["promotion_linked"] = str(row["promotion_linked"]).lower() in {"1", "true", "yes"}
        except ValueError as exc: raise TaskPlanningError("换岗关系数值字段格式错误") from exc
    emit("validation", "横向换岗校验完成", {"relationships": len(rows)})
    return {"version": 2, "kind": "job_lateral_import", "source_id": task.get("source_id"), "mode": task.get("mode"), "items": rows}, {"relationships": len(rows), "preview": rows[:10]}


def plan_recommendation_import(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    resources = _read_csv(task, RECOMMENDATION_RESOURCE_COLUMNS, "learning_file")
    competitions = _read_csv(task, RECOMMENDATION_COMPETITION_COLUMNS, "competition_file")
    driver, database = _driver()
    with driver.session(database=database) as session:
        promos = {str(x["id"]) for x in session.run("MATCH (p:JobPromotion) RETURN p.promotion_id AS id")}
        resource_ids = {str(x["id"]) for x in session.run("MATCH (r:LearningResource) RETURN r.resource_id AS id")}
        competition_ids = {str(x["id"]) for x in session.run("MATCH (c:Competition) RETURN c.competition_id AS id")}
    missing = ({x["promotion_id"] for x in resources + competitions} - promos) | ({x["resource_id"] for x in resources} - resource_ids) | ({x["competition_id"] for x in competitions} - competition_ids)
    if missing: raise TaskPlanningError(f"推荐文件引用了不存在的节点: {sorted(missing)[:10]}")
    resource_keys = [(x["promotion_id"], x["resource_id"]) for x in resources]
    competition_keys = [(x["promotion_id"], x["competition_id"]) for x in competitions]
    if len(resource_keys) != len(set(resource_keys)) or len(competition_keys) != len(set(competition_keys)):
        raise TaskPlanningError("推荐文件存在重复的晋升路线与资源/竞赛组合")
    try:
        for row in resources + competitions:
            row["stage"] = int(float(row["stage"])); row["rank"] = int(float(row["rank"])); row["score"] = float(row["score"])
            if row["stage"] < 1 or row["rank"] < 1 or not 0 <= row["score"] <= 1: raise ValueError
    except ValueError as exc: raise TaskPlanningError("推荐文件的 stage、rank 或 score 非法") from exc
    emit("validation", "晋升推荐双文件校验完成", {"resources": len(resources), "competitions": len(competitions)})
    return {"version": 2, "kind": "promotion_recommendation_import", "source_id": task.get("source_id"), "mode": task.get("mode"), "resource_recommendations": resources, "competition_recommendations": competitions}, {"resource_recommendations": len(resources), "competition_recommendations": len(competitions), "preview": {"resources": resources[:5], "competitions": competitions[:5]}}


def plan_salary_normalization(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    force = bool(task.get("options", {}).get("force"))
    driver, database = _driver()
    with driver.session(database=database) as session:
        rows = [dict(x) for x in session.run("MATCH (j:Job) WHERE $force OR j.salary_parse_version IS NULL OR j.salary_parse_version <> $version RETURN j.job_key AS job_key,j.salary AS salary,j.salary_norm AS old_salary_norm,j.salary_parse_version AS old_version", force=force, version=SALARY_PARSE_VERSION)]
    changes = []
    for row in rows:
        props = neo4j_salary_properties(row.get("salary") or "")
        changes.append({"job_key": row["job_key"], "old": {"salary_norm": row.get("old_salary_norm"), "salary_parse_version": row.get("old_version")}, "new": props, "parsed": props.get("salary_norm") not in {"未知"}})
    emit("salary", "薪资规范化变更已生成", {"jobs": len(changes)})
    return {"version": 2, "kind": "salary_normalization", "jobs": changes}, {"jobs": len(changes), "parsed": sum(1 for x in changes if x["parsed"]), "unparsed": sum(1 for x in changes if not x["parsed"]), "preview": changes[:10]}


def plan_inferred_cleanup(_task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    driver, database = _driver()
    with driver.session(database=database) as session:
        jobs = [dict(x) for x in session.run("MATCH (j:Job) WHERE j.source='inferred' OPTIONAL MATCH (j)-[r]-() RETURN j.job_key AS job_key,j.title AS title,count(r) AS relationship_count")]
        titles = [dict(x) for x in session.run("MATCH (jt:JobTitle) OPTIONAL MATCH (j:Job)-[:HAS_TITLE]->(jt) WITH jt,count(j) AS actual WHERE actual < 2 RETURN jt.name AS name,actual AS job_count")]
    emit("cleanup", "推断岗位清理清单已固化", {"jobs": len(jobs), "job_titles": len(titles)})
    return {"version": 2, "kind": "inferred_job_cleanup", "jobs": jobs, "job_titles": titles}, {"delete_jobs": len(jobs), "delete_job_titles": len(titles), "affected_relationships": sum(int(x["relationship_count"]) for x in jobs), "preview": {"jobs": jobs[:10], "job_titles": titles[:10]}}


PLANNERS = {
    "job_import": plan_job_import,
    "job_capability_evaluation": plan_capability_evaluation,
    "job_capability_result_import": plan_capability_result_import,
    "job_workstyle_import": plan_workstyle_import,
    "job_workstyle_evaluation": plan_workstyle_evaluation,
    "learning_resource_import": lambda task, emit: _plan_csv(task, kind="learning_resource_import", required=RESOURCE_COLUMNS, id_column="resource_id", emit=emit),
    "competition_import": lambda task, emit: _plan_csv(task, kind="competition_import", required=COMPETITION_COLUMNS, id_column="competition_id", emit=emit),
    "job_promotion_import": plan_promotions_import,
    "job_lateral_import": plan_lateral_import,
    "promotion_recommendation_import": plan_recommendation_import,
    "salary_normalization": plan_salary_normalization,
    "inferred_job_cleanup": plan_inferred_cleanup,
}


def build_change_set(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    try:
        planner_key = TASK_HANDLERS[task["task_type"]][0]
        planner = PLANNERS[str(planner_key)]
    except KeyError as exc: raise TaskPlanningError(f"未知任务类型: {task['task_type']}") from exc
    return planner(task, emit)
