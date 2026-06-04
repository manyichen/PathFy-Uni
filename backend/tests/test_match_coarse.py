"""人岗匹配粗排纯函数。"""

from __future__ import annotations

from app.domains.match.capability_profile import serialize_capability_profile
from app.domains.match.services import _coarse_morphology_match, _pearson_across_dims
from app.infrastructure.neo4j import CONF_KEYS, DIM_KEYS


def _flat_scores(value: float) -> dict[str, float]:
    return {k: value for k in DIM_KEYS}


def _flat_conf(value: float) -> dict[str, float]:
    return {k: value for k in CONF_KEYS}


def test_pearson_identical_profiles():
    scores = _flat_scores(70.0)
    r = _pearson_across_dims(scores, scores)
    assert r == 1.0


def test_coarse_match_identical_high():
    scores = _flat_scores(80.0)
    conf = _flat_conf(0.8)
    ms, wg, _gaps, shape_r = _coarse_morphology_match(
        scores, conf, scores, conf, soft_margin=6.0, shape_weight=0.42
    )
    assert ms >= 90.0
    assert wg == 0.0
    assert shape_r == 1.0


def test_serialize_capability_profile():
    raw = {
        "id": "1",
        "display_name": "测试",
        "scores": _flat_scores(60.0),
        "confidences": _flat_conf(0.55),
    }
    out = serialize_capability_profile(raw)
    assert out["vector_kind"] == "student_supply"
    assert out["score_avg"] == 60.0
    assert len(out["scores"]) == len(DIM_KEYS)
