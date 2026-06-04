"""LLM 外发与本地存储的统一脱敏工具。"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from flask import current_app, has_app_context

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CN_MOBILE_RE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
_CN_ID_RE = re.compile(
    r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])"
    r"(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
)
_BANK_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)")
_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_QQ_WECHAT_RE = re.compile(
    r"(?i)\b(?:qq|wechat|weixin)\s*[:=]\s*[A-Za-z0-9_-]{5,32}\b"
)
_CN_CONTACT_LABEL_RE = re.compile(
    r"(\u5fae\u4fe1|\u5fae\s*\u4fe1|QQ|\u90ae\u7bb1|\u7535\u8bdd|"
    r"\u624b\u673a|\u8054\u7cfb\u65b9\u5f0f|\u8eab\u4efd\u8bc1\u53f7|"
    r"\u8bc1\u4ef6\u53f7)\s*[:\uff1a=]\s*([^\s,\uff0c;\uff1b]{3,64})"
)
_TOKEN_QUERY_RE = re.compile(
    r"(?i)([?&](?:token|access_token|refresh_token|key|secret|code|session)=)[^&#\s]+"
)

_SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
)
_PRIVATE_ID_KEYS = {
    "user_id",
    "resume_id",
    "student_id",
    "profile_id",
    "account_id",
    "session_id",
    "message_id",
}
_REFERENCE_ID_KEYS = {"job_id", "job_ids", "target_job_ids"}
_NAME_KEYS = {"display_name", "student_name", "real_name", "username", "full_name"}
_DROP_TEXT_KEYS = {"resume_text", "resume_excerpt"}
_RAW_STORAGE_FLAGS = {
    "resume": "LOCAL_STORE_RAW_RESUME_TEXT",
    "review": "LOCAL_STORE_RAW_REVIEW_TEXT",
    "chat": "LOCAL_STORE_RAW_CHAT_MESSAGES",
}


def _cfg(name: str, default: Any) -> Any:
    if has_app_context():
        return current_app.config.get(name, default)
    return default


def _cfg_bool(name: str, default: bool) -> bool:
    value = _cfg(name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(_cfg(name, default))
    except (TypeError, ValueError):
        return default


def privacy_mode_enabled() -> bool:
    return _cfg_bool("LLM_PRIVACY_MODE", True)


def should_store_raw_llm() -> bool:
    return _cfg_bool("LLM_STORE_RAW_SNIPPETS", False)


def should_store_raw_user_text(kind: str) -> bool:
    flag = _RAW_STORAGE_FLAGS.get(str(kind or "").strip().lower())
    if not flag:
        return False
    return _cfg_bool(flag, False)


def redact_text(text: Any, *, max_chars: int | None = None) -> str:
    value = str(text or "")
    if not privacy_mode_enabled():
        return value[:max_chars] if max_chars else value

    value = _TOKEN_QUERY_RE.sub(r"\1[REDACTED_TOKEN]", value)
    value = _URL_RE.sub("[REDACTED_URL]", value)
    value = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    value = _CN_ID_RE.sub("[REDACTED_ID_CARD]", value)
    value = _CN_MOBILE_RE.sub("[REDACTED_PHONE]", value)
    value = _BANK_CARD_RE.sub("[REDACTED_BANK_CARD]", value)
    value = _QQ_WECHAT_RE.sub("[REDACTED_CONTACT]", value)
    value = _CN_CONTACT_LABEL_RE.sub(r"\1:[REDACTED]", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    if max_chars is not None and max_chars > 0 and len(value) > max_chars:
        return value[:max_chars] + "\n[TRUNCATED_FOR_PRIVACY]"
    return value


def redact_payload(obj: Any, *, max_string_chars: int | None = None) -> Any:
    if max_string_chars is None:
        max_string_chars = _cfg_int("LLM_MAX_FIELD_CHARS", 1200)

    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, value in obj.items():
            key_s = str(key)
            key_l = key_s.lower()
            if any(part in key_l for part in _SECRET_KEY_PARTS):
                out[key_s] = "[REDACTED_SECRET]"
                continue
            if key_l in _PRIVATE_ID_KEYS:
                continue
            if key_l in _REFERENCE_ID_KEYS:
                out[key_s] = value
                continue
            if key_l in _DROP_TEXT_KEYS:
                continue
            if key_l in _NAME_KEYS:
                out[key_s] = "[REDACTED_NAME]"
                continue
            out[key_s] = redact_payload(value, max_string_chars=max_string_chars)
        return out
    if isinstance(obj, list):
        return [redact_payload(item, max_string_chars=max_string_chars) for item in obj]
    if isinstance(obj, tuple):
        return [redact_payload(item, max_string_chars=max_string_chars) for item in obj]
    if isinstance(obj, str):
        return redact_text(obj, max_chars=max_string_chars)
    return obj


def storage_safe_text(text: Any, *, kind: str, max_chars: int | None = None) -> str:
    if max_chars is None:
        max_chars = _cfg_int("LOCAL_MAX_STORED_TEXT_CHARS", 4000)
    value = str(text or "")
    if should_store_raw_user_text(kind):
        return value[:max_chars] if max_chars and max_chars > 0 else value
    return redact_text(value, max_chars=max_chars)


def privacy_student_profile(profile: Dict[str, Any], *, include_excerpt: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "vector_kind": profile.get("vector_kind") or "student_supply",
        "scores": profile.get("scores") or {},
        "confidences": profile.get("confidences") or {},
    }
    for key in ("score_avg", "conf_avg"):
        if profile.get(key) is not None:
            out[key] = profile.get(key)

    education = profile.get("education") or profile.get("major")
    if education:
        out["education"] = redact_text(education, max_chars=120)

    city_pref = profile.get("city_pref")
    if city_pref:
        out["city_pref"] = redact_text(city_pref, max_chars=80)

    skills_hint = profile.get("skills_hint")
    if isinstance(skills_hint, list):
        safe_skills: List[str] = []
        for item in skills_hint:
            text = redact_text(item, max_chars=80).strip()
            if text:
                safe_skills.append(text)
            if len(safe_skills) >= 12:
                break
        if safe_skills:
            out["skills_hint"] = safe_skills
    elif skills_hint:
        out["skills_hint"] = redact_text(skills_hint, max_chars=240)

    if include_excerpt and profile.get("resume_excerpt"):
        out["resume_excerpt"] = redact_text(
            profile.get("resume_excerpt"),
            max_chars=_cfg_int("LLM_MAX_FIELD_CHARS", 1200),
        )
    return out


def llm_privacy_notice() -> str:
    if not privacy_mode_enabled():
        return ""
    return (
        "Privacy rule: user identifiers and contact details may be redacted. "
        "Do not request, infer, repeat, or output real names, phone numbers, emails, "
        "ID numbers, account tokens, addresses, or other personal identifiers."
    )
