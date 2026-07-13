"""Build reviewable graph change sets without mutating Neo4j."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from app.domains.graph.constants import COLUMN_ALIASES, REQUIRED_CN_COLUMNS, build_ai_payload, normalize_text, normalize_title
from app.domains.graph.incremental import deduplicate_jobs, import_keys, job_key_for_row, plan_incremental_rows
from app.domains.graph.repository import fetch_job_import_fingerprints
from app.domains.graph.services import _call_llm_batch_extract, _llm_model
from app.domains.graph.sync_service import LATERAL_SYSTEM, PROMOTION_PATH_SYSTEM, _call_llm_json, _parse_confidence
from app.infrastructure.neo4j import neo4j_driver, neo4j_settings


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
    path = task["input_file_path"]
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
    change_set = {"version": 1, "kind": "job_import", "source_id": task.get("source_id") or "manual", "mode": task.get("mode") or "merge", "input_keys": keys, "jobs": jobs, "job_titles": [{"name": n, "count": counts[n]} for n in sorted(counts)], "promotions": promotions, "lateral": lateral}
    summary = {"input_rows": len(df) + duplicates, "unique_jobs": len(df), "duplicate_rows": duplicates, "new_or_changed_jobs": len(jobs), "unchanged_jobs": len(unchanged), "job_titles": len(titles), "promotions": len(promotions), "lateral_transfers": len(lateral), "snapshot_prune": task.get("mode") == "snapshot", "preview": {"jobs": [{"job_key": x["job_key"], "title": x["row"].get("name"), "company": x["row"].get("company")} for x in jobs[:10]], "promotions": promotions[:10], "lateral": lateral[:10]}}
    return change_set, summary


RESOURCE_COLUMNS = {"resource_id", "job_name", "resource_name", "resource_desc", "resource_url", "resource_type", "difficulty", "source", "skill_tag"}
COMPETITION_COLUMNS = {"competition_id", "job_name", "competition_name", "competition_desc", "official_url", "competition_type", "organizer", "target_audience", "team_mode", "frequency", "difficulty", "cap_tags", "skill_tags", "award_level"}


def _plan_csv(task: dict[str, Any], *, kind: str, required: set[str], id_column: str, emit=lambda *_args, **_kwargs: None):
    df = pd.read_csv(task["input_file_path"], encoding="utf-8-sig", dtype=str).fillna("")
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
    change_set = {"version": 1, "kind": kind, "source_id": task.get("source_id") or "master_csv", "mode": task.get("mode") or "snapshot", "items": records}
    emit("validation", "CSV 校验和关系规划完成", {"items": len(records), "job_title_links": sum(len(x["job_titles"]) for x in records)})
    return change_set, {"items": len(records), "job_title_links": sum(len(x["job_titles"]) for x in records), "snapshot_prune": task.get("mode") == "snapshot", "preview": records[:10]}


def build_change_set(task: dict[str, Any], emit=lambda *_args, **_kwargs: None):
    if task["task_type"] == "job_import": return plan_job_import(task, emit)
    if task["task_type"] == "learning_resource_import": return _plan_csv(task, kind="learning_resource_import", required=RESOURCE_COLUMNS, id_column="resource_id", emit=emit)
    if task["task_type"] == "competition_import": return _plan_csv(task, kind="competition_import", required=COMPETITION_COLUMNS, id_column="competition_id", emit=emit)
    raise TaskPlanningError(f"未知任务类型: {task['task_type']}")
