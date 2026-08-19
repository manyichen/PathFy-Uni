"""报告文案 LLM（豆包）与 OpenAI 兼容调用。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from flask import current_app
from app.domains.settings.service import settings_view
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
    cfg = settings_view(base=current_app.config)
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

    target_lines = []
    for target in brief_targets[:3]:
        gap_text = "、".join(str(value) for value in target.get("top_gaps") or []) or "关键能力"
        target_lines.append(f"{target.get('title') or '目标岗位'}（匹配 {target.get('match_score') or '待补充'}）：优先补齐 {gap_text}")
    resource_names = [value["name"] for value in grounded if value.get("name")][:3]
    resource_clause = f"可使用已核验资源：{'、'.join(resource_names)}。" if resource_names else "资源名称不足时不追加未经核验的推荐。"
    return {
        "provider": "grounded-template",
        "text": (
            "；".join(target_lines)
            + "。本月计划以可查看的交付物、明确截止时间和验收标准为准。\n"
            + resource_clause
            + "月末仅根据完成记录、作品、证书或反馈调整下一轮计划。"
        ),
        "source": "profile+job+graph",
    }


def augment_plans_narrative_with_doubao(plans_by_target: List[Dict[str, Any]]) -> Dict[str, Any]:
    """为每个目标岗位生成独立叙事（豆包），写入 plans_by_target[].narrative。"""
    if not plans_by_target:
        return {"ok": False, "reason": "empty_plans"}
    cfg = settings_view(base=current_app.config)
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


def build_grounded_report_narratives(
    plans_by_target: List[Dict[str, Any]],
    target_insights: List[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Build evidence-dense copy from verified report fields without another model round trip."""
    insight_by_id = {
        str(value.get("id") or value.get("job_id") or ""): value
        for value in target_insights
        if isinstance(value, dict)
    }
    summaries: List[str] = []
    updated = 0
    for plan in plans_by_target:
        if not isinstance(plan, dict):
            continue
        job_id = str(plan.get("job_id") or "")
        insight = insight_by_id.get(job_id) or {}
        title = str(plan.get("display_title") or insight.get("title") or "目标岗位")
        score = (insight.get("match_preview") or {}).get("match_score") or plan.get("match_score")
        gap_labels = [str(value) for value in plan.get("top_gap_labels") or [] if str(value)][:2]
        nmp = plan.get("next_month_plan") if isinstance(plan.get("next_month_plan"), dict) else {}
        actions = [
            action
            for item in nmp.get("items") or [] if isinstance(item, dict)
            for action in item.get("custom_actions") or [] if isinstance(action, dict) and action.get("text")
        ]
        resources = [
            str(value.get("resource_name") or value.get("competition_name") or "")
            for value in ((plan.get("recommendations") or {}).get("learning_resources") or [])[:2]
            if isinstance(value, dict)
        ]
        gap_text = "、".join(gap_labels) or "关键岗位能力"
        first_action = str((actions[0] if actions else {}).get("text") or "完成首项可验收任务")
        deliverable = str((actions[0] if actions else {}).get("deliverable") or first_action)
        resource_text = "、".join(value for value in resources if value)
        plan["narrative"] = {
            **(plan.get("narrative") if isinstance(plan.get("narrative"), dict) else {}),
            "path_advice": (
                f"{title}当前匹配度为{score if score is not None else '待补充'}，优先收敛{gap_text}。"
                f"本月先执行“{first_action}”，形成“{deliverable}”作为可核验证据"
                + (f"，并结合{resource_text}补齐知识输入。" if resource_text else "。")
            ),
            "execution_reminder": "每周只检查行动是否交付、证据是否可查看；月末依据完成率和复盘结果调整下月任务，不以泛化自评替代成果。",
            "provider": "grounded-template",
            "source": "profile+job+graph+plan",
        }
        summaries.append(f"{title}：重点补齐{gap_text}，首要交付为{deliverable}")
        updated += 1
    summary_text = "；".join(summaries[:3])
    narrative = {
        "provider": "grounded-template",
        "text": (
            f"本报告按岗位缺口、图谱资源和可验收行动组织，而不是泛化职业建议。{summary_text}。\n"
            "执行时保留作品、证书、反馈或活动记录；每月复盘只用已确认数据更新计划，信息不足处维持待验证状态。"
        ),
    }
    return narrative, {"ok": updated > 0, "updated": updated, "provider": "grounded-template"}
