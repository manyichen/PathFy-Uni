"""Controlled, reversible preference tie-break ranking.

The function only reorders consecutive jobs inside a narrow capability-score
band.  It records both orders and never changes any score.
"""
from __future__ import annotations

import hashlib
from typing import Any, MutableMapping, Sequence


PREFERENCE_RANKING_VERSION = "preference-tie-break-v1"
PREFERENCE_EXPERIMENT_KEY = "preference-tie-break-v1"


def experiment_variant(user_id: int, percent: int) -> tuple[str, int]:
    bucket = int(hashlib.sha256(f"{user_id}:{PREFERENCE_EXPERIMENT_KEY}".encode("utf-8")).hexdigest()[:8], 16) % 100
    return ("tie_break" if bucket < max(0, min(100, int(percent))) else "control", bucket)


def apply_preference_tie_break(
    ranked: list[MutableMapping[str, Any]],
    *,
    max_ability_gap: float = 3.0,
) -> dict[str, Any]:
    original_order = [str(card.get("id") or "") for card in ranked]
    for index, card in enumerate(ranked, start=1):
        preview = card.setdefault("match_preview", {})
        preview["ability_rank"] = index
        preview["preference_rank"] = index

    groups: list[tuple[int, int]] = []
    start = 0
    while start < len(ranked):
        anchor = float((ranked[start].get("match_preview") or {}).get("match_score") or 0.0)
        end = start + 1
        while end < len(ranked):
            score = float((ranked[end].get("match_preview") or {}).get("match_score") or 0.0)
            if abs(anchor - score) > max(0.0, float(max_ability_gap)):
                break
            end += 1
        if end - start > 1:
            groups.append((start, end))
        start = end

    for start, end in groups:
        segment = ranked[start:end]
        segment.sort(
            key=lambda card: (
                0 if ((card.get("match_preview") or {}).get("preference_fit") or {}).get("status") == "available" else 1,
                -float((((card.get("match_preview") or {}).get("preference_fit") or {}).get("score") or 0.0)),
                int((card.get("match_preview") or {}).get("ability_rank") or 0),
            )
        )
        ranked[start:end] = segment

    changed: list[dict[str, Any]] = []
    for index, card in enumerate(ranked, start=1):
        preview = card.setdefault("match_preview", {})
        preview["preference_rank"] = index
        ability_rank = int(preview.get("ability_rank") or index)
        influenced = ability_rank != index
        fit = preview.get("preference_fit")
        if isinstance(fit, dict):
            fit["influenced_ranking"] = influenced
        if influenced:
            changed.append({"job_id": str(card.get("id") or ""), "ability_rank": ability_rank, "preference_rank": index})

    return {
        "version": PREFERENCE_RANKING_VERSION,
        "original_ability_order": original_order,
        "preference_order": [str(card.get("id") or "") for card in ranked],
        "changes": changed,
        "changed_jobs": len(changed),
        "max_ability_gap": float(max_ability_gap),
    }
