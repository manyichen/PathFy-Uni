"""Read-only planning helpers for graph-derived LLM changes.

This module intentionally contains no Neo4j write path. Reviewed mutations are
applied only by :mod:`app.domains.graph.task_apply`.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from app.domains.graph.services import _build_graph_llm_client, _llm_model
from app.domains.settings.service import setting

PROMOTION_PATH_SYSTEM = """你是职业发展路径专家。请根据输入的岗位名称列表，推断合理的晋升路径。

返回 JSON 对象：
{
  "paths": [{
    "from_title": "初级前端工程师", "to_title": "高级前端工程师",
    "promotion_name": "前端晋升路径", "stage1": "掌握基础",
    "stage2": "独立开发", "stage3": "主导项目",
    "stage3_job_title": "前端架构师", "confidence": 0.85,
    "rationale": "技能递进清晰"
  }]
}

约束：
1. 只使用输入列表中存在的岗位名称。
2. 晋升方向必须体现技能或职级递进。
3. 每条路径给出三个阶段和最终目标岗位。
4. confidence 为 0~1，低于 0.5 的不要输出。
5. 找不到合适路径返回空数组。"""

LATERAL_SYSTEM = """你是职业转岗分析专家。请评估输入岗位之间的横向转岗可行性。

返回 JSON 对象：
{
  "pairs": [{
    "from": "后端开发工程师", "to": "数据分析师", "score": 0.72,
    "track_from": "技术研发", "track_to": "数据科学",
    "cap_similarity": 0.65, "same_track": false,
    "rationale": "编程和逻辑思维有重叠"
  }]
}

约束：
1. score 为 0~1 的综合可行性。
2. track_from/track_to 使用简短中文职业赛道。
3. cap_similarity 表示能力维度重叠度。
4. 只输出 score > 0.4 的有实际可能性的配对。"""


def _strip_json_fence(text: str) -> str:
    value = (text or "").strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", value, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if value.startswith("```"):
        return value.replace("```json", "").replace("```", "").strip()
    return value


def _call_llm_json(system_prompt: str, user_content: str, *, label: str = "") -> dict:
    """Call the configured model during planning, with bounded retries."""
    client = _build_graph_llm_client()
    model = _llm_model()
    retry_count = max(1, int(setting("GRAPH_MAX_RETRIES", 5)))
    timeout = float(setting("GRAPH_LLM_TIMEOUT_SECONDS", 120))
    for attempt in range(1, retry_count + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                timeout=timeout,
            )
            return json.loads(_strip_json_fence((response.choices[0].message.content or "").strip()))
        except Exception as exc:
            if attempt == retry_count:
                raise RuntimeError(f"{label} LLM 调用失败，已重试 {attempt} 次: {exc}") from exc
            time.sleep(min(2 ** (attempt - 1), 8))
    return {}


def _parse_confidence(value: Any) -> float:
    if value is None:
        return 0.0
    is_percent = False
    if isinstance(value, str):
        raw: Any = value.strip()
        if not raw:
            return 0.0
        if raw.endswith("%"):
            is_percent = True
            raw = raw[:-1].strip()
    else:
        raw = value
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if is_percent or number > 1:
        number /= 100.0
    return max(0.0, min(1.0, number))


def _promotion_id(from_title: str, to_title: str) -> str:
    digest = hashlib.sha1(f"{from_title}\0{to_title}".encode("utf-8")).hexdigest()
    return f"promotion_{digest[:16]}"
