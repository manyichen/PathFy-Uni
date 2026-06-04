"""目标职业粗排。"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import current_app

from app.infrastructure.neo4j import serialize_job_row
from app.domains.match.services import (
    _coarse_morphology_match,
    _fetch_jobs_for_match,
    _sort_ranked_for_goal,
)

def _build_match_ranked(profile: Dict[str, Any], q: str, location_q: str, match_goal: str) -> List[Dict[str, Any]]:
    rows = _fetch_jobs_for_match(
        q=q,
        location_q=location_q,
        cap=max(120, int(current_app.config.get("MATCH_LLM_POOL_K", 40)) * 4),
    )
    shape_w = float(current_app.config.get("MATCH_COARSE_SHAPE_WEIGHT", 0.42))
    margin_fit = float(current_app.config.get("MATCH_GAP_SOFT_MARGIN_FIT", 6.0))
    margin_stretch = float(current_app.config.get("MATCH_GAP_SOFT_MARGIN_STRETCH", 10.0))
    soft_margin = margin_stretch if match_goal == "stretch" else margin_fit
    ranked: List[Dict[str, Any]] = []
    for row in rows:
        card = serialize_job_row(row)
        ms, wg, gaps, shape_r = _coarse_morphology_match(
            profile["scores"],
            profile["confidences"],
            card["scores"],
            card["confidences"],
            soft_margin=soft_margin,
            shape_weight=shape_w,
        )
        ranked.append(
            {
                **card,
                "match_preview": {
                    "match_score": ms,
                    "weighted_gap": wg,
                    "dimension_gaps": gaps,
                    "shape_correlation": shape_r,
                },
            }
        )
    _sort_ranked_for_goal(ranked, match_goal)
    return ranked

