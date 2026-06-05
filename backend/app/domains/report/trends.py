"""赛道画像：招聘样本统计 + 图谱路径/资源（默认报告，不联网）。"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.domains.report.graph_repository import fetch_track_graph_stats_batch
from app.infrastructure.neo4j import neo4j_settings

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_COUNTS_CSV = _BACKEND_ROOT.parent / "datasets" / "master" / "job_title_record_counts.csv"


def _percentile_rank(value: float, population: List[float]) -> float:
    if not population:
        return 50.0
    below = sum(1 for x in population if x < value)
    equal = sum(1 for x in population if x == value)
    return round((below + 0.5 * equal) / len(population) * 100.0, 1)


@lru_cache(maxsize=1)
def _load_hiring_table(csv_path: str | None = None) -> List[Dict[str, Any]]:
    path = Path(csv_path) if csv_path else _DEFAULT_COUNTS_CSV
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            title = str(row.get("job_title") or "").strip()
            if not title:
                continue
            rows.append(
                {
                    "job_title": title,
                    "rank": int(float(row.get("rank") or 0)),
                    "record_count": int(float(row.get("record_count") or 0)),
                    "pct_of_total": float(row.get("pct_of_total") or 0),
                    "company_count": int(float(row.get("company_count") or 0)),
                    "job_code_count": int(float(row.get("job_code_count") or 0)),
                }
            )
    return rows


def build_track_profile(
    *,
    job_title_name: str,
    job_card_title: str | None = None,
) -> Dict[str, Any]:
    """
    为单个 JobTitle 生成赛道画像。
    job_title_name：图谱 JobTitle.name；缺失时回退 job_card 的 title。
    """
    title = str(job_title_name or job_card_title or "").strip() or "未知岗位"
    hiring_rows = _load_hiring_table()
    hiring_map = {r["job_title"]: r for r in hiring_rows}

    graph_batch = fetch_track_graph_stats_batch()
    graph = graph_batch.get(title) or {
        "promotion_route_count": 0,
        "lateral_similar_count": 0,
        "learning_resource_count": 0,
        "competition_count": 0,
    }

    hiring = hiring_map.get(title)
    record_counts = [float(r["record_count"]) for r in hiring_rows]
    path_scores = []
    resource_scores = []
    for r in hiring_rows:
        t = r["job_title"]
        g = graph_batch.get(t) or {}
        path_scores.append(float(g.get("promotion_route_count", 0) * 2 + g.get("lateral_similar_count", 0)))
        resource_scores.append(
            float(g.get("learning_resource_count", 0) + g.get("competition_count", 0))
        )

    my_path = float(graph.get("promotion_route_count", 0) * 2 + graph.get("lateral_similar_count", 0))
    my_resource = float(graph.get("learning_resource_count", 0) + graph.get("competition_count", 0))

    if hiring:
        vis = _percentile_rank(float(hiring["record_count"]), record_counts)
        hiring_block = {
            "record_count": hiring["record_count"],
            "rank": hiring["rank"],
            "pct_of_total": hiring["pct_of_total"],
            "company_count": hiring["company_count"],
            "job_code_count": hiring["job_code_count"],
            "percentile": vis,
        }
    else:
        vis = 35.0
        hiring_block = {
            "record_count": 0,
            "rank": None,
            "pct_of_total": 0.0,
            "company_count": 0,
            "job_code_count": 0,
            "percentile": vis,
            "note": "系统里暂未收录到该岗位名的招聘统计",
        }

    path_pct = _percentile_rank(my_path, path_scores) if path_scores else 50.0
    res_pct = _percentile_rank(my_resource, resource_scores) if resource_scores else 50.0

    rc = int(hiring_block.get("record_count", 0) or 0)
    rank = hiring_block.get("rank")
    if rank and int(rank) <= 3:
        heat_txt = "招聘热度在本库排名靠前"
    elif rank:
        heat_txt = f"招聘热度在本库约第 {int(rank)} 名"
    elif rc >= 50:
        heat_txt = f"系统收录 {rc} 条相关招聘信息，较活跃"
    else:
        heat_txt = "招聘热度一般"
    summary = (
        f"{heat_txt}；可沿约 {int(graph.get('promotion_route_count', 0))} 条晋升路线发展，"
        f"另有 {int(graph.get('lateral_similar_count', 0))} 个相近方向可参考；"
        f"关联 {int(graph.get('learning_resource_count', 0))} 条学习资源、"
        f"{int(graph.get('competition_count', 0))} 项竞赛，便于制定成长计划。"
    )

    try:
        from app.domains.report.graph_repository import _neo4j_settings_safe

        neo4j_ok = bool(_neo4j_settings_safe()[2])
    except Exception:  # noqa: BLE001
        neo4j_ok = False
    return {
        "job_title": title,
        "hiring_visibility_0_100": vis,
        "path_breadth_0_100": path_pct,
        "resource_density_0_100": res_pct,
        "hiring": hiring_block,
        "paths": {
            "promotion_route_count": int(graph.get("promotion_route_count", 0)),
            "lateral_similar_count": int(graph.get("lateral_similar_count", 0)),
        },
        "resources": {
            "learning_resource_count": int(graph.get("learning_resource_count", 0)),
            "competition_count": int(graph.get("competition_count", 0)),
        },
        "summary_text": summary[:200],
        "evidence": "datasets/master/job_title_record_counts.csv + Neo4j JobTitle 图谱统计",
        "source": "internal",
        "data_as_of": "2026-02-26",
        "graph_available": neo4j_ok,
    }


def attach_track_profiles_to_insights(target_insights: List[Dict[str, Any]]) -> None:
    """为 target_insights 写入 track_profile（就地修改）。"""
    from app.domains.report.graph_repository import resolve_job_title_names

    job_ids = [str(t.get("id") or "") for t in target_insights]
    title_by_job = resolve_job_title_names(job_ids)
    for t in target_insights:
        jid = str(t.get("id") or "")
        jt_name = title_by_job.get(jid) or str(t.get("title") or "").strip()
        t["track_profile"] = build_track_profile(
            job_title_name=jt_name,
            job_card_title=str(t.get("title") or ""),
        )
