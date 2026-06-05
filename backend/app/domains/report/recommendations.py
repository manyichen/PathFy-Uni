"""图谱推荐：检索、打分、LLM 选题、写入报告结构。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from flask import current_app

from app.domains.report.constants import DIM_LABELS
from app.domains.report.graph_repository import (
    fetch_competitions_for_title,
    fetch_learning_resources_for_title,
    resolve_job_title_names,
)
from app.domains.report.growth import _top_gap_dimensions
from app.domains.report.llm import _call_openai_compatible
from app.domains.report.utils import truthy
from app.infrastructure.llm import strip_json_fence
from app.infrastructure.privacy import redact_payload

# 维度 -> 资源 skill_tag / 名称 匹配关键词
_DIM_HINTS: Dict[str, List[str]] = {
    "cap_req_theory": ["理论", "算法", "数学", "基础", "数据结构", "Java", "C++", "编程"],
    "cap_req_cross": ["跨", "综合", "英语", "翻译"],
    "cap_req_practice": ["实践", "项目", "Web", "Spring", "实操", "工程", "测试", "运维"],
    "cap_req_digital": ["数据", "Python", "SQL", "Redis", "自动化", "Linux", "数字"],
    "cap_req_innovation": ["创新", "设计", "竞赛", "挑战"],
    "cap_req_teamwork": ["团队", "协作", "沟通", "管理"],
    "cap_req_social": ["营销", "商务", "销售", "社会", "网络"],
    "cap_req_growth": ["学习", "成长", "Git", "Office", "入门"],
}


def _cfg_int(key: str, default: int) -> int:
    try:
        return int(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return default


def _text_blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _score_learning_resource(
    row: Dict[str, Any],
    *,
    top_gaps: List[str],
    phase: str,
    match_score: float,
) -> float:
    blob = _text_blob(row.get("skill_tag"), row.get("resource_name"), row.get("resource_desc"))
    score = 0.2
    diff = str(row.get("difficulty") or "")
    if phase == "short_term" and diff == "入门":
        score += 0.25
    elif phase == "mid_term" and diff == "进阶":
        score += 0.25
    elif diff:
        score += 0.1
    for dim in top_gaps[:3]:
        hints = _DIM_HINTS.get(dim, [])
        if any(h.lower() in blob for h in hints):
            score += 0.18
    rtype = str(row.get("resource_type") or "")
    if rtype == "视频课程":
        score += 0.08
    if match_score < 60 and diff == "入门":
        score += 0.1
    return round(min(1.0, score), 4)


def _parse_cap_tags(cap_tags: Any) -> List[str]:
    raw = str(cap_tags or "")
    return [p.strip() for p in raw.split("|") if p.strip()]


def _score_competition(
    row: Dict[str, Any],
    *,
    top_gaps: List[str],
    phase: str,
    match_score: float = 50.0,
) -> float:
    tags = set(_parse_cap_tags(row.get("cap_tags")))
    score = 0.25
    overlap = len(tags.intersection(set(top_gaps)))
    score += min(0.45, overlap * 0.15)
    diff = str(row.get("difficulty") or "")
    if phase == "mid_term" and diff in ("进阶", "高阶"):
        score += 0.2
    elif phase == "short_term" and diff == "入门":
        score += 0.1
    ctype = str(row.get("competition_type") or "")
    if "创新" in ctype and "cap_req_innovation" in top_gaps:
        score += 0.12
    if match_score < 60 and diff == "入门":
        score += 0.08
    return round(min(1.0, score), 4)


def _rank_pool(
    rows: List[Dict[str, Any]],
    *,
    scorer,
    phase: str,
    top_gaps: List[str],
    match_score: float,
    limit: int,
) -> List[Dict[str, Any]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for row in rows:
        s = scorer(row, top_gaps=top_gaps, phase=phase, match_score=match_score)
        scored.append((s, {**row, "_score": s}))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("resource_id") or x[1].get("competition_id") or "")))
    return [x[1] for x in scored[:limit]]


def _serialize_lr(row: Dict[str, Any], *, phase: str, rationale: str = "", source: str = "graph") -> Dict[str, Any]:
    return {
        "resource_id": str(row.get("resource_id") or ""),
        "resource_name": str(row.get("resource_name") or ""),
        "resource_desc": str(row.get("resource_desc") or "")[:500],
        "resource_url": str(row.get("resource_url") or ""),
        "resource_type": str(row.get("resource_type") or ""),
        "difficulty": str(row.get("difficulty") or ""),
        "source": str(row.get("source") or ""),
        "skill_tag": str(row.get("skill_tag") or ""),
        "score": float(row.get("_score") or 0),
        "phase": phase,
        "rationale": rationale[:120],
        "origin": source,
    }


def _serialize_comp(
    row: Dict[str, Any], *, phase: str, rationale: str = "", source: str = "graph"
) -> Dict[str, Any]:
    return {
        "competition_id": str(row.get("competition_id") or ""),
        "competition_name": str(row.get("competition_name") or ""),
        "competition_desc": str(row.get("competition_desc") or "")[:500],
        "official_url": str(row.get("official_url") or ""),
        "competition_type": str(row.get("competition_type") or ""),
        "difficulty": str(row.get("difficulty") or ""),
        "cap_tags": _parse_cap_tags(row.get("cap_tags")),
        "award_level": str(row.get("award_level") or ""),
        "score": float(row.get("_score") or 0),
        "phase": phase,
        "rationale": rationale[:120],
        "origin": source,
    }


def _rule_pick(
    lr_pool: List[Dict[str, Any]],
    comp_pool: List[Dict[str, Any]],
    *,
    lr_final: int,
    comp_final: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    picked_lr: List[Dict[str, Any]] = []
    seen_types: Set[str] = set()
    for row in lr_pool:
        if len(picked_lr) >= lr_final:
            break
        rt = str(row.get("resource_type") or "")
        if rt in seen_types and len(picked_lr) >= 2:
            continue
        picked_lr.append(row)
        seen_types.add(rt)
    for row in lr_pool:
        if len(picked_lr) >= lr_final:
            break
        if row not in picked_lr:
            picked_lr.append(row)
    for i, row in enumerate(picked_lr):
        row["_llm_phase"] = "short_term" if i < max(1, lr_final // 2) else "mid_term"
        row["_llm_rationale"] = "规则推荐：按匹配分与类型多样性选取"
    picked_comp = comp_pool[:comp_final]
    for row in picked_comp:
        row["_llm_phase"] = "mid_term"
        row["_llm_rationale"] = "规则推荐：按能力标签重合度选取"
    return picked_lr[:lr_final], picked_comp


def _lr_brief_for_llm(candidates: List[Dict[str, Any]], *, limit: int = 12) -> List[Dict[str, Any]]:
    return [
        {
            "resource_id": r.get("resource_id"),
            "resource_name": r.get("resource_name"),
            "resource_type": r.get("resource_type"),
            "difficulty": r.get("difficulty"),
            "skill_tag": r.get("skill_tag"),
            "score": r.get("_score"),
        }
        for r in candidates[:limit]
    ]


def _comp_brief_for_llm(candidates: List[Dict[str, Any]], *, limit: int = 8) -> List[Dict[str, Any]]:
    return [
        {
            "competition_id": c.get("competition_id"),
            "competition_name": c.get("competition_name"),
            "difficulty": c.get("difficulty"),
            "cap_tags": _parse_cap_tags(c.get("cap_tags")),
            "score": c.get("_score"),
        }
        for c in candidates[:limit]
    ]


def _selection_from_parsed_item(
    parsed: Dict[str, Any],
    *,
    lr_candidates: List[Dict[str, Any]],
    comp_candidates: List[Dict[str, Any]],
    lr_final: int,
    comp_final: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    allowed_lr = {str(x.get("resource_id")) for x in lr_candidates}
    allowed_cp = {str(x.get("competition_id")) for x in comp_candidates}
    lr_by_id = {str(r.get("resource_id")): r for r in lr_candidates}
    cp_by_id = {str(r.get("competition_id")): r for r in comp_candidates}
    lr_rows: List[Dict[str, Any]] = []
    comp_rows: List[Dict[str, Any]] = []
    for it in parsed.get("learning_resources") or []:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("resource_id") or "").strip()
        if rid not in allowed_lr or rid not in lr_by_id:
            continue
        row = dict(lr_by_id[rid])
        row["_llm_phase"] = str(it.get("phase") or "short_term")
        row["_llm_rationale"] = str(it.get("rationale") or "")[:120]
        lr_rows.append(row)
    for it in parsed.get("competitions") or []:
        if not isinstance(it, dict):
            continue
        cid = str(it.get("competition_id") or "").strip()
        if cid not in allowed_cp or cid not in cp_by_id:
            continue
        row = dict(cp_by_id[cid])
        row["_llm_phase"] = str(it.get("phase") or "mid_term")
        row["_llm_rationale"] = str(it.get("rationale") or "")[:120]
        comp_rows.append(row)
    return lr_rows[:lr_final], comp_rows[:comp_final]


def _curate_batch_with_llm(
    jobs: List[Dict[str, Any]],
    *,
    lr_final: int,
    comp_final: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    一次 DeepSeek 请求为全部目标策展。返回 job_id -> {lr, cp, meta}。
    """
    cfg = current_app.config
    if not jobs:
        return {}, {"ok": False, "reason": "empty_jobs", "mode": "batch"}
    if not truthy(cfg.get("CAREER_ENABLE_RECOMMENDATION_LLM", True)):
        return {}, {"ok": False, "reason": "CAREER_ENABLE_RECOMMENDATION_LLM disabled", "mode": "batch"}

    api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        return {}, {"ok": False, "reason": "missing DEEPSEEK_API_KEY", "mode": "batch"}

    brief_jobs = []
    for j in jobs[:5]:
        brief_jobs.append(
            {
                "job_id": j["job_id"],
                "job_title_name": j["job_title_name"],
                "match_score": j["match_score"],
                "top_gap_dimensions": j["top_gaps"],
                "top_gap_labels": [DIM_LABELS.get(d, d) for d in j["top_gaps"]],
                "candidates": {
                    "learning_resources": _lr_brief_for_llm(j["lr_candidates"]),
                    "competitions": _comp_brief_for_llm(j["comp_candidates"]),
                },
            }
        )

    payload = {
        "task": "curate_career_resources_batch",
        "pick_limits": {"learning_resources": lr_final, "competitions": comp_final},
        "jobs": brief_jobs,
        "rules": [
            "每个 job_id 必须各输出一条",
            "只能从该 job candidates 中的 id 选择，禁止编造",
            "短期偏入门课程，中期偏竞赛与进阶",
            "rationale 每条 <= 40 字",
        ],
        "output_schema": {
            "items": [
                {
                    "job_id": "string",
                    "learning_resources": [
                        {"resource_id": "str", "phase": "short_term|mid_term", "rationale": "str"}
                    ],
                    "competitions": [
                        {"competition_id": "str", "phase": "mid_term", "rationale": "str"}
                    ],
                }
            ]
        },
    }
    model = str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat")
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    try:
        text = _call_openai_compatible(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model=model,
            timeout=timeout,
            system_prompt="你是职业规划资源策展助手。仅输出 JSON 对象，禁止 markdown。",
            user_prompt=json.dumps(redact_payload(payload), ensure_ascii=False),
            temperature=0.35,
        )
        parsed = json.loads(strip_json_fence(text))
        items = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(items, list):
            return {}, {"ok": False, "reason": "llm_items_missing", "mode": "batch", "model": model}

        job_index = {str(j["job_id"]): j for j in jobs}
        out: Dict[str, Dict[str, Any]] = {}
        updated = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            jid = str(it.get("job_id") or "").strip()
            if jid not in job_index:
                continue
            j = job_index[jid]
            lr_rows, comp_rows = _selection_from_parsed_item(
                it,
                lr_candidates=j["lr_candidates"],
                comp_candidates=j["comp_candidates"],
                lr_final=lr_final,
                comp_final=comp_final,
            )
            if not lr_rows and not comp_rows:
                continue
            out[jid] = {
                "lr": lr_rows,
                "cp": comp_rows,
                "meta": {"ok": True, "provider": "deepseek", "model": model, "mode": "batch"},
            }
            updated += 1
        return out, {
            "ok": updated > 0,
            "updated": updated,
            "provider": "deepseek",
            "model": model,
            "mode": "batch",
            "job_count": len(jobs),
        }
    except Exception as exc:  # noqa: BLE001
        return {}, {"ok": False, "reason": str(exc), "mode": "batch", "fallback": "rule"}


def _curate_with_llm(
    *,
    job_id: str,
    job_title_name: str,
    top_gaps: List[str],
    match_score: float,
    lr_candidates: List[Dict[str, Any]],
    comp_candidates: List[Dict[str, Any]],
    lr_final: int,
    comp_final: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    cfg = current_app.config
    meta: Dict[str, Any] = {"ok": False, "reason": "disabled"}
    if not truthy(cfg.get("CAREER_ENABLE_RECOMMENDATION_LLM", True)):
        lr, cp = _rule_pick(lr_candidates, comp_candidates, lr_final=lr_final, comp_final=comp_final)
        return lr, cp, {"ok": False, "reason": "CAREER_ENABLE_RECOMMENDATION_LLM disabled", "fallback": "rule"}

    api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        lr, cp = _rule_pick(lr_candidates, comp_candidates, lr_final=lr_final, comp_final=comp_final)
        return lr, cp, {"ok": False, "reason": "missing DEEPSEEK_API_KEY", "fallback": "rule"}

    payload = {
        "task": "curate_career_resources",
        "job_id": job_id,
        "job_title_name": job_title_name,
        "match_score": match_score,
        "top_gap_dimensions": top_gaps,
        "top_gap_labels": [DIM_LABELS.get(d, d) for d in top_gaps],
        "pick_limits": {"learning_resources": lr_final, "competitions": comp_final},
        "candidates": {
            "learning_resources": _lr_brief_for_llm(lr_candidates, limit=20),
            "competitions": _comp_brief_for_llm(comp_candidates, limit=12),
        },
        "rules": [
            "只能从 candidates 中的 id 选择，禁止编造新 id 或 URL",
            "短期偏入门课程，中期偏竞赛与进阶",
            "每条附 rationale <= 40 字",
        ],
        "output_schema": {
            "learning_resources": [
                {"resource_id": "str", "phase": "short_term|mid_term", "rationale": "str"}
            ],
            "competitions": [{"competition_id": "str", "phase": "mid_term", "rationale": "str"}],
        },
    }
    model = str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat")
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    try:
        text = _call_openai_compatible(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model=model,
            timeout=timeout,
            system_prompt="你是职业规划资源策展助手。仅输出 JSON 对象，禁止 markdown。",
            user_prompt=json.dumps(redact_payload(payload), ensure_ascii=False),
            temperature=0.35,
        )
        parsed = json.loads(strip_json_fence(text))
        lr_rows, comp_rows = _selection_from_parsed_item(
            parsed,
            lr_candidates=lr_candidates,
            comp_candidates=comp_candidates,
            lr_final=lr_final,
            comp_final=comp_final,
        )
        if not lr_rows and not comp_rows:
            raise ValueError("llm_empty_selection")
        meta = {"ok": True, "provider": "deepseek", "model": model, "fallback": None, "mode": "single"}
        return lr_rows, comp_rows, meta
    except Exception as exc:  # noqa: BLE001
        lr, cp = _rule_pick(lr_candidates, comp_candidates, lr_final=lr_final, comp_final=comp_final)
        return lr, cp, {"ok": False, "reason": str(exc), "fallback": "rule"}


def build_graph_recommendations(
    target_insights: List[Dict[str, Any]],
    *,
    use_llm_curator: bool = True,
) -> Dict[str, Any]:
    """构建完整 recommendations 块（含 by_target / shared / meta）。规则先出，可选 batch LLM 覆盖。"""
    if not truthy(current_app.config.get("CAREER_ENABLE_GRAPH_RECOMMENDATIONS", True)):
        return {"schema_version": 1, "enabled": False, "by_target": [], "shared": {}, "meta": {}}

    job_ids = [str(t.get("id") or "").strip() for t in target_insights if str(t.get("id") or "").strip()]
    title_map = resolve_job_title_names(job_ids)

    pool_lr = _cfg_int("CAREER_LR_POOL_PER_TARGET", 18)
    pool_comp = _cfg_int("CAREER_COMP_POOL_PER_TARGET", 10)
    final_lr = _cfg_int("CAREER_LR_PER_TARGET", 6)
    final_comp = _cfg_int("CAREER_COMP_PER_TARGET", 3)

    by_target: List[Dict[str, Any]] = []
    title_to_targets: Dict[str, List[str]] = {}
    curator_runs: List[Dict[str, Any]] = []
    total_lr_cand = 0
    total_comp_cand = 0
    pending_jobs: List[Dict[str, Any]] = []
    rule_by_job: Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]] = {}

    for t in target_insights:
        jid = str(t.get("id") or "").strip()
        title_name = title_map.get(jid) or str(t.get("title") or "").strip()
        if not title_name:
            continue
        title_to_targets.setdefault(title_name, []).append(jid)
        gaps = (t.get("match_preview") or {}).get("dimension_gaps") or {}
        top_gaps = _top_gap_dimensions(gaps, 3)
        ms = float((t.get("match_preview") or {}).get("match_score") or 0)

        raw_lr = fetch_learning_resources_for_title(title_name)
        raw_cp = fetch_competitions_for_title(title_name)
        total_lr_cand += len(raw_lr)
        total_comp_cand += len(raw_cp)

        lr_pool = _rank_pool(
            raw_lr,
            scorer=_score_learning_resource,
            phase="short_term",
            top_gaps=top_gaps,
            match_score=ms,
            limit=pool_lr,
        )
        comp_pool = _rank_pool(
            raw_cp,
            scorer=_score_competition,
            phase="mid_term",
            top_gaps=top_gaps,
            match_score=ms,
            limit=pool_comp,
        )

        rule_lr, rule_cp = _rule_pick(lr_pool, comp_pool, lr_final=final_lr, comp_final=final_comp)
        rule_by_job[jid] = (rule_lr, rule_cp)
        pending_jobs.append(
            {
                "job_id": jid,
                "job_title_name": title_name,
                "top_gaps": top_gaps,
                "match_score": ms,
                "lr_candidates": lr_pool,
                "comp_candidates": comp_pool,
            }
        )

    batch_by_job: Dict[str, Dict[str, Any]] = {}
    batch_meta: Dict[str, Any] = {"ok": False, "mode": "rule_only"}
    if use_llm_curator and pending_jobs:
        batch_by_job, batch_meta = _curate_batch_with_llm(
            pending_jobs,
            lr_final=final_lr,
            comp_final=final_comp,
        )

    for t in target_insights:
        jid = str(t.get("id") or "").strip()
        title_name = title_map.get(jid) or str(t.get("title") or "").strip()
        if not title_name or jid not in rule_by_job:
            continue
        gaps = (t.get("match_preview") or {}).get("dimension_gaps") or {}
        top_gaps = _top_gap_dimensions(gaps, 3)
        ms = float((t.get("match_preview") or {}).get("match_score") or 0)
        rule_lr, rule_cp = rule_by_job[jid]
        llm_pick = batch_by_job.get(jid) or {}
        if llm_pick.get("meta", {}).get("ok"):
            picked_lr = llm_pick["lr"]
            picked_cp = llm_pick["cp"]
            cur_meta = llm_pick["meta"]
        else:
            picked_lr, picked_cp = rule_lr, rule_cp
            cur_meta = llm_pick.get("meta") or {
                "ok": False,
                "fallback": "rule",
                "reason": batch_meta.get("reason") or "batch_miss",
            }
        curator_runs.append({"job_id": jid, **cur_meta})

        lr_out = [
            _serialize_lr(
                r,
                phase=str(r.get("_llm_phase") or "short_term"),
                rationale=str(r.get("_llm_rationale") or "规则推荐：贴合能力缺口与阶段"),
                source="graph+llm" if cur_meta.get("ok") else "graph+rule",
            )
            for r in picked_lr
        ]
        cp_out = [
            _serialize_comp(
                r,
                phase=str(r.get("_llm_phase") or "mid_term"),
                rationale=str(r.get("_llm_rationale") or "规则推荐：贴合能力维度标签"),
                source="graph+llm" if cur_meta.get("ok") else "graph+rule",
            )
            for r in picked_cp
        ]
        by_target.append(
            {
                "job_id": jid,
                "job_title_name": title_name,
                "match_score": ms,
                "top_gaps": top_gaps,
                "top_gap_labels": [DIM_LABELS.get(d, d) for d in top_gaps],
                "learning_resources": lr_out,
                "competitions": cp_out,
            }
        )

    # 多目标共用同一 JobTitle 的资源
    shared_lr: Dict[str, Dict[str, Any]] = {}
    shared_cp: Dict[str, Dict[str, Any]] = {}
    for title, jids in title_to_targets.items():
        if len(jids) < 2:
            continue
        for block in by_target:
            if block.get("job_title_name") != title:
                continue
            for lr in block.get("learning_resources") or []:
                rid = str(lr.get("resource_id") or "")
                if rid:
                    shared_lr[rid] = lr
            for cp in block.get("competitions") or []:
                cid = str(cp.get("competition_id") or "")
                if cid:
                    shared_cp[cid] = cp

    return {
        "schema_version": 1,
        "enabled": True,
        "by_target": by_target,
        "shared": {
            "learning_resources": list(shared_lr.values()),
            "competitions": list(shared_cp.values()),
        },
        "meta": {
            "retrieval": {
                "lr_candidates_seen": total_lr_cand,
                "comp_candidates_seen": total_comp_cand,
                "job_titles_resolved": len(title_map),
            },
            "curator": curator_runs,
            "curator_batch": batch_meta,
            "limits": {"lr_per_target": final_lr, "comp_per_target": final_comp},
        },
    }


def enrich_growth_plan_with_recommendations(
    short_term: List[Dict[str, Any]],
    mid_term: List[Dict[str, Any]],
    recommendations: Dict[str, Any],
) -> None:
    """为 growth_plan 各阶段条目附加 learning_path_refs / practice_plan_refs。"""
    if not recommendations.get("enabled"):
        return
    by_target = recommendations.get("by_target") or []
    if not isinstance(by_target, list):
        return

    all_lr: List[Dict[str, Any]] = []
    all_cp: List[Dict[str, Any]] = []
    for block in by_target:
        if not isinstance(block, dict):
            continue
        all_lr.extend(block.get("learning_resources") or [])
        all_cp.extend(block.get("competitions") or [])

    def _refs_for_dim(dim: str, phase: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        hints = _DIM_HINTS.get(dim, [])
        lr_hits = []
        for lr in all_lr:
            lr_phase = str(lr.get("phase") or "")
            if phase == "short_term" and lr_phase == "mid_term":
                continue
            blob = _text_blob(lr.get("skill_tag"), lr.get("resource_name"))
            if any(h.lower() in blob for h in hints) or not hints:
                lr_hits.append(lr)
        lr_hits.sort(key=lambda x: -float(x.get("score") or 0))
        cp_hits = []
        tags_dim = {dim}
        for cp in all_cp:
            if tags_dim.intersection(set(cp.get("cap_tags") or [])):
                cp_hits.append(cp)
            else:
                blob = _text_blob(cp.get("competition_name"), cp.get("competition_desc"))
                if any(h.lower() in blob for h in hints):
                    cp_hits.append(cp)
        cp_hits.sort(key=lambda x: -float(x.get("score") or 0))
        return lr_hits[:3], cp_hits[:2]

    for item in short_term:
        if not isinstance(item, dict):
            continue
        dim = str(item.get("focus_dimension") or "")
        lr_refs, cp_refs = _refs_for_dim(dim, "short_term")
        item["learning_path_refs"] = [
            {
                "kind": "learning_resource",
                "id": lr.get("resource_id"),
                "label": lr.get("resource_name"),
                "url": lr.get("resource_url"),
            }
            for lr in lr_refs
        ]
        item["practice_plan_refs"] = [
            {
                "kind": "competition",
                "id": cp.get("competition_id"),
                "label": cp.get("competition_name"),
                "url": cp.get("official_url"),
            }
            for cp in cp_refs[:1]
        ]
        if lr_refs and isinstance(item.get("learning_path"), list):
            names = [str(lr.get("resource_name") or "") for lr in lr_refs[:2] if lr.get("resource_name")]
            if names:
                item["learning_path"] = [
                    f"优先学习：{'、'.join(names)}（图谱推荐）",
                    *(item.get("learning_path") or [])[:1],
                ]

    for item in mid_term:
        if not isinstance(item, dict):
            continue
        dim = str(item.get("focus_dimension") or "")
        lr_refs, cp_refs = _refs_for_dim(dim, "mid_term")
        item["learning_path_refs"] = [
            {
                "kind": "learning_resource",
                "id": lr.get("resource_id"),
                "label": lr.get("resource_name"),
                "url": lr.get("resource_url"),
            }
            for lr in lr_refs[:2]
        ]
        item["practice_plan_refs"] = [
            {
                "kind": "competition",
                "id": cp.get("competition_id"),
                "label": cp.get("competition_name"),
                "url": cp.get("official_url"),
            }
            for cp in cp_refs
        ]
        if cp_refs and isinstance(item.get("practice_plan"), list):
            cname = str(cp_refs[0].get("competition_name") or "")
            if cname:
                item["practice_plan"] = [
                    f"建议参赛：{cname}（图谱推荐）",
                    *(item.get("practice_plan") or [])[:1],
                ]


def pick_replan_resource_hints(
    report_obj: Dict[str, Any],
    focus_dimensions: List[str],
) -> List[str]:
    """从重规划维度选取可执行图谱资源提示。"""
    if not focus_dimensions:
        return []
    block: Dict[str, Any] = {}
    plans = report_obj.get("plans_by_target") or []
    if isinstance(plans, list) and plans and isinstance(plans[0], dict):
        inner = plans[0].get("recommendations") or {}
        block = {
            "learning_resources": inner.get("learning_resources") or [],
            "competitions": inner.get("competitions") or [],
        }
    if not block:
        rec = report_obj.get("recommendations") or {}
        if not rec.get("enabled"):
            return []
        by_target = rec.get("by_target") or []
        if not by_target:
            return []
        block = by_target[0] if isinstance(by_target[0], dict) else {}
    dim = focus_dimensions[0]
    hints = _DIM_HINTS.get(dim, [])
    lines: List[str] = []
    for lr in block.get("learning_resources") or []:
        blob = _text_blob(lr.get("skill_tag"), lr.get("resource_name"))
        if any(h.lower() in blob for h in hints) or not hints:
            name = str(lr.get("resource_name") or "")
            url = str(lr.get("resource_url") or "")
            if name:
                lines.append(f"完成课程「{name}」" + (f"：{url}" if url else ""))
            if len(lines) >= 2:
                break
    for cp in block.get("competitions") or []:
        if dim in (cp.get("cap_tags") or []):
            name = str(cp.get("competition_name") or "")
            url = str(cp.get("official_url") or "")
            if name:
                lines.append(f"了解赛事「{name}」" + (f"：{url}" if url else ""))
            break
    return lines[:3]
