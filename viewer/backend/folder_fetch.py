"""Plan and apply bulk B-Roll folder assignments for folder-format scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from storage_r2 import broll_category_prefix, list_r2_videos

ShortageStrategy = Literal["leave_empty", "reuse_spaced", "random_api"]
FOLDER_REUSE_MIN_GAP_S = 300.0


def segment_timeline_start(segment: dict[str, Any]) -> float:
    timing = segment.get("timing") or {}
    for key in ("export_start_seconds", "start_seconds"):
        value = timing.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return float(segment.get("segment_id") or 0)


def enrich_segments_folder_status(
    segments: list[dict[str, Any]],
    script_format: str,
) -> None:
    if script_format != "folder":
        return

    clip_cache: dict[str, list[dict[str, Any]]] = {}
    category_counts: dict[str, int] = {}

    for segment in segments:
        if segment.get("render_mode") == "remotion":
            continue
        category = str(segment.get("category") or "").strip()
        category_counts[category] = category_counts.get(category, 0) + 1

    for segment in segments:
        if segment.get("render_mode") == "remotion":
            segment["folder_status"] = {
                "expects_folder": False,
                "has_folder": False,
                "clip_count": 0,
            }
            continue
        category = str(segment.get("category") or "").strip()
        if category == "stock":
            segment["folder_status"] = {
                "expects_folder": False,
                "has_folder": False,
                "clip_count": 0,
            }
            continue

        if category not in clip_cache:
            clip_cache[category] = list_r2_videos(broll_category_prefix(category))
        clips = clip_cache[category]
        segment_count = category_counts.get(category, 0)
        segment["folder_status"] = {
            "expects_folder": True,
            "has_folder": len(clips) > 0,
            "clip_count": len(clips),
            "folder_prefix": broll_category_prefix(category),
            "shortage": 0 < len(clips) < segment_count,
        }


def _pick_spaced_clip(
    clips: list[dict[str, Any]],
    segment_start: float,
    last_used_at: dict[str, float],
) -> dict[str, Any]:
    eligible: list[tuple[float, dict[str, Any]]] = []
    for clip in clips:
        key = str(clip["key"])
        last_at = last_used_at.get(key, -1e18)
        gap = segment_start - last_at
        if gap >= FOLDER_REUSE_MIN_GAP_S:
            eligible.append((gap, clip))

    if eligible:
        eligible.sort(key=lambda item: item[0], reverse=True)
        return eligible[0][1]

    return min(
        clips,
        key=lambda clip: last_used_at.get(str(clip["key"]), -1e18),
    )


def _append_folder_assignment(
    assignments: list[dict[str, Any]],
    segment: dict[str, Any],
    category: str,
    clip: dict[str, Any],
    prefix: str,
    *,
    reused: bool = False,
) -> None:
    assignments.append(
        {
            "segment_id": segment["segment_id"],
            "category": category,
            "mode": "folder",
            "search_query": segment.get("search_query", ""),
            "storage_key": clip["key"],
            "clip_name": clip["name"],
            "folder": prefix,
            "reused": reused,
        }
    )


def _append_unassigned(
    assignments: list[dict[str, Any]],
    segment: dict[str, Any],
    category: str,
) -> None:
    assignments.append(
        {
            "segment_id": segment["segment_id"],
            "category": category,
            "mode": "unassigned",
            "search_query": segment.get("search_query", ""),
            "warning": "Left empty — assign manually later.",
        }
    )


def _append_api_shortage(
    assignments: list[dict[str, Any]],
    segment: dict[str, Any],
    category: str,
) -> None:
    assignments.append(
        {
            "segment_id": segment["segment_id"],
            "category": category,
            "mode": "api_shortage",
            "search_query": segment.get("search_query", ""),
            "warning": (
                f"Not enough clips in B-Roll/{category}/ — "
                f"will fetch randomly from API using \"{segment.get('search_query', '')}\"."
            ),
        }
    )


def _assign_category_segments(
    assignments: list[dict[str, Any]],
    category: str,
    ordered: list[dict[str, Any]],
    clips: list[dict[str, Any]],
    strategy: ShortageStrategy,
) -> None:
    prefix = broll_category_prefix(category)
    has_shortage = len(clips) < len(ordered)

    if not has_shortage:
        last_used_at: dict[str, float] = {}
        for segment in ordered:
            start = segment_timeline_start(segment)
            clip = _pick_spaced_clip(clips, start, last_used_at)
            _append_folder_assignment(
                assignments,
                segment,
                category,
                clip,
                prefix,
                reused=last_used_at.get(str(clip["key"])) is not None,
            )
            last_used_at[str(clip["key"])] = start
        return

    if strategy == "leave_empty":
        for index, segment in enumerate(ordered):
            if index < len(clips):
                clip = clips[index % len(clips)]
                _append_folder_assignment(
                    assignments, segment, category, clip, prefix
                )
            else:
                _append_unassigned(assignments, segment, category)
        return

    if strategy == "reuse_spaced":
        last_used_at = {}
        for segment in ordered:
            start = segment_timeline_start(segment)
            clip = _pick_spaced_clip(clips, start, last_used_at)
            _append_folder_assignment(
                assignments,
                segment,
                category,
                clip,
                prefix,
                reused=last_used_at.get(str(clip["key"])) is not None,
            )
            last_used_at[str(clip["key"])] = start
        return

    if strategy == "random_api":
        for index, segment in enumerate(ordered):
            if index < len(clips):
                clip = clips[index % len(clips)]
                _append_folder_assignment(
                    assignments, segment, category, clip, prefix
                )
            else:
                _append_api_shortage(assignments, segment, category)
        return


def build_folder_fetch_plan(
    segments: list[dict[str, Any]],
    *,
    shortage_strategy: ShortageStrategy | None = None,
) -> dict[str, Any]:
    assignments: list[dict[str, Any]] = []
    folder_clips: dict[str, list[dict[str, Any]]] = {}
    by_category: dict[str, list[dict[str, Any]]] = {}
    shortages: list[dict[str, Any]] = []

    for segment in segments:
        if segment.get("render_mode") == "remotion":
            continue
        category = str(segment.get("category") or "").strip()
        if category == "stock":
            assignments.append(
                {
                    "segment_id": segment["segment_id"],
                    "category": category,
                    "mode": "api",
                    "search_query": segment.get("search_query", ""),
                }
            )
            continue
        by_category.setdefault(category, []).append(segment)

    for category, category_segments in by_category.items():
        prefix = broll_category_prefix(category)
        if category not in folder_clips:
            folder_clips[category] = list_r2_videos(prefix)
        clips = folder_clips[category]
        ordered = sorted(category_segments, key=lambda item: item["segment_id"])

        if not clips:
            for segment in ordered:
                assignments.append(
                    {
                        "segment_id": segment["segment_id"],
                        "category": category,
                        "mode": "api_warning",
                        "search_query": segment.get("search_query", ""),
                        "warning": (
                            f"No clips found in B-Roll/{category}/. "
                            "Use API fetch for this segment."
                        ),
                    }
                )
            continue

        if len(clips) < len(ordered):
            shortages.append(
                {
                    "category": category,
                    "segment_count": len(ordered),
                    "clip_count": len(clips),
                    "deficit": len(ordered) - len(clips),
                    "folder_prefix": prefix,
                }
            )

        strategy: ShortageStrategy = shortage_strategy or "reuse_spaced"
        if len(clips) >= len(ordered):
            strategy = shortage_strategy or "reuse_spaced"
        elif not shortage_strategy:
            # Preview only: show spaced reuse as default illustration.
            strategy = "reuse_spaced"

        _assign_category_segments(
            assignments,
            category,
            ordered,
            clips,
            strategy,
        )

    assignments.sort(key=lambda item: item["segment_id"])
    needs_shortage_choice = bool(shortages) and shortage_strategy is None

    return {
        "assignments": assignments,
        "shortages": shortages,
        "needs_shortage_choice": needs_shortage_choice,
        "shortage_strategy": shortage_strategy,
        "summary": {
            "folder": sum(1 for item in assignments if item["mode"] == "folder"),
            "api": sum(1 for item in assignments if item["mode"] == "api"),
            "api_warning": sum(
                1 for item in assignments if item["mode"] == "api_warning"
            ),
            "api_shortage": sum(
                1 for item in assignments if item["mode"] == "api_shortage"
            ),
            "unassigned": sum(
                1 for item in assignments if item["mode"] == "unassigned"
            ),
            "total": len(assignments),
        },
        "folders": {
            category: {
                "prefix": broll_category_prefix(category),
                "clip_count": len(clips),
            }
            for category, clips in folder_clips.items()
        },
    }


def apply_folder_fetch_plan(
    selections_path: Path,
    script_path: Path,
    segments_by_id: dict[int, dict[str, Any]],
    assignments: list[dict[str, Any]],
    *,
    cache_dir: Path | None = None,
    use_ai: bool = True,
    ai_budget: Any | None = None,
    judgment_cache: Any | None = None,
    flagged_path: Path | None = None,
) -> dict[str, Any]:
    from broll_viewer import (
        build_storage_selection,
        fetch_segment_video,
        save_segment_selection,
    )

    applied: list[dict[str, Any]] = []
    api_fetched: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for item in assignments:
        mode = item.get("mode")
        if mode in {"api", "api_warning", "unassigned"}:
            skipped.append(item)
            continue

        segment_id = int(item["segment_id"])
        segment = segments_by_id.get(segment_id)
        if segment is None:
            continue

        if mode == "api_shortage":
            try:
                payload = fetch_segment_video(
                    selections_path,
                    script_path,
                    segment_id,
                    segment["search_query"],
                    refetch=False,
                    provider_override="random",
                    segment=segment,
                    cache_dir=cache_dir,
                    use_ai=use_ai,
                    ai_budget=ai_budget,
                    judgment_cache=judgment_cache,
                    flagged_path=flagged_path,
                )
                api_fetched.append(
                    {
                        "segment_id": segment_id,
                        "selection": payload.get("selection"),
                    }
                )
            except Exception as exc:
                api_fetched.append(
                    {
                        "segment_id": segment_id,
                        "error": str(exc),
                    }
                )
            continue

        if mode != "folder":
            skipped.append(item)
            continue

        storage_key = str(item.get("storage_key") or "").strip()
        if not storage_key:
            continue

        video = build_storage_selection(storage_key)
        saved = save_segment_selection(
            selections_path,
            script_path,
            segment_id,
            segment["search_query"],
            video,
            1,
            0,
            query_used=f"folder:{storage_key}",
            fetch_provider="storage",
            judgment={
                "confidence": 1.0,
                "confidence_source": "manual",
                "needs_review": False,
                "ai_skipped": "folder_fetch",
            },
        )
        applied.append(
            {
                "segment_id": segment_id,
                "selection": saved,
                "storage_key": storage_key,
                "clip_name": item.get("clip_name"),
            }
        )

    return {
        "applied_count": len(applied),
        "api_fetched_count": len(
            [entry for entry in api_fetched if entry.get("selection")]
        ),
        "skipped_count": len(skipped),
        "applied": applied,
        "api_fetched": api_fetched,
    }
