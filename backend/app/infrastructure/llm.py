"""LLM 通用工具：Markdown JSON 围栏剥离、Ark/OpenAI 兼容客户端与 JSON 调用。"""

from __future__ import annotations

import json
import re
from typing import Any

from flask import current_app
from openai import OpenAI

from app.infrastructure.privacy import llm_privacy_notice, privacy_mode_enabled, redact_payload


def strip_json_fence(text: str) -> str:
    """从模型输出中剥离 ```json ... ``` 围栏，返回可 parse 的 JSON 字符串。"""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if t.startswith("```"):
        return t.replace("```json", "").replace("```", "").strip()
    return t


def build_ark_openai_client(*, required: bool = False) -> OpenAI | None:
    """构建豆包/Ark OpenAI 兼容客户端；未配置 key 时 required=False 返回 None。"""
    api_key = str(current_app.config.get("ARK_API_KEY") or "").strip()
    if not api_key:
        if required:
            raise RuntimeError("未配置 ARK_API_KEY")
        return None
    timeout = int(current_app.config.get("AI_LLM_TIMEOUT_SECONDS", 90))
    base_url = str(current_app.config.get("ARK_BASE_URL", "")).strip()
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def call_ark_json(
    system_prompt: str,
    payload: dict[str, Any],
    *,
    temperature: float = 0.2,
    required: bool = False,
) -> dict[str, Any] | None:
    """
    调用 Ark 模型并解析 JSON 对象响应。
    required=False 时缺 key 或解析失败返回 None；required=True 时抛出 RuntimeError。
    """
    client = build_ark_openai_client(required=required)
    if client is None:
        return None

    model = current_app.config.get("ARK_MODEL", "doubao-seed-2-0-mini-260215")
    sys_content = system_prompt
    notice = llm_privacy_notice()
    if notice:
        sys_content = f"{sys_content}\n{notice}"
    safe_payload = redact_payload(payload) if privacy_mode_enabled() else payload
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_content},
                {"role": "user", "content": json.dumps(safe_payload, ensure_ascii=False)},
            ],
            temperature=temperature,
            stream=False,
            response_format={"type": "json_object"},
        )
        content = strip_json_fence((resp.choices[0].message.content or "").strip())
        data = json.loads(content)
    except Exception as exc:
        if required:
            raise RuntimeError(f"模型 JSON 调用失败: {exc}") from exc
        return None

    if not isinstance(data, dict):
        if required:
            raise RuntimeError("模型返回结构不合法")
        return None
    return data
