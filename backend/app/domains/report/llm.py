"""报告文案 LLM（豆包）与 OpenAI 兼容调用。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from flask import current_app
from openai import OpenAI

from app.domains.report.growth import _top_gap_dimensions
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
    payload = {
        "student_name": "候选人",
        "targets": brief_targets,
        "short_term_focus": [x.get("focus_label") for x in short_term[:3]],
        "mid_term_focus": [x.get("focus_label") for x in mid_term[:3]],
    }
    user_prompt = (
        "请输出 2 段中文总结：\n"
        "1) 职业路径建议（80-120字）\n"
        "2) 执行提醒（80-120字）\n"
        "不要使用 markdown。信息依据如下：\n"
        f"{json.dumps(redact_payload(payload), ensure_ascii=False)}"
    )
    system_prompt = "你是职业规划顾问，输出简洁、可执行、具体的中文建议。"

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
