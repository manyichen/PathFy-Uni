"""报告文案 LLM（豆包）与 OpenAI 兼容调用。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from flask import current_app
from openai import OpenAI

from app.domains.report.constants import DIM_LABELS
from app.domains.report.growth import _top_gap_dimensions
from app.domains.report.utils import truthy
from app.infrastructure.llm import strip_json_fence
from app.infrastructure.privacy import llm_privacy_notice, redact_payload


def _call_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    sys_content = system_prompt
    notice = llm_privacy_notice()
    if notice:
        sys_content = f"{sys_content}\n{notice}"
    client = OpenAI(api_key=api_key.strip(), base_url=base_url.strip(), timeout=timeout)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_prompt},
        ],
        temperature=max(0.0, min(2.0, float(temperature))),
    )
    return (resp.choices[0].message.content or "").strip()


def _build_llm_summary(
    *,
    profile: Dict[str, Any],
    target_insights: List[Dict[str, Any]],
    short_term: List[Dict[str, Any]],
    mid_term: List[Dict[str, Any]],
    recommendations: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    cfg = current_app.config
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)

    brief_targets = [
        {
            "title": t.get("title"),
            "match_score": (t.get("match_preview") or {}).get("match_score"),
            "top_gaps": _top_gap_dimensions((t.get("match_preview") or {}).get("dimension_gaps") or {}, 2),
        }
        for t in target_insights[:5]
    ]
    grounded: List[Dict[str, str]] = []
    rec = recommendations or {}
    if rec.get("enabled"):
        for block in (rec.get("by_target") or [])[:3]:
            if not isinstance(block, dict):
                continue
            for lr in (block.get("learning_resources") or [])[:2]:
                grounded.append(
                    {
                        "type": "course",
                        "name": str(lr.get("resource_name") or ""),
                        "id": str(lr.get("resource_id") or ""),
                    }
                )
            for cp in (block.get("competitions") or [])[:1]:
                grounded.append(
                    {
                        "type": "competition",
                        "name": str(cp.get("competition_name") or ""),
                        "id": str(cp.get("competition_id") or ""),
                    }
                )

    payload = {
        "student_name": "候选人",
        "targets": brief_targets,
        "short_term_focus": [x.get("focus_label") for x in short_term[:3]],
        "mid_term_focus": [x.get("focus_label") for x in mid_term[:3]],
        "grounded_resources": grounded,
    }
    user_prompt = (
        "请输出 2 段中文总结：\n"
        "1) 职业路径建议（80-120字）\n"
        "2) 执行提醒（80-120字）\n"
        "不要使用 markdown。必须在文中点名至少 2 个 grounded_resources 中的具体课程或竞赛名称，"
        "不得编造 grounded_resources 列表以外的资源名称。\n"
        "信息依据如下：\n"
        f"{json.dumps(redact_payload(payload), ensure_ascii=False)}"
    )
    system_prompt = (
        "你是职业规划顾问，输出简洁、可执行、具体的中文建议。"
        "推荐内容须基于提供的图谱资源列表。"
    )

    try:
        api_key = str(cfg.get("ARK_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("missing ARK_API_KEY")
        text = _call_openai_compatible(
            api_key=api_key,
            base_url=str(cfg.get("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"),
            model=str(cfg.get("CAREER_ARK_MODEL") or cfg.get("ARK_MODEL") or "doubao-seed-2-0-lite-260215"),
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return {"provider": "doubao", "text": text}
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "doubao",
            "text": (
                "你当前最优策略是先完成短期关键能力补齐，再把中期任务聚焦到可证明的项目与岗位化实践。"
                "每两周检查能力缺口和任务完成率，确保成长路径持续贴近目标岗位。"
            ),
            "error": str(exc),
        }


def augment_plans_narrative_with_doubao(plans_by_target: List[Dict[str, Any]]) -> Dict[str, Any]:
    """为每个目标岗位生成独立叙事（豆包），写入 plans_by_target[].narrative。"""
    if not plans_by_target:
        return {"ok": False, "reason": "empty_plans"}
    cfg = current_app.config
    if not truthy(cfg.get("CAREER_ENABLE_PER_TARGET_COPYWRITER", True)):
        return {"ok": False, "reason": "CAREER_ENABLE_PER_TARGET_COPYWRITER disabled"}
    if not truthy(cfg.get("CAREER_ENABLE_COPYWRITER", True)):
        return {"ok": False, "reason": "CAREER_ENABLE_COPYWRITER disabled"}

    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)
    model = str(cfg.get("CAREER_ARK_MODEL") or cfg.get("ARK_MODEL") or "doubao-seed-2-0-lite-260215")

    brief_plans = []
    for p in plans_by_target[:5]:
        if not isinstance(p, dict):
            continue
        rec = p.get("recommendations") or {}
        lr_names = [
            str(x.get("resource_name") or "")
            for x in (rec.get("learning_resources") or [])[:3]
            if x.get("resource_name")
        ]
        cp_names = [
            str(x.get("competition_name") or "")
            for x in (rec.get("competitions") or [])[:2]
            if x.get("competition_name")
        ]
        phases = p.get("phases") or {}
        brief_plans.append(
            {
                "job_id": p.get("job_id"),
                "display_title": p.get("display_title"),
                "match_score": p.get("match_score"),
                "top_gap_labels": p.get("top_gap_labels")
                or [DIM_LABELS.get(d, d) for d in (p.get("top_gaps") or [])],
                "phase_labels": [
                    (phases.get("early") or {}).get("label"),
                    (phases.get("mid") or {}).get("label"),
                    (phases.get("late") or {}).get("label"),
                ],
                "grounded_resources": lr_names + cp_names,
            }
        )

    payload = {
        "task": "per_target_career_narrative",
        "plans": brief_plans,
        "output_schema": {
            "items": [
                {
                    "job_id": "string",
                    "path_advice": "string 80-120字",
                    "execution_reminder": "string 60-100字",
                }
            ]
        },
        "rules": [
            "每个 job_id 必须输出一条",
            "必须引用该岗位 grounded_resources 中至少 1 个具体名称",
            "禁止编造 grounded_resources 以外的课程或竞赛",
            "只输出 JSON 对象，禁止 markdown",
        ],
    }
    system_prompt = (
        "你是职业规划顾问。请为每个目标岗位分别写路径建议与执行提醒，"
        "语气具体、可执行，彼此区分。"
    )
    user_prompt = json.dumps(redact_payload(payload), ensure_ascii=False)

    try:
        api_key = str(cfg.get("ARK_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("missing ARK_API_KEY")
        text = _call_openai_compatible(
            api_key=api_key,
            base_url=str(cfg.get("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"),
            model=model,
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.35,
        )
        parsed = json.loads(strip_json_fence(text))
        items = parsed.get("items") if isinstance(parsed, dict) else None
        if not isinstance(items, list):
            return {"ok": False, "reason": "llm_items_missing", "provider": "doubao", "model": model}

        by_id = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            jid = str(it.get("job_id") or "").strip()
            if jid:
                by_id[jid] = {
                    "path_advice": str(it.get("path_advice") or "").strip()[:220],
                    "execution_reminder": str(it.get("execution_reminder") or "").strip()[:220],
                }
        updated = 0
        for plan in plans_by_target:
            if not isinstance(plan, dict):
                continue
            jid = str(plan.get("job_id") or "").strip()
            llm_n = by_id.get(jid)
            if not llm_n or not llm_n.get("path_advice"):
                continue
            prev = plan.get("narrative") if isinstance(plan.get("narrative"), dict) else {}
            plan["narrative"] = {
                **prev,
                **llm_n,
                "provider": "doubao",
                "model": model,
                "source": "graph+llm",
            }
            updated += 1
        return {"ok": updated > 0, "updated": updated, "provider": "doubao", "model": model}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc), "provider": "doubao", "model": model}
