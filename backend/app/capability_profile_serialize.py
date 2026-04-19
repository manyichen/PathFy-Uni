"""学生能力画像序列化（八维分与置信度），供匹配粗排等复用。"""

from __future__ import annotations

from typing import Any, Dict

from .jobs import CONF_KEYS, DIM_KEYS


def _wrap_scores(raw: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in DIM_KEYS:
        out[k] = round(float(raw.get(k, 0.0)), 2)
    return out


def _wrap_conf(raw: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k in CONF_KEYS:
        v = float(raw.get(k, 0.6))
        out[k] = round(min(1.0, max(0.0, v)), 4)
    return out


def serialize_capability_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    scores = _wrap_scores(profile["scores"])
    confidences = _wrap_conf(profile["confidences"])
    score_avg = round(sum(scores.values()) / len(DIM_KEYS), 2) if DIM_KEYS else 0.0
    conf_avg = round((sum(confidences.values()) / len(CONF_KEYS)) * 100, 2) if CONF_KEYS else 0.0
    base = {k: v for k, v in profile.items() if k not in ("scores", "confidences")}
    return {
        **base,
        "vector_kind": "student_supply",
        "scores": scores,
        "confidences": confidences,
        "score_avg": score_avg,
        "conf_avg": conf_avg,
    }
