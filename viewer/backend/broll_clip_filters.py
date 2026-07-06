"""Shared b-roll clip filtering helpers."""

from __future__ import annotations

import math
from typing import Any


def segment_duration_seconds(segment: dict[str, Any] | None) -> float | None:
    if not segment:
        return None
    timing = segment.get("timing") or {}
    duration = timing.get("duration_seconds")
    if duration is None:
        return None
    try:
        value = float(duration)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def min_required_clip_duration(segment_duration: float | None) -> float | None:
    """Clips must be at least half the segment length (never shorter)."""
    if segment_duration is None or segment_duration <= 0:
        return None
    return segment_duration * 0.5


def video_duration_seconds(video: dict[str, Any]) -> float:
    try:
        return float(video.get("duration") or 0)
    except (TypeError, ValueError):
        return 0.0


def clip_meets_duration_requirement(
    video: dict[str, Any],
    segment_duration: float | None,
) -> bool:
    minimum = min_required_clip_duration(segment_duration)
    if minimum is None:
        return True
    clip_duration = video_duration_seconds(video)
    if clip_duration <= 0:
        return False
    return clip_duration >= minimum


def filter_videos_for_segment(
    videos: list[dict[str, Any]],
    segment: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    segment_duration = segment_duration_seconds(segment)
    if segment_duration is None:
        return videos
    return [
        video
        for video in videos
        if clip_meets_duration_requirement(video, segment_duration)
    ]


def pexels_min_duration_param(segment_duration: float | None) -> int | None:
    minimum = min_required_clip_duration(segment_duration)
    if minimum is None:
        return None
    return max(1, int(math.ceil(minimum)))
