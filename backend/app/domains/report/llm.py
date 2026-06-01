"""报告文案 LLM。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import requests
from flask import current_app
from openai import OpenAI

from app.domains.report.growth import _top_gap_dimensions

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
    client = OpenAI(api_key=api_key.strip(), base_url=base_url.strip(), timeout=timeout)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=max(0.0, min(2.0, float(temperature))),
    )
    return (resp.choices[0].message.content or "").strip()


def _call_qwen_text(*, api_key: str, model: str, user_prompt: str, timeout: float) -> str:
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": user_prompt}]},
        "parameters": {"temperature": 0.3, "result_format": "text"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    data = resp.json()
    return str((data.get("output") or {}).get("text") or "").strip()


def _build_llm_summary(
    *,
    profile: Dict[str, Any],
    target_insights: List[Dict[str, Any]],
    short_term: List[Dict[str, Any]],
    mid_term: List[Dict[str, Any]],
) -> Dict[str, Any]:
    cfg = current_app.config
    provider = str(cfg.get("CAREER_COPYWRITER_PROVIDER") or "doubao").strip().lower()
    timeout = float(cfg.get("CAREER_LLM_TIMEOUT_SECONDS") or 120.0)

    student_name = str(profile.get("display_name") or "候选人")
    brief_targets = [
        {
            "title": t.get("title"),
            "match_score": (t.get("match_preview") or {}).get("match_score"),
            "top_gaps": _top_gap_dimensions((t.get("match_preview") or {}).get("dimension_gaps") or {}, 2),
        }
        for t in target_insights[:5]
    ]
    payload = {
        "student_name": student_name,
        "targets": brief_targets,
        "short_term_focus": [x.get("focus_label") for x in short_term[:3]],
        "mid_term_focus": [x.get("focus_label") for x in mid_term[:3]],
    }
    user_prompt = (
        "请输出 2 段中文总结：\n"
        "1) 职业路径建议（80-120字）\n"
        "2) 执行提醒（80-120字）\n"
        "不要使用 markdown。信息依据如下：\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    system_prompt = "你是职业规划顾问，输出简洁、可执行、具体的中文建议。"

    try:
        if provider == "deepseek":
            api_key = str(cfg.get("DEEPSEEK_API_KEY") or "").strip()
            if not api_key:
                raise RuntimeError("missing DEEPSEEK_API_KEY")
            text = _call_openai_compatible(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                model=str(cfg.get("CAREER_DEEPSEEK_MODEL") or "deepseek-chat"),
                timeout=timeout,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return {"provider": "deepseek", "text": text}
        if provider == "qwen":
            api_key = str(cfg.get("DASHSCOPE_API_KEY") or "").strip()
            if not api_key:
                raise RuntimeError("missing DASHSCOPE_API_KEY")
            text = _call_qwen_text(
                api_key=api_key,
                model=str(cfg.get("CAREER_QWEN_MODEL") or "qwen-plus"),
                user_prompt=user_prompt,
                timeout=timeout,
            )
            return {"provider": "qwen", "text": text}

        # 默认豆包（Ark OpenAI 兼容）
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
            "provider": provider,
            "text": (
                "你当前最优策略是先完成短期关键能力补齐，再把中期任务聚焦到可证明的项目与岗位化实践。"
                "每两周检查能力缺口和任务完成率，确保成长路径持续贴近目标岗位。"
            ),
            "error": str(exc),
        }

