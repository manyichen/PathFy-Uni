"""Eight-dimension job capability evaluation used by graph queue planners."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from openai import OpenAI

from app.domains.graph.sync_service import _call_llm_json

DIMENSIONS = ("theory", "cross", "practice", "digital", "innovation", "teamwork", "social", "growth")
REQ_FIELDS = tuple(f"cap_req_{name}" for name in DIMENSIONS)
CONF_FIELDS = tuple(f"cap_conf_{name}" for name in DIMENSIONS)
CAP_VERSION = os.getenv("GRAPH_CAP_VERSION", "job-cap-v2")
REVIEW_THRESHOLD = float(os.getenv("GRAPH_CAP_REVIEW_CONFIDENCE_THRESHOLD", "0.60"))
PRIMARY_PROVIDER = os.getenv("GRAPH_CAP_PRIMARY_PROVIDER", "deepseek").strip().lower()
REVIEW_PROVIDER = os.getenv("GRAPH_CAP_REVIEW_PROVIDER", "qwen").strip().lower()
MAX_RETRIES = max(1, int(os.getenv("GRAPH_CAP_MAX_RETRIES", "3")))

SYSTEM = """你是招聘岗位八维能力要求评估器。根据岗位名称、岗位描述、技能、证书、经验和图谱上下文评估：
theory 理论、cross 交叉、practice 实践、digital 数字、innovation 创新、teamwork 协作、social 社会连接、growth 成长。
严格返回 JSON：{\"scores\":{八个维度:0到100},\"confidence\":{八个维度:0到1},\"evidence\":[简短证据],\"risk_flags\":[风险]}。
证据不足必须降低置信度，不得编造输入中不存在的信息。"""


def capability_fingerprint(payload: dict[str, Any]) -> str:
    fingerprint_fields = ("job_key", "title", "company", "industry", "demand", "company_detail", "hard_skills", "certificates", "experience")
    stable_payload = {key: payload.get(key) for key in fingerprint_fields}
    for key in ("hard_skills", "certificates"):
        stable_payload[key] = sorted({str(value).strip() for value in (stable_payload.get(key) or []) if str(value).strip()})
    encoded = json.dumps({"version": CAP_VERSION, "payload": stable_payload}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    confidence = raw.get("confidence") if isinstance(raw.get("confidence"), dict) else {}
    normalized: dict[str, Any] = {}
    for dim in DIMENSIONS:
        score = scores.get(dim, scores.get(f"cap_req_{dim}", raw.get(f"cap_req_{dim}")))
        conf = confidence.get(dim, confidence.get(f"cap_conf_{dim}", raw.get(f"cap_conf_{dim}")))
        try:
            normalized[f"cap_req_{dim}"] = round(max(0.0, min(100.0, float(score))), 2)
            normalized[f"cap_conf_{dim}"] = round(max(0.0, min(1.0, float(conf))), 4)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"能力评估缺少合法维度: {dim}") from exc
    normalized["cap_evidence"] = [str(x)[:500] for x in (raw.get("evidence") or []) if str(x).strip()][:8]
    normalized["cap_risk_flags"] = sorted({str(x)[:200] for x in (raw.get("risk_flags") or []) if str(x).strip()})
    normalized["cap_version"] = str(raw.get("cap_version") or CAP_VERSION)
    return normalized


def needs_review(result: dict[str, Any]) -> bool:
    return min(float(result[field]) for field in CONF_FIELDS) < REVIEW_THRESHOLD


def merge_results(primary: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    for field in REQ_FIELDS:
        merged[field] = round(0.4 * float(primary[field]) + 0.6 * float(review[field]), 2)
    for field in CONF_FIELDS:
        merged[field] = round(0.4 * float(primary[field]) + 0.6 * float(review[field]), 4)
    merged["cap_evidence"] = review.get("cap_evidence") or primary.get("cap_evidence") or []
    merged["cap_risk_flags"] = sorted(set(primary.get("cap_risk_flags", [])) | set(review.get("cap_risk_flags", [])))
    merged["cap_fusion"] = "0.4_primary_0.6_review"
    return merged


def _provider_settings(provider: str) -> tuple[str, str, str, dict[str, Any]]:
    if provider == "deepseek":
        return (os.getenv("DEEPSEEK_API_KEY", ""), os.getenv("GRAPH_CAP_PRIMARY_BASE_URL", "https://api.deepseek.com"), os.getenv("GRAPH_CAP_PRIMARY_MODEL", "deepseek-chat"), {})
    if provider == "qwen":
        return (os.getenv("DASHSCOPE_API_KEY", ""), os.getenv("GRAPH_CAP_REVIEW_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"), os.getenv("GRAPH_CAP_REVIEW_MODEL", "qwen3.6-plus"), {"enable_thinking": False})
    raise RuntimeError(f"不支持的岗位能力评估 Provider: {provider}")


def _call_provider(provider: str, payload: dict[str, Any], *, label: str) -> dict[str, Any]:
    if provider == "graph":
        return _call_llm_json(SYSTEM, json.dumps(payload, ensure_ascii=False), label=label)
    api_key, base_url, model, extra_body = _provider_settings(provider)
    if not api_key: raise RuntimeError(f"{label}缺少 {provider} API Key")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=float(os.getenv("GRAPH_CAP_LLM_TIMEOUT_SECONDS", "180")))
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            kwargs: dict[str, Any] = {"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], "temperature": 0.2, "response_format": {"type": "json_object"}}
            if extra_body: kwargs["extra_body"] = extra_body
            response = client.chat.completions.create(**kwargs)
            raw = (response.choices[0].message.content or "").strip()
            if raw.startswith("```"): raw = raw.strip("`").removeprefix("json").strip()
            result = json.loads(raw)
            if not isinstance(result, dict): raise ValueError("模型返回顶层不是对象")
            return result
        except Exception as exc:
            last_error = exc
            if attempt + 1 < MAX_RETRIES: time.sleep(min(2 ** attempt, 4))
    raise RuntimeError(f"{label}失败: {last_error}") from last_error


def evaluate_job(payload: dict[str, Any]) -> dict[str, Any]:
    primary = _normalize(_call_provider(PRIMARY_PROVIDER, payload, label="岗位八维能力初评"))
    if needs_review(primary):
        review_input = {"job": payload, "primary_result": primary, "task": "复核低置信度维度并返回完整八维结果"}
        review = _normalize(_call_provider(REVIEW_PROVIDER, review_input, label="岗位八维能力复核"))
        primary = merge_results(primary, review)
    else:
        primary["cap_fusion"] = "primary_only"
    primary["cap_input_fingerprint"] = capability_fingerprint(payload)
    return primary


def normalize_imported_result(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize(raw)
    normalized["cap_input_fingerprint"] = str(raw.get("cap_input_fingerprint") or "historical-import")
    normalized["cap_fusion"] = str(raw.get("cap_fusion") or raw.get("fusion") or "historical-import")
    return normalized
