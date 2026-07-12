"""Heuristic scoring for b-roll candidate selection."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from broll_clip_filters import (
    clip_meets_duration_requirement,
    min_required_clip_duration,
    segment_duration_seconds,
    video_duration_seconds,
)

HEURISTIC_AUTO_PICK = 7.5
NEEDS_REVIEW_THRESHOLD = 0.55

QUALITY_LABELS: dict[str, str] = {
    "none": "Missing",
    "good": "Good",
    "mid": "Mid",
    "review": "Review",
    "unknown": "Unknown",
}


def compute_quality_tier(selection: dict[str, Any] | None) -> str:
    if not selection or not selection.get("url"):
        return "none"
    if selection.get("confidence_source") == "manual":
        return "good"
    if selection.get("needs_review"):
        return "review"
    confidence = selection.get("confidence")
    if confidence is None:
        return "unknown"
    value = float(confidence)
    if value >= 0.72:
        return "good"
    if value >= NEEDS_REVIEW_THRESHOLD:
        return "mid"
    return "review"


def enrich_selection_judgment(
    selection: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not selection:
        return None
    tier = compute_quality_tier(selection)
    return {
        **selection,
        "quality_tier": tier,
        "quality_label": QUALITY_LABELS.get(tier, tier),
    }


def summarize_judgments(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in QUALITY_LABELS}
    for row in rows:
        tier = compute_quality_tier(row.get("selection"))
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def score_candidate_heuristic(
    video: dict[str, Any],
    segment: dict[str, Any],
    query: str,
) -> float:
    score = 0.0
    query_tokens = _tokenize(query)
    desc_tokens = _tokenize(segment.get("description", ""))
    content_tokens = _tokenize(segment.get("content", "")[:160])
    wanted = query_tokens | desc_tokens | content_tokens

    duration = video_duration_seconds(video)
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    segment_duration = segment_duration_seconds(segment)
    minimum = min_required_clip_duration(segment_duration)

    if segment_duration and minimum:
        if duration >= segment_duration:
            score += 3.5
        elif duration >= minimum:
            score += 2.0
        else:
            score -= 6.0
    elif duration >= 8:
        score += 2.0
    elif duration >= 5:
        score += 1.5
    elif duration >= 3:
        score += 0.75
    elif duration < 2:
        score -= 2.0

    if width >= 1920:
        score += 2.5
    elif width >= 1280:
        score += 1.5
    elif width >= 854:
        score += 0.5
    elif width < 640:
        score -= 1.5

    if width and height and width > height:
        score += 1.0

    if video.get("thumbnail"):
        score += 0.5

    meta_text = " ".join(
        str(video.get(key, ""))
        for key in ("alt", "title", "tags", "photographer")
        if video.get(key)
    )
    meta_tokens = _tokenize(meta_text)
    overlap = len(wanted & meta_tokens)
    score += min(3.0, overlap * 1.25)

    return round(score, 2)


class JudgmentCache:
    def __init__(self, cache_dir: Path) -> None:
        self.path = cache_dir / "heuristic_judgments.json"
        legacy_path = cache_dir / "ai_judgments.json"
        if not self.path.exists() and legacy_path.exists():
            self.path = legacy_path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _key(self, segment_id: int, query: str, candidates: list[dict[str, Any]]) -> str:
        ids = ",".join(str(video.get("video_id")) for video in candidates)
        return f"{segment_id}:{query}:{ids}"

    def get(
        self,
        segment_id: int,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        return self._data.get(self._key(segment_id, query, candidates))

    def set(
        self,
        segment_id: int,
        query: str,
        candidates: list[dict[str, Any]],
        payload: dict[str, Any],
    ) -> None:
        self._data[self._key(segment_id, query, candidates)] = payload
        self._save()


def _heuristic_pick(
    segment: dict[str, Any],
    candidates: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    scores = [
        score_candidate_heuristic(video, segment, query) for video in candidates
    ]
    best_index = max(range(len(candidates)), key=lambda i: scores[i])
    top = scores[best_index]
    confidence = round(min(0.95, top / 10.0), 3)
    return {
        "best_index": best_index,
        "confidence": confidence,
        "confidence_source": "heuristic",
        "needs_review": top < HEURISTIC_AUTO_PICK - 1.0,
        "match_reason": None,
        "heuristic_scores": scores,
    }


def pick_best_candidate(
    segment: dict[str, Any],
    candidates: list[dict[str, Any]],
    query: str,
    *,
    segment_id: int,
    cache_dir: Path,
    judgment_cache: JudgmentCache | None = None,
) -> dict[str, Any]:
    if not candidates:
        return {
            "best_index": 0,
            "confidence": 0.0,
            "confidence_source": "heuristic",
            "needs_review": True,
        }

    segment_duration = segment_duration_seconds(segment)
    pool_indices: list[int] = []
    pool: list[dict[str, Any]] = []
    for index, video in enumerate(candidates):
        width = int(video.get("width") or 0)
        duration = video_duration_seconds(video)
        if width and width < 480:
            continue
        if not clip_meets_duration_requirement(video, segment_duration):
            continue
        if duration and duration < 1.5 and segment_duration is None:
            continue
        if not video.get("thumbnail"):
            continue
        pool_indices.append(index)
        pool.append(video)

    if not pool:
        pool = list(candidates)
        pool_indices = list(range(len(candidates)))

    if judgment_cache is None:
        judgment_cache = JudgmentCache(cache_dir)

    cached = judgment_cache.get(segment_id, query, pool)
    if cached:
        pool_index = int(cached.get("best_index", 0))
        pool_index = max(0, min(pool_index, len(pool) - 1))
        return {
            **cached,
            "best_index": pool_indices[pool_index],
        }

    scores = [score_candidate_heuristic(video, segment, query) for video in pool]
    ranked = sorted(range(len(pool)), key=lambda i: scores[i], reverse=True)
    top_index = ranked[0]
    top_score = scores[top_index]
    second_score = scores[ranked[1]] if len(ranked) > 1 else 0.0

    def finalize(pool_index: int, payload: dict[str, Any]) -> dict[str, Any]:
        pool_index = max(0, min(pool_index, len(pool) - 1))
        result = {**payload, "best_index": pool_indices[pool_index]}
        judgment_cache.set(segment_id, query, pool, {**payload, "best_index": pool_index})
        return result

    if top_score >= HEURISTIC_AUTO_PICK and (top_score - second_score) >= 1.5:
        return finalize(
            top_index,
            {
                "confidence": round(min(0.95, top_score / 10.0), 3),
                "confidence_source": "heuristic",
                "needs_review": False,
                "match_reason": "Strong technical/heuristic match",
                "heuristic_scores": scores,
            },
        )

    heuristic = _heuristic_pick(segment, pool, query)
    return finalize(int(heuristic["best_index"]), heuristic)
