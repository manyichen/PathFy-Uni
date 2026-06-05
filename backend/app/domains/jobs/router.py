import hashlib
import json
from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, request

from app.infrastructure.neo4j import (
    CONF_KEYS,
    DIM_KEYS,
    neo4j_driver,
    neo4j_settings,
    serialize_job_row,
)
from app.infrastructure.llm import call_ark_json
from app.infrastructure.salary import (
    cypher_job_salary_display,
    cypher_job_salary_raw,
    parse_salary_range,
)

_SALARY_DISP = cypher_job_salary_display()
_SALARY_RAW = cypher_job_salary_raw()

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")

_JOBS_FILTER_WHERE = """
    (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
"""

_JOBS_RETURN_FIELDS = f"""
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      {_SALARY_DISP},
      {_SALARY_RAW},
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
      coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
      coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
      coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
      coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
      coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
      coalesce(j.cap_req_social, 0.0) AS cap_req_social,
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
      coalesce(j.cap_conf_theory, 0.0) AS cap_conf_theory,
      coalesce(j.cap_conf_cross, 0.0) AS cap_conf_cross,
      coalesce(j.cap_conf_practice, 0.0) AS cap_conf_practice,
      coalesce(j.cap_conf_digital, 0.0) AS cap_conf_digital,
      coalesce(j.cap_conf_innovation, 0.0) AS cap_conf_innovation,
      coalesce(j.cap_conf_teamwork, 0.0) AS cap_conf_teamwork,
      coalesce(j.cap_conf_social, 0.0) AS cap_conf_social,
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth
"""

_JOBS_SHUFFLE_CACHE: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
_JOBS_SHUFFLE_CACHE_ORDER: List[Tuple[str, str]] = []
_MAX_JOBS_SHUFFLE_CACHES = 32


def _normalize_jobs_sort(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if value in {"random", "score_asc", "score_desc"}:
        return value
    return "default"


def _jobs_order_clause(sort_mode: str) -> str:
    if sort_mode == "score_asc":
        return "ORDER BY total_score ASC, title ASC"
    return "ORDER BY total_score DESC, title ASC"


def _jobs_shuffle_key(job_id: str, seed: str) -> str:
    return hashlib.md5(f"{seed}:{job_id}".encode("utf-8")).hexdigest()


def _shuffled_job_rows(keyword: str, seed: str) -> List[Dict[str, Any]]:
    cache_key = (keyword, seed)
    cached = _JOBS_SHUFFLE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    uri, user, password, database = neo4j_settings()
    query = f"""
    MATCH (j:Job)
    WHERE {_JOBS_FILTER_WHERE}
    WITH j,
      (coalesce(j.cap_req_theory, 0.0) +
       coalesce(j.cap_req_cross, 0.0) +
       coalesce(j.cap_req_practice, 0.0) +
       coalesce(j.cap_req_digital, 0.0) +
       coalesce(j.cap_req_innovation, 0.0) +
       coalesce(j.cap_req_teamwork, 0.0) +
       coalesce(j.cap_req_social, 0.0) +
       coalesce(j.cap_req_growth, 0.0)) AS total_score
    RETURN
      {_JOBS_RETURN_FIELDS},
      total_score
    """
    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        rows = [dict(r) for r in session.run(query, {"q": keyword})]
    rows.sort(key=lambda row: _jobs_shuffle_key(str(row.get("id") or ""), seed))
    _JOBS_SHUFFLE_CACHE[cache_key] = rows
    _JOBS_SHUFFLE_CACHE_ORDER.append(cache_key)
    while len(_JOBS_SHUFFLE_CACHE_ORDER) > _MAX_JOBS_SHUFFLE_CACHES:
        old_key = _JOBS_SHUFFLE_CACHE_ORDER.pop(0)
        _JOBS_SHUFFLE_CACHE.pop(old_key, None)
    return rows


def _jobs_page_payload(
    rows: List[Dict[str, Any]],
    *,
    page: int,
    page_size: int,
    sort_mode: str,
    seed: str = "",
) -> Dict[str, Any]:
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page_num = min(max(1, page), total_pages)
    start = (page_num - 1) * page_size
    page_rows = rows[start : start + page_size]
    data = [serialize_job_row(r) for r in page_rows]
    payload: Dict[str, Any] = {
        "jobs": data,
        "total": total,
        "page": page_num,
        "page_size": page_size,
        "total_pages": total_pages,
        "sort": sort_mode,
    }
    if sort_mode == "random" and seed:
        payload["seed"] = seed
    return payload


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    raw = str(value or "").strip()
    if not raw:
        return []
    sep = "|" if "|" in raw else ","
    return [x.strip() for x in raw.split(sep) if x.strip()]


def _dedupe_by_key(rows: List[Dict[str, Any]], key_fn) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for row in rows:
        key = key_fn(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _serialize_graph_resource(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "resource_id": str(row.get("resource_id") or "").strip(),
        "resource_name": str(row.get("resource_name") or "").strip(),
        "resource_desc": str(row.get("resource_desc") or "")[:500],
        "resource_url": str(row.get("resource_url") or "").strip(),
        "resource_type": str(row.get("resource_type") or "").strip(),
        "difficulty": str(row.get("difficulty") or "").strip(),
        "source": str(row.get("source") or "").strip(),
        "skill_tag": str(row.get("skill_tag") or "").strip(),
        "stage": _safe_int(row.get("stage"), 0),
        "stage_role": str(row.get("stage_role") or "").strip(),
        "rank": _safe_int(row.get("rank"), 0),
        "score": round(_safe_float(row.get("score")), 4),
        "rationale": str(row.get("rationale") or "").strip(),
    }


def _serialize_graph_competition(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "competition_id": str(row.get("competition_id") or "").strip(),
        "competition_name": str(row.get("competition_name") or "").strip(),
        "competition_desc": str(row.get("competition_desc") or "")[:500],
        "official_url": str(row.get("official_url") or "").strip(),
        "competition_type": str(row.get("competition_type") or "").strip(),
        "organizer": str(row.get("organizer") or "").strip(),
        "target_audience": str(row.get("target_audience") or "").strip(),
        "team_mode": str(row.get("team_mode") or "").strip(),
        "frequency": str(row.get("frequency") or "").strip(),
        "difficulty": str(row.get("difficulty") or "").strip(),
        "cap_tags": _as_text_list(row.get("cap_tags")),
        "skill_tags": _as_text_list(row.get("skill_tags")),
        "award_level": str(row.get("award_level") or "").strip(),
        "stage": _safe_int(row.get("stage"), 0),
        "stage_role": str(row.get("stage_role") or "").strip(),
        "rank": _safe_int(row.get("rank"), 0),
        "score": round(_safe_float(row.get("score")), 4),
        "match_via": str(row.get("match_via") or "").strip(),
        "rationale": str(row.get("rationale") or "").strip(),
    }


def _normalize_graph_resources(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = [
        _serialize_graph_resource(x)
        for x in rows
        if isinstance(x, dict) and str(x.get("resource_id") or x.get("resource_name") or "").strip()
    ]
    cleaned.sort(
        key=lambda x: (
            x.get("stage") or 99,
            x.get("rank") or 999,
            -float(x.get("score") or 0),
            x.get("resource_id") or "",
        )
    )
    return _dedupe_by_key(cleaned, lambda x: (x.get("resource_id"), x.get("stage")))


def _normalize_graph_competitions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = [
        _serialize_graph_competition(x)
        for x in rows
        if isinstance(x, dict) and str(x.get("competition_id") or x.get("competition_name") or "").strip()
    ]
    cleaned.sort(
        key=lambda x: (
            x.get("stage") or 99,
            x.get("rank") or 999,
            -float(x.get("score") or 0),
            x.get("competition_id") or "",
        )
    )
    return _dedupe_by_key(cleaned, lambda x: (x.get("competition_id"), x.get("stage")))


def _fetch_title_materials(session, title_names: List[str]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    titles = sorted({str(x or "").strip() for x in title_names if str(x or "").strip()})
    if not titles:
        return {}
    out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        title: {"learning_resources": [], "competitions": []} for title in titles
    }
    resource_query = """
    UNWIND $titles AS title
    MATCH (jt:JobTitle {name: title})<-[:FOR_JOB_TITLE]-(lr:LearningResource)
    RETURN
      title,
      lr.resource_id AS resource_id,
      lr.resource_name AS resource_name,
      lr.resource_desc AS resource_desc,
      lr.resource_url AS resource_url,
      lr.resource_type AS resource_type,
      lr.difficulty AS difficulty,
      lr.source AS source,
      lr.skill_tag AS skill_tag
    ORDER BY title ASC, lr.difficulty ASC, lr.resource_id ASC
    """
    competition_query = """
    UNWIND $titles AS title
    MATCH (jt:JobTitle {name: title})<-[:FOR_JOB_TITLE]-(c:Competition)
    RETURN
      title,
      c.competition_id AS competition_id,
      c.competition_name AS competition_name,
      c.competition_desc AS competition_desc,
      c.official_url AS official_url,
      c.competition_type AS competition_type,
      c.organizer AS organizer,
      c.target_audience AS target_audience,
      c.team_mode AS team_mode,
      c.frequency AS frequency,
      c.difficulty AS difficulty,
      c.cap_tags AS cap_tags,
      c.skill_tags AS skill_tags,
      c.award_level AS award_level
    ORDER BY title ASC, c.difficulty ASC, c.competition_id ASC
    """
    for row in session.run(resource_query, {"titles": titles}):
        rec = dict(row)
        title = str(rec.pop("title") or "").strip()
        if title in out:
            out[title]["learning_resources"].append(rec)
    for row in session.run(competition_query, {"titles": titles}):
        rec = dict(row)
        title = str(rec.pop("title") or "").strip()
        if title in out:
            out[title]["competitions"].append(rec)

    for title, block in out.items():
        block["learning_resources"] = _normalize_graph_resources(block["learning_resources"])[:8]
        block["competitions"] = _normalize_graph_competitions(block["competitions"])[:4]
    return out


def _stage_period(stage: int) -> str:
    if stage <= 1:
        return "0-3个月"
    if stage == 2:
        return "3-9个月"
    return "9-12个月"


def _promotion_stage_label(stage: int) -> str:
    if stage <= 1:
        return "基础补齐"
    if stage == 2:
        return "岗位化实践"
    return "成果冲刺"


def _promotion_actions(stage: int, role: str, target_title: str) -> List[str]:
    role_name = role or target_title or "目标岗位"
    if stage <= 1:
        return [
            f"围绕「{role_name}」补齐岗位基础知识，优先完成入门课程与核心工具练习。",
            "把学习内容整理为笔记、代码片段或案例复盘，形成后续项目素材。",
        ]
    if stage == 2:
        return [
            f"按「{role_name}」的真实工作场景完成一个可展示项目，突出个人职责和技术取舍。",
            "结合图谱推荐竞赛或实践任务，补充团队协作、交付和问题解决证据。",
        ]
    return [
        f"面向「{target_title or role_name}」整理作品集、简历关键词和面试讲述线。",
        "用岗位 JD 反向检查能力缺口，完成模拟面试和投递反馈复盘。",
    ]


def _build_promotion_route(
    item: Dict[str, Any],
    *,
    fallback_resources: List[Dict[str, Any]],
    fallback_competitions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    promotion_resources = _normalize_graph_resources(item.get("resources") or [])
    promotion_competitions = _normalize_graph_competitions(item.get("competitions") or [])
    stage_roles = [
        str(item.get("stage1") or "").strip(),
        str(item.get("stage2") or "").strip(),
        str(item.get("stage3") or "").strip(),
    ]
    target_title = (
        str(item.get("stage3_job_title") or "").strip()
        or stage_roles[2]
        or str(item.get("to_title") or "").strip()
        or str(item.get("promotion_name") or "").strip()
        or "未命名岗位"
    )

    stages = []
    for idx, role in enumerate(stage_roles, start=1):
        if not role and idx < 3:
            continue
        stage_resources = [x for x in promotion_resources if x.get("stage") == idx]
        stage_competitions = [x for x in promotion_competitions if x.get("stage") == idx]
        if not stage_resources and idx <= 2:
            stage_resources = fallback_resources[:3]
        if not stage_competitions and idx >= 2:
            stage_competitions = fallback_competitions[:2]
        stage_role = role or target_title
        stages.append(
            {
                "stage": idx,
                "label": _promotion_stage_label(idx),
                "role": stage_role,
                "period": _stage_period(idx),
                "milestone": f"达到「{stage_role}」阶段可展示水平",
                "actions": _promotion_actions(idx, stage_role, target_title),
                "learning_resources": stage_resources[:4],
                "competitions": stage_competitions[:2],
            }
        )

    if not stages:
        stages.append(
            {
                "stage": 1,
                "label": "路径准备",
                "role": target_title,
                "period": "0-3个月",
                "milestone": f"明确「{target_title}」能力要求并完成基础补齐",
                "actions": _promotion_actions(1, target_title, target_title),
                "learning_resources": fallback_resources[:4],
                "competitions": fallback_competitions[:2],
            }
        )

    route_title = str(item.get("promotion_name") or item.get("title") or target_title).strip()
    from_title = str(item.get("from_title") or "").strip()
    route_text = str(item.get("promotion") or "").strip() or " → ".join(
        [x["role"] for x in stages if x.get("role")]
    )
    confidence = round(_safe_float(item.get("confidence")), 4)
    rationale = str(item.get("rationale") or item.get("notes") or "").strip()
    if not rationale:
        rationale = f"该路线来自 JobTitle「{from_title}」关联的 JobPromotion 模板。"

    return {
        "id": str(item.get("id") or "").strip(),
        "job_title": from_title,
        "route_title": route_title,
        "route_text": route_text,
        "target_title": target_title,
        "confidence": confidence,
        "rationale": rationale,
        "notes": str(item.get("notes") or "").strip(),
        "stages": stages,
        "action_plan": {
            "summary": f"沿「{route_title}」推进：先补齐基础，再完成岗位化项目，最后沉淀可投递成果。",
            "phases": stages,
        },
        "learning_resources": promotion_resources[:10],
        "competitions": promotion_competitions[:6],
    }


def _build_lateral_action_plan(
    *,
    target_title: str,
    score: float,
    rationale: str,
    resources: List[Dict[str, Any]],
    competitions: List[Dict[str, Any]],
    candidate_jobs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    job_hint = candidate_jobs[0].get("title") if candidate_jobs else target_title
    early_resources = resources[:3]
    mid_resources = resources[3:6] or resources[:2]
    mid_competitions = competitions[:2]
    phases = [
        {
            "stage": 1,
            "label": "迁移评估",
            "role": target_title,
            "period": "0-2个月",
            "milestone": f"明确转向「{target_title}」的能力重合点和关键短板",
            "actions": [
                f"对照「{target_title}」岗位要求梳理可迁移能力，优先保留已有项目中的通用证据。",
                "完成入门资源学习，并把缺口整理为 2-3 个可训练任务。",
            ],
            "learning_resources": early_resources,
            "competitions": [],
        },
        {
            "stage": 2,
            "label": "转岗项目",
            "role": target_title,
            "period": "2-6个月",
            "milestone": f"形成一个面向「{target_title}」的项目或竞赛成果",
            "actions": [
                f"围绕「{job_hint or target_title}」常见场景做小型项目，补齐目标岗位表达方式。",
                "选择一项竞赛、开源任务或业务案例作为转岗证明，强调问题定义、过程和结果。",
            ],
            "learning_resources": mid_resources,
            "competitions": mid_competitions,
        },
        {
            "stage": 3,
            "label": "投递准备",
            "role": target_title,
            "period": "6-9个月",
            "milestone": f"具备投递「{target_title}」同类岗位的材料和面试叙事",
            "actions": [
                "将原岗位经历改写为目标岗位可理解的成果语言，突出迁移逻辑。",
                "优先投递图谱中同 JobTitle 的具体岗位，按面试反馈迭代项目和简历。",
            ],
            "learning_resources": resources[:2],
            "competitions": competitions[:1],
        },
    ]
    summary = f"相似度约 {score:.0%}。{rationale or '该方向由 JobTitle 横向迁移关系推荐。'}"
    return {"summary": summary, "phases": phases}


def _fetch_job_for_analysis(session, job_id):
    row = session.run(
        f"""
        MATCH (j:Job)
        WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
        OPTIONAL MATCH (j)-[:REQUIRES]->(req)
        RETURN
          coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
          coalesce(j.title, j.name, '未命名岗位') AS title,
          {_SALARY_DISP},
          {_SALARY_RAW},
          coalesce(j.company, '未知公司') AS company,
          coalesce(j.location, '未知地点') AS location,
          coalesce(j.demand, '') AS demand,
          coalesce(j.experience_text, '') AS experience_text,
          coalesce(j.experience_years, 0.0) AS experience_years,
          coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
          coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
          coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
          coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
          coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
          coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
          coalesce(j.cap_req_social, 0.0) AS cap_req_social,
          coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
          collect(DISTINCT coalesce(req.name, '')) AS requirement_names
        LIMIT 1
        """,
        {"job_id": job_id},
    ).single()
    return dict(row) if row else None


def _build_transition_analysis(from_row, to_row):
    from_reqs = {str(x).strip() for x in (from_row.get("requirement_names") or []) if str(x).strip()}
    to_reqs = {str(x).strip() for x in (to_row.get("requirement_names") or []) if str(x).strip()}

    overlap = sorted(from_reqs & to_reqs)
    missing = sorted(to_reqs - from_reqs)
    transferable = sorted(from_reqs - to_reqs)

    cap_gaps = []
    for key in DIM_KEYS:
        from_val = round(_safe_float(from_row.get(key)), 2)
        to_val = round(_safe_float(to_row.get(key)), 2)
        cap_gaps.append(
            {
                "dimension": key,
                "from": from_val,
                "to": to_val,
                "gap": round(to_val - from_val, 2),
            }
        )
    cap_gaps.sort(key=lambda x: x["gap"], reverse=True)

    from_salary = parse_salary_range(from_row.get("salary_raw") or from_row.get("salary"))
    to_salary = parse_salary_range(to_row.get("salary_raw") or to_row.get("salary"))
    salary_delta = None
    if from_salary.get("monthly_min") is not None and to_salary.get("monthly_min") is not None:
        salary_delta = round(float(to_salary["monthly_min"]) - float(from_salary["monthly_min"]), 2)

    exp_gap = round(_safe_float(to_row.get("experience_years")) - _safe_float(from_row.get("experience_years")), 2)

    return {
        "score_summary": {
            "experience_gap": exp_gap,
            "salary_min_delta": salary_delta,
            "overlap_count": len(overlap),
            "missing_count": len(missing),
        },
        "skill_overlap": overlap[:20],
        "skill_missing": missing[:20],
        "transferable_skills": transferable[:20],
        "capability_gaps": cap_gaps,
    }


def _fallback_transition_advice(from_row, to_row, analysis):
    major_gaps = [g for g in analysis["capability_gaps"] if g["gap"] > 8][:3]
    top_gap_names = [g["dimension"].replace("cap_req_", "") for g in major_gaps]
    if not top_gap_names:
        top_gap_names = ["digital", "innovation"]

    return {
        "summary": f"从{from_row.get('title', '当前岗位')}转向{to_row.get('title', '目标岗位')}总体可行，但需要补齐目标岗位关键能力与要求。",
        "feasibility": "中",
        "advantages": analysis["skill_overlap"][:5],
        "gaps": analysis["skill_missing"][:5],
        "learning_plan": [
            f"第1-2周：针对 {top_gap_names[0]} 做岗位 JD 定向学习与项目拆解。",
            "第3-5周：完成 1 个可展示的业务小项目并沉淀文档。",
            "第6-8周：按目标岗位要求补齐案例表达与面试题训练。",
        ],
        "risk_alerts": [
            "若目标岗位经验门槛明显更高，建议先投递相邻层级岗位。",
            "若技能缺口超过 5 项，建议分阶段转岗而非一次跳转。",
        ],
        "final_recommendation": "建议先进行 4-8 周补齐，再发起正式转岗投递。",
    }


def _llm_transition_advice(from_row, to_row, analysis):
    try:
        llm_result = call_ark_json(
            system_prompt=(
                "你是职业发展顾问。"
                "你会基于两个岗位信息和量化差异，给出转岗分析建议。"
                "只输出 JSON 对象，不要输出解释。"
                "字段必须包含: summary, feasibility, advantages, gaps, learning_plan, risk_alerts, final_recommendation。"
                "feasibility 仅允许: 高|中|低。"
                "advantages/gaps/learning_plan/risk_alerts 必须是字符串数组。"
            ),
            payload={"from_job": from_row, "to_job": to_row, "analysis": analysis},
        )
        if not llm_result:
            return _fallback_transition_advice(from_row, to_row, analysis)
        return {
            "summary": str(llm_result.get("summary") or ""),
            "feasibility": str(llm_result.get("feasibility") or "中"),
            "advantages": [str(x) for x in (llm_result.get("advantages") or []) if str(x).strip()][:8],
            "gaps": [str(x) for x in (llm_result.get("gaps") or []) if str(x).strip()][:8],
            "learning_plan": [str(x) for x in (llm_result.get("learning_plan") or []) if str(x).strip()][:8],
            "risk_alerts": [str(x) for x in (llm_result.get("risk_alerts") or []) if str(x).strip()][:8],
            "final_recommendation": str(llm_result.get("final_recommendation") or ""),
        }
    except Exception:
        return _fallback_transition_advice(from_row, to_row, analysis)


@jobs_bp.get("")
def list_jobs():
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    page = max(1, int(request.args.get("page", "1")))
    page_size = max(1, min(int(request.args.get("page_size", "40")), 200))
    skip = (page - 1) * page_size
    keyword = (request.args.get("q") or "").strip()
    sort_mode = _normalize_jobs_sort(request.args.get("sort") or "")
    seed = str(request.args.get("seed") or "").strip()

    if sort_mode == "random":
        if not seed:
            return jsonify({"ok": False, "message": "随机排序需要提供 seed"}), 400
        rows = _shuffled_job_rows(keyword, seed)
        return jsonify({"ok": True, "data": _jobs_page_payload(rows, page=page, page_size=page_size, sort_mode=sort_mode, seed=seed)})

    count_query = f"""
    MATCH (j:Job)
    WHERE {_JOBS_FILTER_WHERE}
    RETURN count(j) AS total
    """

    list_query = f"""
    MATCH (j:Job)
    WHERE {_JOBS_FILTER_WHERE}
    WITH j,
      (coalesce(j.cap_req_theory, 0.0) +
       coalesce(j.cap_req_cross, 0.0) +
       coalesce(j.cap_req_practice, 0.0) +
       coalesce(j.cap_req_digital, 0.0) +
       coalesce(j.cap_req_innovation, 0.0) +
       coalesce(j.cap_req_teamwork, 0.0) +
       coalesce(j.cap_req_social, 0.0) +
       coalesce(j.cap_req_growth, 0.0)) AS total_score
    RETURN
      {_JOBS_RETURN_FIELDS}
    {_jobs_order_clause(sort_mode)}
    SKIP $skip
    LIMIT $limit
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        total_row = session.run(count_query, {"q": keyword}).single()
        total = int((total_row or {}).get("total") or 0)
        rows = [
            dict(r)
            for r in session.run(
                list_query,
                {"limit": page_size, "skip": skip, "q": keyword},
            )
        ]

    data = [serialize_job_row(r) for r in rows]
    total_pages = max(1, (total + page_size - 1) // page_size)
    return jsonify(
        {
            "ok": True,
            "data": {
                "jobs": data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "sort": sort_mode,
            },
        }
    )


@jobs_bp.get("/options")
def list_job_options():
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    page = max(1, int(request.args.get("page", "1")))
    page_size = max(1, min(int(request.args.get("page_size", "20")), 100))
    skip = (page - 1) * page_size
    keyword = (request.args.get("q") or "").strip()

    count_query = """
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
    RETURN count(j) AS total
    """

    list_query = f"""
    MATCH (j:Job)
    WHERE (j.source IS NULL OR trim(toString(j.source)) = '')
      AND (
        $q = '' OR
        toLower(coalesce(j.title, j.name, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.company, '')) CONTAINS toLower($q) OR
        toLower(coalesce(j.location, '')) CONTAINS toLower($q)
      )
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      {_SALARY_DISP},
      coalesce(j.experience_years, 0.0) AS experience_years
    ORDER BY title ASC, company ASC
    SKIP $skip
    LIMIT $limit
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        total_row = session.run(count_query, {"q": keyword}).single()
        total = int((total_row or {}).get("total") or 0)
        rows = [
            dict(r)
            for r in session.run(
                list_query,
                {"limit": page_size, "skip": skip, "q": keyword},
            )
        ]

    total_pages = max(1, (total + page_size - 1) // page_size)
    return jsonify(
        {
            "ok": True,
            "data": {
                "jobs": rows,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
        }
    )


@jobs_bp.get("/<path:job_id>")
def job_detail(job_id: str):
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    detail_query = f"""
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    OPTIONAL MATCH (j)-[:REQUIRES]->(req)
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      {_SALARY_DISP},
      {_SALARY_RAW},
      coalesce(j.company, '未知公司') AS company,
      coalesce(j.location, '未知地点') AS location,
      coalesce(j.industry, '') AS industry,
      coalesce(j.company_type, '') AS company_type,
      coalesce(j.company_size, '') AS company_size,
      coalesce(j.company_detail, '') AS company_detail,
      coalesce(j.demand, '') AS demand,
      coalesce(j.experience_text, '') AS experience_text,
      coalesce(j.experience_years, 0.0) AS experience_years,
      coalesce(j.internship_req, '') AS internship_req,
      coalesce(j.updated_date, '') AS updated_date,
      coalesce(j.source_url, '') AS source_url,
      coalesce(j.cap_risk_flags, []) AS risk_flags,
      coalesce(j.cap_evidence, []) AS cap_evidence,
      coalesce(j.cap_req_theory, 0.0) AS cap_req_theory,
      coalesce(j.cap_req_cross, 0.0) AS cap_req_cross,
      coalesce(j.cap_req_practice, 0.0) AS cap_req_practice,
      coalesce(j.cap_req_digital, 0.0) AS cap_req_digital,
      coalesce(j.cap_req_innovation, 0.0) AS cap_req_innovation,
      coalesce(j.cap_req_teamwork, 0.0) AS cap_req_teamwork,
      coalesce(j.cap_req_social, 0.0) AS cap_req_social,
      coalesce(j.cap_req_growth, 0.0) AS cap_req_growth,
      coalesce(j.cap_conf_theory, 0.0) AS cap_conf_theory,
      coalesce(j.cap_conf_cross, 0.0) AS cap_conf_cross,
      coalesce(j.cap_conf_practice, 0.0) AS cap_conf_practice,
      coalesce(j.cap_conf_digital, 0.0) AS cap_conf_digital,
      coalesce(j.cap_conf_innovation, 0.0) AS cap_conf_innovation,
      coalesce(j.cap_conf_teamwork, 0.0) AS cap_conf_teamwork,
      coalesce(j.cap_conf_social, 0.0) AS cap_conf_social,
      coalesce(j.cap_conf_growth, 0.0) AS cap_conf_growth,
      collect(DISTINCT {{
        name: coalesce(req.name, ''),
        label: head(labels(req)),
        level: coalesce(req.level, '')
      }}) AS requirements
    LIMIT 1
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        row = session.run(detail_query, {"job_id": job_id}).single()

    if not row:
        return jsonify({"ok": False, "message": "岗位不存在"}), 404

    raw = dict(row)
    detail = serialize_job_row(raw)
    detail.update(
        {
            "industry": raw.get("industry") or "",
            "company_type": raw.get("company_type") or "",
            "company_size": raw.get("company_size") or "",
            "company_detail": raw.get("company_detail") or "",
            "demand": raw.get("demand") or "",
            "experience_text": raw.get("experience_text") or "",
            "experience_years": round(float(raw.get("experience_years") or 0), 2),
            "internship_req": raw.get("internship_req") or "",
            "updated_date": raw.get("updated_date") or "",
            "source_url": raw.get("source_url") or "",
            "cap_evidence": raw.get("cap_evidence") or [],
            "requirements": sorted(
                [
                    {
                        "name": str(item.get("name") or "").strip(),
                        "label": str(item.get("label") or "").strip(),
                        "level": str(item.get("level") or "").strip(),
                    }
                    for item in (raw.get("requirements") or [])
                    if str(item.get("name") or "").strip()
                ],
                key=lambda x: (x["label"], x["name"]),
            ),
        }
    )

    return jsonify({"ok": True, "data": detail})


@jobs_bp.post("/transition-analysis")
def transition_analysis():
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    payload = request.get_json(silent=True) or {}
    from_job_id = str(payload.get("from_job_id") or "").strip()
    to_job_id = str(payload.get("to_job_id") or "").strip()
    if not from_job_id or not to_job_id:
        return jsonify({"ok": False, "message": "from_job_id 和 to_job_id 不能为空"}), 400
    if from_job_id == to_job_id:
        return jsonify({"ok": False, "message": "请至少选择两个不同岗位"}), 400

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        from_row = _fetch_job_for_analysis(session, from_job_id)
        to_row = _fetch_job_for_analysis(session, to_job_id)

    if not from_row or not to_row:
        return jsonify({"ok": False, "message": "岗位不存在"}), 404

    analysis = _build_transition_analysis(from_row, to_row)
    advice = _llm_transition_advice(from_row, to_row, analysis)

    return jsonify(
        {
            "ok": True,
            "data": {
                "from_job": {
                    "id": from_row["id"],
                    "title": from_row["title"],
                    "company": from_row["company"],
                    "location": from_row["location"],
                    "salary": from_row["salary"],
                },
                "to_job": {
                    "id": to_row["id"],
                    "title": to_row["title"],
                    "company": to_row["company"],
                    "location": to_row["location"],
                    "salary": to_row["salary"],
                },
                "analysis": analysis,
                "advice": advice,
            },
        }
    )


@jobs_bp.get("/<path:job_id>/promotion-path")
def get_promotion_path(job_id: str):
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    try:
        max_depth = int(request.args.get("max_depth", "4"))
    except ValueError:
        max_depth = 4
    try:
        max_paths = int(request.args.get("max_paths", "3"))
    except ValueError:
        max_paths = 3

    max_depth = max(1, min(max_depth, 8))
    max_paths = max(1, min(max_paths, 8))
    promotion_limit = max(max_paths, 12)

    start_query = f"""
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.company, '') AS company,
      coalesce(j.location, '') AS location,
      {_SALARY_DISP},
      {_SALARY_RAW},
      coalesce(j.experience_years, 0.0) AS experience_years
    LIMIT 1
    """

    promotion_query = """
    MATCH (start:Job)
    WHERE coalesce(start.job_key, start.job_code, start.name, start.title, elementId(start)) = $job_id
    WITH start, trim(coalesce(start.title, start.name, '')) AS title_name
    OPTIONAL MATCH (start)-[:HAS_TITLE]->(direct_jt:JobTitle)
    OPTIONAL MATCH (fallback_jt:JobTitle {name: title_name})
    WITH title_name, coalesce(direct_jt, fallback_jt) AS jt
    WHERE jt IS NOT NULL
    MATCH (promotion:JobPromotion)-[:FOR_JOB_TITLE]->(jt)
    OPTIONAL MATCH (promotion)-[rr:RECOMMENDS_RESOURCE]->(lr:LearningResource)
    OPTIONAL MATCH (promotion)-[rc:RECOMMENDS_COMPETITION]->(c:Competition)
    RETURN
      coalesce(jt.name, title_name) AS from_title,
      coalesce(promotion.promotion_id, promotion.name, '') AS id,
      coalesce(promotion.stage3_job_title, promotion.stage3, promotion.title, promotion.name, '未命名岗位') AS to_title,
      coalesce(promotion.title, promotion.name, '') AS promotion_name,
      coalesce(promotion.promotion, '') AS promotion,
      coalesce(promotion.stage1, '') AS stage1,
      coalesce(promotion.stage2, '') AS stage2,
      coalesce(promotion.stage3, '') AS stage3,
      coalesce(promotion.stage3_job_title, '') AS stage3_job_title,
      coalesce(promotion.confidence, 0.0) AS confidence,
      coalesce(promotion.rationale, '') AS rationale,
      coalesce(promotion.notes, '') AS notes,
      collect(DISTINCT CASE WHEN lr IS NULL THEN null ELSE {
        resource_id: lr.resource_id,
        resource_name: lr.resource_name,
        resource_desc: lr.resource_desc,
        resource_url: lr.resource_url,
        resource_type: lr.resource_type,
        difficulty: lr.difficulty,
        source: lr.source,
        skill_tag: lr.skill_tag,
        stage: rr.stage,
        stage_role: rr.stage_role,
        rank: rr.rank,
        score: rr.score,
        rationale: rr.rationale
      } END) AS resources,
      collect(DISTINCT CASE WHEN c IS NULL THEN null ELSE {
        competition_id: c.competition_id,
        competition_name: c.competition_name,
        competition_desc: c.competition_desc,
        official_url: c.official_url,
        competition_type: c.competition_type,
        organizer: c.organizer,
        target_audience: c.target_audience,
        team_mode: c.team_mode,
        frequency: c.frequency,
        difficulty: c.difficulty,
        cap_tags: c.cap_tags,
        skill_tags: c.skill_tags,
        award_level: c.award_level,
        stage: rc.stage,
        stage_role: rc.stage_role,
        rank: rc.rank,
        score: rc.score,
        match_via: rc.match_via,
        rationale: rc.rationale
      } END) AS competitions
    ORDER BY confidence DESC, promotion_name ASC, to_title ASC
    LIMIT $limit
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        start_row = session.run(start_query, {"job_id": job_id}).single()
        if not start_row:
            return jsonify({"ok": False, "message": "岗位不存在"}), 404

        promotion_rows = [
            dict(r)
            for r in session.run(
                promotion_query,
                {"job_id": job_id, "limit": promotion_limit},
            )
        ]
        job_title_name = promotion_rows[0]["from_title"] if promotion_rows else str(start_row.get("title") or "")
        title_materials = _fetch_title_materials(session, [job_title_name]).get(
            job_title_name,
            {"learning_resources": [], "competitions": []},
        )

    start_job = dict(start_row)
    normalized_paths = []
    next_steps = []
    routes = []
    fallback_resources = title_materials.get("learning_resources") or []
    fallback_competitions = title_materials.get("competitions") or []

    for item in promotion_rows:
        item["resources"] = [x for x in (item.get("resources") or []) if x]
        item["competitions"] = [x for x in (item.get("competitions") or []) if x]
        route = _build_promotion_route(
            item,
            fallback_resources=fallback_resources,
            fallback_competitions=fallback_competitions,
        )
        routes.append(route)
        confidence = round(_safe_float(item.get("confidence")), 4)
        title = str(route.get("target_title") or item.get("to_title") or "未命名岗位")
        target = {
            "id": f"jobtitle::{title}",
            "title": title,
            "company": "JobTitle",
            "location": "",
            "salary": "",
            "experience_years": 0.0,
            "confidence": confidence,
            "rationale": str(item.get("rationale") or ""),
            "stage1": str(item.get("stage1") or ""),
            "stage2": str(item.get("stage2") or ""),
            "stage3": str(item.get("stage3") or ""),
            "stage3_job_title": str(item.get("stage3_job_title") or ""),
        }
        next_steps.append(target)

        if len(normalized_paths) >= max_paths:
            continue
        path_nodes = [start_job]
        for stage in route.get("stages", []):
            role = str(stage.get("role") or "").strip()
            if not role:
                continue
            if path_nodes and str(path_nodes[-1].get("title") or "") == role:
                continue
            path_nodes.append(
                {
                    "id": f"jobtitle::{role}",
                    "title": role,
                    "company": "JobTitle",
                    "location": "",
                    "salary": "",
                    "experience_years": 0.0,
                }
            )
        normalized_paths.append(
            {
                "hops": max(1, len(path_nodes) - 1),
                "nodes": path_nodes,
                "edges": [
                    {
                        "source": "JobPromotion",
                        "reason": str(route.get("rationale") or item.get("promotion_name") or ""),
                        "confidence": confidence,
                        "stage1": str(item.get("stage1") or ""),
                        "stage2": str(item.get("stage2") or ""),
                        "stage3": str(item.get("stage3") or ""),
                        "stage3_job_title": str(item.get("stage3_job_title") or ""),
                    }
                ],
            }
        )

    return jsonify(
        {
            "ok": True,
            "data": {
                "job": start_job,
                "paths": normalized_paths,
                "next_steps": next_steps,
                "routes": routes[:max_paths],
                "resources": fallback_resources,
                "competitions": fallback_competitions,
                "meta": {
                    "source": "JobPromotion",
                    "job_title": promotion_rows[0]["from_title"] if promotion_rows else start_job.get("title", ""),
                    "max_depth": max_depth,
                    "max_paths": max_paths,
                },
            },
        }
    )


@jobs_bp.get("/<path:job_id>/lateral-paths")
def get_lateral_paths(job_id: str):
    uri, user, password, database = neo4j_settings()
    if not password:
        return jsonify({"ok": False, "message": "缺少 NEO4J_PASSWORD"}), 500

    try:
        max_paths = int(request.args.get("max_paths", "6"))
    except ValueError:
        max_paths = 6
    max_paths = max(1, min(max_paths, 12))

    start_query = f"""
    MATCH (j:Job)
    WHERE coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) = $job_id
    OPTIONAL MATCH (j)-[:HAS_TITLE]->(jt:JobTitle)
    RETURN
      coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)) AS id,
      coalesce(j.title, j.name, '未命名岗位') AS title,
      coalesce(j.company, '') AS company,
      coalesce(j.location, '') AS location,
      {_SALARY_DISP},
      {_SALARY_RAW},
      coalesce(j.experience_years, 0.0) AS experience_years,
      coalesce(jt.name, trim(coalesce(j.title, j.name, ''))) AS job_title
    LIMIT 1
    """

    lateral_query = """
    MATCH (start:Job)
    WHERE coalesce(start.job_key, start.job_code, start.name, start.title, elementId(start)) = $job_id
    WITH start, trim(coalesce(start.title, start.name, '')) AS title_name
    OPTIONAL MATCH (start)-[:HAS_TITLE]->(direct_jt:JobTitle)
    OPTIONAL MATCH (fallback_jt:JobTitle {name: title_name})
    WITH title_name, coalesce(direct_jt, fallback_jt) AS jt
    WHERE jt IS NOT NULL
    MATCH (jt)-[rel:SIMILAR_FOR_LATERAL]->(target:JobTitle)
    RETURN
      coalesce(jt.name, title_name) AS from_title,
      target.name AS target_title,
      coalesce(rel.score, 0.0) AS score,
      coalesce(rel.rank, 999) AS rank,
      coalesce(rel.track_from, '') AS track_from,
      coalesce(rel.track_to, '') AS track_to,
      coalesce(rel.cap_similarity, 0.0) AS cap_similarity,
      coalesce(rel.same_track, false) AS same_track,
      coalesce(rel.promotion_linked, false) AS promotion_linked,
      coalesce(rel.rationale, '') AS rationale
    ORDER BY rank ASC, score DESC, target_title ASC
    LIMIT $limit
    """

    candidate_jobs_query = f"""
    UNWIND $titles AS title
    MATCH (jt:JobTitle {{name: title}})
    CALL (jt) {{
      MATCH (j:Job)-[:HAS_TITLE]->(jt)
      WHERE j.source IS NULL OR trim(toString(j.source)) = ''
      WITH j,
        (coalesce(j.cap_req_theory, 0.0) +
         coalesce(j.cap_req_cross, 0.0) +
         coalesce(j.cap_req_practice, 0.0) +
         coalesce(j.cap_req_digital, 0.0) +
         coalesce(j.cap_req_innovation, 0.0) +
         coalesce(j.cap_req_teamwork, 0.0) +
         coalesce(j.cap_req_social, 0.0) +
         coalesce(j.cap_req_growth, 0.0)) AS total_score
      RETURN collect({{
        id: coalesce(j.job_key, j.job_code, j.name, j.title, elementId(j)),
        title: coalesce(j.title, j.name, '未命名岗位'),
        company: coalesce(j.company, ''),
        location: coalesce(j.location, ''),
        salary: coalesce(j.salary_norm, j.salary, '薪资面议'),
        experience_years: coalesce(j.experience_years, 0.0),
        score_avg: round(total_score / 8.0, 2)
      }})[..3] AS jobs
    }}
    RETURN title, jobs
    """

    driver = neo4j_driver(uri, user, password)
    with driver.session(database=database) as session:
        start_row = session.run(start_query, {"job_id": job_id}).single()
        if not start_row:
            return jsonify({"ok": False, "message": "岗位不存在"}), 404

        lateral_rows = [
            dict(r)
            for r in session.run(
                lateral_query,
                {"job_id": job_id, "limit": max_paths},
            )
        ]
        target_titles = [str(r.get("target_title") or "").strip() for r in lateral_rows]
        materials = _fetch_title_materials(session, target_titles)
        candidate_jobs: Dict[str, List[Dict[str, Any]]] = {}
        if target_titles:
            for row in session.run(candidate_jobs_query, {"titles": target_titles}):
                rec = dict(row)
                candidate_jobs[str(rec.get("title") or "")] = rec.get("jobs") or []

    start_job = dict(start_row)
    job_title_name = str(start_job.pop("job_title", "") or start_job.get("title") or "").strip()
    routes = []
    for item in lateral_rows:
        target_title = str(item.get("target_title") or "").strip()
        block = materials.get(target_title, {"learning_resources": [], "competitions": []})
        resources = block.get("learning_resources") or []
        competitions = block.get("competitions") or []
        jobs = candidate_jobs.get(target_title) or []
        score = round(_safe_float(item.get("score")), 4)
        rationale = str(item.get("rationale") or "").strip()
        routes.append(
            {
                "id": f"{job_title_name}->{target_title}",
                "from_title": job_title_name,
                "target_title": target_title,
                "score": score,
                "rank": _safe_int(item.get("rank"), 999),
                "track_from": str(item.get("track_from") or "").strip(),
                "track_to": str(item.get("track_to") or "").strip(),
                "cap_similarity": round(_safe_float(item.get("cap_similarity")), 4),
                "same_track": bool(item.get("same_track")),
                "promotion_linked": bool(item.get("promotion_linked")),
                "rationale": rationale,
                "candidate_jobs": jobs,
                "learning_resources": resources,
                "competitions": competitions,
                "action_plan": _build_lateral_action_plan(
                    target_title=target_title,
                    score=score,
                    rationale=rationale,
                    resources=resources,
                    competitions=competitions,
                    candidate_jobs=jobs,
                ),
            }
        )

    return jsonify(
        {
            "ok": True,
            "data": {
                "job": start_job,
                "job_title": job_title_name,
                "routes": routes,
                "meta": {
                    "source": "SIMILAR_FOR_LATERAL",
                    "max_paths": max_paths,
                },
            },
        }
    )
