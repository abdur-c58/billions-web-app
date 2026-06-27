"""Heuristic + OpenAI vision judging for b-roll candidate selection."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
AI_MODEL = "gpt-4o-mini"
MAX_CANDIDATES_FOR_AI = 5
HEURISTIC_AUTO_PICK = 7.5
NEEDS_REVIEW_THRESHOLD = 0.55
DEFAULT_AI_MAX_CALLS_PER_DAY = 100

QUALITY_LABELS: dict[str, str] = {
    "none": "Missing",
    "good": "Good",
    "mid": "Mid",
    "review": "Review",
    "unknown": "Unknown",
}

# test comment
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

    duration = float(video.get("duration") or 0)
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)

    if duration >= 8:
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


class AiBudget:
    def __init__(self, cache_dir: Path, max_calls: int = DEFAULT_AI_MAX_CALLS_PER_DAY) -> None:
        self.cache_dir = cache_dir
        self.max_calls = max_calls
        self.path = cache_dir / "ai_usage.json"
        self._calls = 0
        self._load()

    def _load(self) -> None:
        today = date.today().isoformat()
        if not self.path.exists():
            self._calls = 0
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._calls = 0
            return
        if data.get("date") != today:
            self._calls = 0
        else:
            self._calls = int(data.get("calls") or 0)
            saved_max = int(data.get("max_calls") or 0)
            if saved_max > 0:
                self.max_calls = saved_max

    def _save(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "date": date.today().isoformat(),
                    "calls": self._calls,
                    "max_calls": self.max_calls,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self._calls)

    def can_use(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY")) and self.remaining > 0

    def consume(self) -> None:
        self._calls += 1
        self._save()

    def snapshot(self) -> dict[str, Any]:
        return {
            "calls_today": self._calls,
            "max_calls": self.max_calls,
            "remaining": self.remaining,
        }


class JudgmentCache:
    def __init__(self, cache_dir: Path) -> None:
        self.path = cache_dir / "ai_judgments.json"
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


def _openai_judge_once(
    segment: dict[str, Any],
    candidates: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    labels = []
    for index, video in enumerate(candidates):
        labels.append(
            f"Option {index}: video_id={video.get('video_id')} "
            f"duration={video.get('duration')}s size={video.get('width')}x{video.get('height')}"
        )

    prompt = (
        "Pick the best stock b-roll thumbnail for a documentary segment.\n"
        f"Search query: {query}\n"
        f"Needed visual: {segment.get('description', '')}\n"
        f"Narration excerpt: {segment.get('content', '')[:220]}\n\n"
        + "\n".join(labels)
        + "\n\nReturn JSON only with keys: "
        "best_index (0-based int), match_score (0-1 float), "
        "subject_match (bool), tone_match (bool), reason (max 15 words)."
    )

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for video in candidates:
        thumbnail = video.get("thumbnail")
        if thumbnail:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": thumbnail, "detail": "low"},
                }
            )

    body = json.dumps(
        {
            "model": AI_MODEL,
            "temperature": 0.1,
            "max_tokens": 180,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": content}],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Billions-BrollViewer/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {raw}") from exc

    message = payload["choices"][0]["message"]["content"]
    parsed = json.loads(message)
    best_index = int(parsed.get("best_index", 0))
    best_index = max(0, min(best_index, len(candidates) - 1))
    match_score = float(parsed.get("match_score", 0))
    match_score = max(0.0, min(1.0, match_score))

    return {
        "best_index": best_index,
        "confidence": round(match_score, 3),
        "confidence_source": "openai",
        "needs_review": match_score < NEEDS_REVIEW_THRESHOLD,
        "ai_model": AI_MODEL,
        "ai_reason": str(parsed.get("reason", ""))[:120],
        "subject_match": bool(parsed.get("subject_match")),
        "tone_match": bool(parsed.get("tone_match")),
        "ai_skipped": None,
    }


def _heuristic_pick(
    segment: dict[str, Any],
    candidates: list[dict[str, Any]],
    query: str,
    *,
    ai_skipped: str | None,
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
        "ai_model": None,
        "ai_reason": None,
        "subject_match": None,
        "tone_match": None,
        "ai_skipped": ai_skipped,
        "heuristic_scores": scores,
    }


def pick_best_candidate(
    segment: dict[str, Any],
    candidates: list[dict[str, Any]],
    query: str,
    *,
    segment_id: int,
    cache_dir: Path,
    use_ai: bool,
    budget: AiBudget | None,
    judgment_cache: JudgmentCache | None = None,
) -> dict[str, Any]:
    if not candidates:
        return {
            "best_index": 0,
            "confidence": 0.0,
            "confidence_source": "heuristic",
            "needs_review": True,
            "ai_skipped": "no_candidates",
        }

    pool_indices: list[int] = []
    pool: list[dict[str, Any]] = []
    for index, video in enumerate(candidates):
        width = int(video.get("width") or 0)
        duration = float(video.get("duration") or 0)
        if width and width < 480:
            continue
        if duration and duration < 1.5:
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
                "ai_model": None,
                "ai_reason": "Strong technical/heuristic match",
                "subject_match": None,
                "tone_match": None,
                "ai_skipped": "heuristic_confident",
                "heuristic_scores": scores,
            },
        )

    ai_pool = [pool[i] for i in ranked[:MAX_CANDIDATES_FOR_AI]]
    ai_index_map = ranked[:MAX_CANDIDATES_FOR_AI]

    if use_ai and budget and budget.can_use():
        try:
            ai_result = _openai_judge_once(segment, ai_pool, query)
            budget.consume()
            mapped_pool_index = ai_index_map[ai_result["best_index"]]
            return finalize(
                mapped_pool_index,
                {
                    "confidence": ai_result["confidence"],
                    "confidence_source": "openai",
                    "needs_review": ai_result["needs_review"],
                    "ai_model": ai_result["ai_model"],
                    "ai_reason": ai_result["ai_reason"],
                    "subject_match": ai_result["subject_match"],
                    "tone_match": ai_result["tone_match"],
                    "ai_skipped": None,
                    "heuristic_scores": scores,
                },
            )
        except Exception as exc:
            message = str(exc).lower()
            if "insufficient_quota" in message or "billing" in message:
                skipped = "quota_exceeded"
            elif "429" in message:
                skipped = "rate_limited"
            else:
                skipped = "api_error"
            heuristic = _heuristic_pick(segment, pool, query, ai_skipped=skipped)
            return finalize(int(heuristic["best_index"]), heuristic)

    skipped = "disabled"
    if not use_ai:
        skipped = "disabled"
    elif budget and not os.environ.get("OPENAI_API_KEY"):
        skipped = "missing_api_key"
    elif budget and budget.remaining <= 0:
        skipped = "budget_exhausted"

    heuristic = _heuristic_pick(segment, pool, query, ai_skipped=skipped)
    return finalize(int(heuristic["best_index"]), heuristic)
