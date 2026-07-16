"""Eight-dimension job capability evaluation used by graph queue planners."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from openai import OpenAI

from app.core.config import Config
from app.domains.graph import capability_cache
from app.domains.graph.sync_service import _call_llm_json
from app.domains.settings.service import setting

DIMENSIONS = ("theory", "cross", "practice", "digital", "innovation", "teamwork", "social", "growth")
REQ_FIELDS = tuple(f"cap_req_{name}" for name in DIMENSIONS)
CONF_FIELDS = tuple(f"cap_conf_{name}" for name in DIMENSIONS)
CAP_METADATA_FIELDS = (
    "cap_evidence", "cap_risk_flags", "cap_version", "cap_input_fingerprint", "cap_fusion",
    "cap_primary_provider", "cap_primary_model", "cap_review_provider", "cap_review_model",
    "cap_prompt_version", "cap_llm_duration_ms", "cap_llm_tokens", "cap_llm_retries",
    "cap_llm_request_ids", "cap_cache_hit",
)
CAP_RESTORE_FIELDS = (*REQ_FIELDS, *CONF_FIELDS, *CAP_METADATA_FIELDS)
CAP_VERSION = Config.GRAPH_CAP_VERSION
PROMPT_VERSION = "job-capability-prompt-v1"

SYSTEM = """你是招聘岗位八维能力要求评估器。根据岗位名称、岗位描述、技能、证书、经验和图谱上下文评估：
theory 理论、cross 交叉、practice 实践、digital 数字、innovation 创新、teamwork 协作、social 社会连接、growth 成长。
批量输入时严格返回 {\"records\":[{\"job_key\":输入岗位标识,\"scores\":{八个维度:0到100},\"confidence\":{八个维度:0到1},\"evidence\":[简短证据],\"risk_flags\":[风险]}]}。
单个输入也可以返回同样的 records 格式。
证据不足必须降低置信度，不得编造输入中不存在的信息。"""


def capability_fingerprint(payload: dict[str, Any]) -> str:
    fingerprint_fields = ("job_key", "title", "company", "industry", "demand", "company_detail", "hard_skills", "certificates", "experience")
    stable_payload = {key: payload.get(key) for key in fingerprint_fields}
    for key in ("hard_skills", "certificates"):
        stable_payload[key] = sorted({str(value).strip() for value in (stable_payload.get(key) or []) if str(value).strip()})
    encoded = json.dumps({"version": setting("GRAPH_CAP_VERSION", "job-cap-v2"), "payload": stable_payload}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
    normalized["cap_version"] = str(raw.get("cap_version") or setting("GRAPH_CAP_VERSION", "job-cap-v2"))
    return normalized


def needs_review(result: dict[str, Any]) -> bool:
    return min(float(result[field]) for field in CONF_FIELDS) < float(setting("GRAPH_CAP_REVIEW_CONFIDENCE_THRESHOLD", 0.6))


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
        return (str(setting("DEEPSEEK_API_KEY", "")), str(setting("GRAPH_CAP_PRIMARY_BASE_URL", "https://api.deepseek.com")), str(setting("GRAPH_CAP_PRIMARY_MODEL", "deepseek-v4-flash")), {})
    if provider == "qwen":
        return (str(setting("DASHSCOPE_API_KEY", "")), str(setting("GRAPH_CAP_REVIEW_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")), str(setting("GRAPH_CAP_REVIEW_MODEL", "qwen3.6-plus")), {"enable_thinking": False})
    raise RuntimeError(f"不支持的岗位能力评估 Provider: {provider}")


def _provider_model(provider: str) -> str:
    if provider == "graph":
        return str(setting("GRAPH_LLM_MODEL", "doubao-seed-2-0-mini-260215"))
    return _provider_settings(provider)[2]


def _call_provider(
    provider: str, payload: dict[str, Any], *, label: str,
    task_id: int | None = None, stage: str = "capability",
) -> dict[str, Any]:
    started = time.perf_counter()
    if provider == "graph":
        result = _call_llm_json(SYSTEM, json.dumps(payload, ensure_ascii=False), label=label)
        duration_ms = round((time.perf_counter() - started) * 1000)
        result["_cap_call_meta"] = {"provider": provider, "model": _provider_model(provider),
                                   "duration_ms": duration_ms, "retry_count": 0,
                                   "request_id": None, "prompt_tokens": 0, "completion_tokens": 0}
        capability_cache.record_metric(task_id=task_id, stage=stage, **result["_cap_call_meta"])
        return result
    api_key, base_url, model, extra_body = _provider_settings(provider)
    if not api_key: raise RuntimeError(f"{label}缺少 {provider} API Key")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=float(setting("GRAPH_CAP_LLM_TIMEOUT_SECONDS", 180)))
    last_error: Exception | None = None
    max_retries = max(1, int(setting("GRAPH_CAP_MAX_RETRIES", 3)))
    for attempt in range(max_retries):
        try:
            kwargs: dict[str, Any] = {"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], "temperature": 0.2, "response_format": {"type": "json_object"}}
            if extra_body: kwargs["extra_body"] = extra_body
            response = client.chat.completions.create(**kwargs)
            raw = (response.choices[0].message.content or "").strip()
            if raw.startswith("```"): raw = raw.strip("`").removeprefix("json").strip()
            result = json.loads(raw)
            if not isinstance(result, dict): raise ValueError("模型返回顶层不是对象")
            usage = getattr(response, "usage", None)
            metadata = {
                "provider": provider,
                "model": model,
                "request_id": str(getattr(response, "id", "") or "") or None,
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "retry_count": attempt,
            }
            result["_cap_call_meta"] = metadata
            capability_cache.record_metric(task_id=task_id, stage=stage, **metadata)
            return result
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max_retries: time.sleep(min(2 ** attempt, 4))
    capability_cache.record_metric(
        task_id=task_id, stage=stage, provider=provider, model=model,
        duration_ms=round((time.perf_counter() - started) * 1000),
        retry_count=max_retries - 1, error_code=type(last_error).__name__ if last_error else "unknown",
    )
    raise RuntimeError(f"{label}失败: {last_error}") from last_error


def _records_by_key(raw: dict[str, Any], payloads: list[dict[str, Any]], *, label: str, require_all: bool = True) -> dict[str, dict[str, Any]]:
    records = raw.get("records")
    if not isinstance(records, list):
        records = [raw] if len(payloads) == 1 else []
    expected = [str(payload.get("job_key") or "") for payload in payloads]
    output: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict): continue
        key = str(record.get("job_key") or record.get("job_id") or (expected[index] if index < len(expected) else ""))
        if key in expected and key not in output: output[key] = record
    missing = [key for key in expected if key not in output]
    if missing and require_all: raise ValueError(f"{label}缺少岗位结果: {missing[:5]}")
    return output


def _merge_call_meta(target: dict[str, Any], source: dict[str, Any]) -> None:
    if not target:
        target.update(source)
        target["request_ids"] = [source.get("request_id")] if source.get("request_id") else []
        return
    for key in ("duration_ms", "prompt_tokens", "completion_tokens", "retry_count"):
        target[key] = int(target.get(key) or 0) + int(source.get(key) or 0)
    if source.get("request_id"):
        target.setdefault("request_ids", []).append(source["request_id"])


def _complete_provider_records(
    provider: str, payloads: list[dict[str, Any]], *, label: str, task_id: int | None,
    stage: str, review_assessments: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Retry only records omitted from an otherwise valid batch response."""
    remaining = list(payloads)
    records: dict[str, dict[str, Any]] = {}
    metadata: dict[str, Any] = {}
    max_rounds = max(1, int(setting("GRAPH_CAP_MAX_RETRIES", 3)))
    for _round in range(max_rounds):
        if review_assessments is None:
            request_payload = {"jobs": remaining, "task": "逐个返回完整八维评分与置信度"}
        else:
            request_payload = {
                "records": [{"job": payload, "primary_assessment": review_assessments[str(payload.get("job_key"))]} for payload in remaining],
                "task": "复核低置信度结果并逐个返回完整八维结果",
            }
        raw = _call_provider(provider, request_payload, label=label, task_id=task_id, stage=stage)
        _merge_call_meta(metadata, dict(raw.pop("_cap_call_meta", {}) or {}))
        records.update(_records_by_key(raw, remaining, label=label, require_all=False))
        remaining = [payload for payload in remaining if str(payload.get("job_key")) not in records]
        if not remaining:
            return records, metadata
    raise ValueError(f"{label}缺少岗位结果: {[str(item.get('job_key')) for item in remaining[:5]]}")


def _cache_identity() -> tuple[str, str, str]:
    primary = str(setting("GRAPH_CAP_PRIMARY_PROVIDER", "deepseek")).lower()
    review = str(setting("GRAPH_CAP_REVIEW_PROVIDER", "qwen")).lower()
    return f"{primary}+{review}", f"{_provider_model(primary)}+{_provider_model(review)}", str(setting("GRAPH_CAP_VERSION", "job-cap-v2"))


def _cache_prompt_version() -> str:
    threshold = float(setting("GRAPH_CAP_REVIEW_CONFIDENCE_THRESHOLD", 0.6))
    return f"{PROMPT_VERSION}:review={threshold:.4f}:fusion=0.4/0.6"


def evaluate_jobs(payloads: list[dict[str, Any]], *, task_id: int | None = None) -> list[dict[str, Any]]:
    if not payloads:
        return []
    cache_provider, cache_model, cap_version = _cache_identity()
    prompt_version = _cache_prompt_version()
    fingerprints = {str(payload.get("job_key")): capability_fingerprint(payload) for payload in payloads}
    output_by_key: dict[str, dict[str, Any]] = {}
    missing_payloads: list[dict[str, Any]] = []
    for payload in payloads:
        key = str(payload.get("job_key"))
        cached = capability_cache.load(
            fingerprints[key], cap_version=cap_version, provider=cache_provider,
            model=cache_model, prompt_version=prompt_version,
        )
        if cached:
            cached["cap_cache_hit"] = True
            output_by_key[key] = cached
            capability_cache.record_metric(
                task_id=task_id, stage="capability_cache", provider=cache_provider,
                model=cache_model, cache_hit=True,
            )
        else:
            missing_payloads.append(payload)
    if not missing_payloads:
        return [output_by_key[str(payload.get("job_key"))] for payload in payloads]

    primary_provider = str(setting("GRAPH_CAP_PRIMARY_PROVIDER", "deepseek")).lower()
    primary_records, primary_meta = _complete_provider_records(
        primary_provider, missing_payloads, label="批量初评", task_id=task_id,
        stage="capability_primary",
    )
    normalized = {key: _normalize(value) for key, value in primary_records.items()}
    review_payloads = [{"job": payload, "primary_assessment": normalized[str(payload.get("job_key"))]} for payload in missing_payloads if needs_review(normalized[str(payload.get("job_key"))])]
    reviews: dict[str, dict[str, Any]] = {}
    review_meta: dict[str, Any] = {}
    if review_payloads:
        review_provider = str(setting("GRAPH_CAP_REVIEW_PROVIDER", "qwen")).lower()
        review_jobs = [item["job"] for item in review_payloads]
        review_records, review_meta = _complete_provider_records(
            review_provider, review_jobs, label="批量复核", task_id=task_id,
            stage="capability_review", review_assessments=normalized,
        )
        reviews = {key: _normalize(value) for key, value in review_records.items()}
    for payload in missing_payloads:
        key = str(payload.get("job_key")); result = normalized[key]
        if key in reviews: result = merge_results(result, reviews[key])
        else: result["cap_fusion"] = "primary_only"
        result.update({
            "cap_input_fingerprint": fingerprints[key],
            "cap_primary_provider": primary_meta.get("provider", primary_provider),
            "cap_primary_model": primary_meta.get("model", _provider_model(primary_provider)),
            "cap_review_provider": review_meta.get("provider") if key in reviews else None,
            "cap_review_model": review_meta.get("model") if key in reviews else None,
            "cap_prompt_version": prompt_version,
            "cap_llm_duration_ms": int(primary_meta.get("duration_ms") or 0) + (int(review_meta.get("duration_ms") or 0) if key in reviews else 0),
            "cap_llm_tokens": int(primary_meta.get("prompt_tokens") or 0) + int(primary_meta.get("completion_tokens") or 0)
                + (int(review_meta.get("prompt_tokens") or 0) + int(review_meta.get("completion_tokens") or 0) if key in reviews else 0),
            "cap_llm_retries": int(primary_meta.get("retry_count") or 0) + (int(review_meta.get("retry_count") or 0) if key in reviews else 0),
            "cap_llm_request_ids": [*primary_meta.get("request_ids", []), *(review_meta.get("request_ids", []) if key in reviews else [])],
            "cap_cache_hit": False,
        })
        capability_cache.store(
            fingerprints[key], result,
            {"primary": primary_meta, "review": review_meta if key in reviews else None},
            cap_version=cap_version, provider=cache_provider, model=cache_model,
            prompt_version=prompt_version,
        )
        output_by_key[key] = result
    return [output_by_key[str(payload.get("job_key"))] for payload in payloads]


def evaluate_job(payload: dict[str, Any]) -> dict[str, Any]:
    return evaluate_jobs([payload])[0]


def normalize_imported_result(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize(raw)
    normalized["cap_input_fingerprint"] = str(raw.get("cap_input_fingerprint") or "historical-import")
    normalized["cap_fusion"] = str(raw.get("cap_fusion") or raw.get("fusion") or "historical-import")
    return normalized
