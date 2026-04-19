"""
人岗匹配 M2：在粗排候选池上调用 DeepSeek，产出 Top5 精排与中文分析。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

_SYSTEM = """你是就业人岗匹配顾问。输入包含学生八维供给分（0-100）与若干岗位的八维需求分及粗排分数。
你必须只从给定 candidates 的 job_id 中选择并排序，禁止编造不存在的岗位。
输出严格 JSON 对象，且只包含键 top5（数组）。top5 长度必须为 min(5, 候选数量)，按匹配优先顺序排列。
数组元素字段：job_id(string), rank(int 1起), overall_fit_0_100(number 0-100), one_line(string 单行中文≤40字),
strengths(string 数组 2-4 条每条≤45字), gaps(string 数组 2-4 条每条≤45字), risks(string 数组 0-3 条每条≤45字)。
overall_fit_0_100 须与八维差距和学生经历潜力一致；岗位 cap_conf 整体偏低时须在 risks 中提示证据不足。

重要：strengths、gaps 每条必须用纯中文定性描述（如「明显强于岗位期望」「与岗位要求基本匹配」「仍有提升空间」），
禁止写具体分数、禁止「XX分」「（数字分）」、禁止「学生A分对岗位B分」式对比；分数信息仅体现在 overall_fit_0_100 字段即可。
不要输出 Markdown 代码块。"""

_SYSTEM_STRETCH = """你是就业人岗匹配顾问（冲刺高质岗位模式）。输入包含学生八维供给分与若干岗位的八维需求分及粗排分数。
你必须只从给定 candidates 的 job_id 中选择并排序，禁止编造不存在的岗位。
在排序与 overall_fit_0_100 上须体现：优先推荐**岗位八维需求整体较高**、挑战性与成长空间更大、且学生**仍有一定可及性**（非完全脱节）的岗位；可接受略低于「舒适匹配」的综合分，但须在 strengths/gaps 中说明潜力、努力方向或需补强的关键能力。
避免推荐学生明显够不着、各维普遍大幅落后的岗位；若候选整体偏弱，仍选相对更有冲刺价值的岗位并在 risks 中如实说明。
输出严格 JSON 对象，且只包含键 top5（数组）。top5 长度必须为 min(5, 候选数量)，按推荐顺序排列。
数组元素字段：job_id(string), rank(int 1起), overall_fit_0_100(number 0-100), one_line(string 单行中文≤40字),
strengths(string 数组 2-4 条每条≤45字), gaps(string 数组 2-4 条每条≤45字), risks(string 数组 0-3 条每条≤45字)。
岗位 cap_conf 整体偏低时须在 risks 中提示证据不足。

重要：strengths、gaps 每条必须用纯中文定性描述，禁止写具体分数、禁止「XX分」「（数字分）」式对比；分数信息仅体现在 overall_fit_0_100 字段即可。
不要输出 Markdown 代码块。"""


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _slim_student(profile: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": profile.get("id"),
        "display_name": profile.get("display_name"),
        "vector_kind": profile.get("vector_kind"),
        "scores": profile.get("scores") or {},
        "confidences": profile.get("confidences") or {},
    }
    for k in ("education", "city_pref", "skills_hint", "resume_excerpt"):
        if profile.get(k):
            out[k] = profile[k]
    return out


def _slim_job(job: Dict[str, Any]) -> Dict[str, Any]:
    mp = job.get("match_preview") or {}
    return {
        "job_id": job.get("id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "salary": job.get("salary"),
        "job_scores": job.get("scores") or {},
        "job_confidences": job.get("confidences") or {},
        "coarse_match_score": mp.get("match_score"),
        "weighted_gap": mp.get("weighted_gap"),
        "dimension_gaps": mp.get("dimension_gaps") or {},
    }


def _parse_llm_payload(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
    raw = _strip_json_fence(content)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"json_decode_error:{e}"
    if not isinstance(obj, dict):
        return None, "root_not_object"
    return obj, ""


def _normalize_top5_items(
    items: List[Any],
    pool: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """校验 job_id ∈ pool，去重后不足 5 条则按粗排顺序补位。"""
    pool_ids = [str(j.get("id") or "") for j in pool if j.get("id")]
    id_set = set(pool_ids)
    coarse_by_id = {str(j.get("id")): j for j in pool if j.get("id")}

    picked: List[str] = []
    enriched: List[Dict[str, Any]] = []

    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            jid = str(it.get("job_id") or "").strip()
            if not jid or jid not in id_set or jid in picked:
                continue
            picked.append(jid)
            enriched.append(
                {
                    "job_id": jid,
                    "rank": int(it.get("rank") or len(enriched) + 1),
                    "overall_fit_0_100": _clamp_float(it.get("overall_fit_0_100"), 0, 100),
                    "one_line": _str_list_one(it.get("one_line"), 80),
                    "strengths": _clean_qualitative_lines(it.get("strengths"), 4, 50),
                    "gaps": _clean_qualitative_lines(it.get("gaps"), 4, 50),
                    "risks": _clean_str_list(it.get("risks"), 3, 50),
                    "llm_fallback": False,
                }
            )
            if len(enriched) >= 5:
                break

    for jid in pool_ids:
        if len(enriched) >= 5:
            break
        if jid in picked:
            continue
        picked.append(jid)
        j = coarse_by_id.get(jid, {})
        mp = j.get("match_preview") or {}
        enriched.append(
            {
                "job_id": jid,
                "rank": len(enriched) + 1,
                "overall_fit_0_100": round(float(mp.get("match_score") or 0), 1),
                "one_line": "（粗排补位：模型未返回该岗说明）",
                "strengths": [],
                "gaps": [],
                "risks": [],
                "llm_fallback": True,
            }
        )

    for i, row in enumerate(enriched):
        row["rank"] = i + 1
    return enriched[:5]


def _clamp_float(v: Any, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = 0.0
    return round(max(lo, min(hi, x)), 1)


def _str_list_one(v: Any, max_len: int) -> str:
    if isinstance(v, list) and v:
        v = v[0]
    s = str(v or "").strip()
    return s[:max_len]


def _clean_str_list(v: Any, max_items: int, max_each: int) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for x in v:
        s = str(x).strip()
        if s:
            out.append(s[:max_each])
        if len(out) >= max_items:
            break
    return out


# 去掉「(80分)」「（52分）」等括号分数，供 strengths / gaps 后处理（避免误删「10分以上」等）
_SCORE_IN_PARENS = re.compile(r"[（(]\s*\d{1,3}\s*分\s*[)）]")


def _strip_explicit_scores_from_line(text: str) -> str:
    """移除优势/缺口文案中的括号分数对比，保留定性叙述。"""
    t = (text or "").strip()
    if not t:
        return t
    prev = None
    while prev != t:
        prev = t
        t = _SCORE_IN_PARENS.sub("", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"[，,、]\s*[，,、]+", "，", t)
    return t.strip(" ，、").strip()


def _clean_qualitative_lines(v: Any, max_items: int, max_each: int) -> List[str]:
    """与 _clean_str_list 相同，但去掉具体分数后再截断。"""
    raw = _clean_str_list(v, max_items, max_each * 2)
    out: List[str] = []
    for s in raw:
        cleaned = _strip_explicit_scores_from_line(s)
        if cleaned:
            out.append(cleaned[:max_each])
        if len(out) >= max_items:
            break
    return out


def refine_top5_deepseek(
    profile: Dict[str, Any],
    candidate_jobs: List[Dict[str, Any]],
    *,
    api_key: str,
    model: str,
    timeout: float,
    match_goal: str = "fit",
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    调用 DeepSeek，返回 { top5: [...], model, raw_snippet } 或 (None, error_message)。
    candidate_jobs 为粗排后的岗位列表（含 scores / match_preview），建议 5～100 条。
    """
    if not api_key.strip():
        return None, "缺少 DEEPSEEK_API_KEY"

    if not candidate_jobs:
        return None, "候选岗位为空，无法精排"

    pool = candidate_jobs[: min(len(candidate_jobs), 100)]
    want = min(5, len(pool))
    goal = (match_goal or "fit").strip().lower()
    is_stretch = goal == "stretch"
    system_content = _SYSTEM_STRETCH if is_stretch else _SYSTEM

    if is_stretch:
        instr = (
            f"当前为冲刺高质岗位模式。请从 candidates 中选出最有「向上冲刺价值」的 {want} 个岗位（若不足 5 则全选），写入 top5 数组；"
            "优先需求门槛更高、成长空间更大且学生仍有可及性的岗位，并在文案中体现挑战与准备路径。"
            " strengths 与 gaps 中不要写任何具体分数或「X分」，仅用中文定性比较与建议。"
        )
    else:
        instr = (
            f"当前为匹配适合岗位模式。请从 candidates 中选出最合适的 {want} 个岗位（若不足 5 则全选），写入 top5 数组。"
            " strengths 与 gaps 中不要写任何具体分数或「X分」，仅用中文定性比较与建议。"
        )

    user_obj = {
        "match_goal": "stretch" if is_stretch else "fit",
        "instruction": instr,
        "student": _slim_student(profile),
        "candidates": [_slim_job(j) for j in pool],
    }
    user_text = json.dumps(user_obj, ensure_ascii=False)

    client = OpenAI(api_key=api_key.strip(), base_url="https://api.deepseek.com", timeout=timeout)

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.35,
    }
    try:
        resp = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception as first:  # noqa: BLE001
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as second:  # noqa: BLE001
            return None, f"deepseek_http_error:{first!r};retry:{second!r}"

    try:
        content = resp.choices[0].message.content or ""
    except (AttributeError, IndexError) as e:
        return None, f"empty_response:{e}"

    parsed, err = _parse_llm_payload(content)
    if err or not parsed:
        return None, err or "parse_failed"

    raw_items = parsed.get("top5")
    if not isinstance(raw_items, list):
        return None, "missing_top5_array"

    top5 = _normalize_top5_items(raw_items, pool)

    # 附上岗位卡片摘要，便于前端少请求一次
    by_id = {str(j.get("id")): j for j in pool}
    decorated: List[Dict[str, Any]] = []
    for row in top5:
        jid = row["job_id"]
        base = by_id.get(jid, {})
        decorated.append(
            {
                **row,
                "title": base.get("title"),
                "company": base.get("company"),
                "location": base.get("location"),
                "salary": base.get("salary"),
                "scores": base.get("scores") or {},
                "coarse_match_score": (base.get("match_preview") or {}).get("match_score"),
            }
        )

    snippet = content.strip()
    if len(snippet) > 2000:
        snippet = snippet[:2000] + "…"

    return (
        {
            "top5": decorated,
            "model": model,
            "pool_size": len(pool),
            "raw_snippet": snippet,
        },
        "",
    )
