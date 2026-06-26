"""Persistent red-flag registry for b-roll clips that must never be auto-fetched again."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def clip_key(video: dict[str, Any] | None) -> str:
    if not video:
        return ""
    provider = str(video.get("provider") or "unknown").strip().lower()
    video_id = video.get("video_id")
    if video_id is not None and str(video_id).strip() != "":
        return f"{provider}:{video_id}"
    url = str(video.get("url") or "").strip()
    return f"url:{url}" if url else ""


def load_flagged_clips(flagged_path: Path) -> dict[str, Any]:
    if not flagged_path.exists():
        return {"clips": {}}
    try:
        data = json.loads(flagged_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"clips": {}}
    if "clips" not in data or not isinstance(data["clips"], dict):
        data["clips"] = {}
    return data


def save_flagged_clips(flagged_path: Path, data: dict[str, Any]) -> None:
    flagged_path.parent.mkdir(parents=True, exist_ok=True)
    flagged_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_flagged_keys(flagged_path: Path) -> set[str]:
    data = load_flagged_clips(flagged_path)
    return set(data.get("clips", {}).keys())


def is_clip_flagged(video: dict[str, Any] | None, flagged_path: Path) -> bool:
    key = clip_key(video)
    if not key:
        return False
    return key in get_flagged_keys(flagged_path)


def filter_flagged_videos(
    videos: list[dict[str, Any]],
    flagged_path: Path,
) -> list[dict[str, Any]]:
    flagged = get_flagged_keys(flagged_path)
    if not flagged:
        return videos
    return [video for video in videos if clip_key(video) not in flagged]


def flag_clip(flagged_path: Path, video: dict[str, Any]) -> dict[str, Any]:
    key = clip_key(video)
    if not key:
        raise ValueError("Cannot flag clip without video_id or url")

    data = load_flagged_clips(flagged_path)
    entry = {
        "key": key,
        "provider": video.get("provider"),
        "video_id": video.get("video_id"),
        "url": video.get("url"),
        "thumbnail": video.get("thumbnail"),
        "photographer": video.get("photographer"),
        "pexels_url": video.get("pexels_url"),
        "pixabay_url": video.get("pixabay_url"),
        "flagged_at": time.time(),
    }
    data["clips"][key] = entry
    save_flagged_clips(flagged_path, data)
    return entry


def unflag_clip(flagged_path: Path, key: str) -> bool:
    data = load_flagged_clips(flagged_path)
    clips = data.get("clips", {})
    if key not in clips:
        return False
    del clips[key]
    data["clips"] = clips
    save_flagged_clips(flagged_path, data)
    return True


def list_flagged_clips(flagged_path: Path) -> list[dict[str, Any]]:
    data = load_flagged_clips(flagged_path)
    clips = list(data.get("clips", {}).values())
    clips.sort(key=lambda item: float(item.get("flagged_at") or 0), reverse=True)
    return clips


def find_segments_with_clip(
    rows: list[dict[str, Any]],
    video: dict[str, Any],
) -> list[int]:
    target = clip_key(video)
    if not target:
        return []
    segment_ids: list[int] = []
    for row in rows:
        selection = row.get("selection")
        if selection and clip_key(selection) == target:
            segment_ids.append(int(row["segment_id"]))
    segment_ids.sort()
    return segment_ids


def find_duplicate_clips(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def row_start_seconds(row: dict[str, Any]) -> float:
        timing = row.get("timing") or {}
        export_start = timing.get("export_start_seconds")
        if export_start is not None:
            try:
                return float(export_start)
            except (TypeError, ValueError):
                pass
        start = timing.get("start_seconds")
        if start is not None:
            try:
                return float(start)
            except (TypeError, ValueError):
                pass
        try:
            return float(row.get("segment_id", 0))
        except (TypeError, ValueError):
            return 0.0

    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        selection = row.get("selection")
        if not selection or not selection.get("url"):
            continue
        key = clip_key(selection)
        if not key:
            continue
        if key not in groups:
            groups[key] = {
                "key": key,
                "provider": selection.get("provider"),
                "video_id": selection.get("video_id"),
                "url": selection.get("url"),
                "thumbnail": selection.get("thumbnail"),
                "photographer": selection.get("photographer"),
                "pexels_url": selection.get("pexels_url"),
                "pixabay_url": selection.get("pixabay_url"),
                "segment_ids": [],
                "occurrences": [],
            }
        segment_id = int(row["segment_id"])
        groups[key]["segment_ids"].append(segment_id)
        groups[key]["occurrences"].append(
            {
                "segment_id": segment_id,
                "start_seconds": row_start_seconds(row),
            }
        )

    duplicates: list[dict[str, Any]] = []
    for group in groups.values():
        segment_ids = sorted(set(group["segment_ids"]))
        if len(segment_ids) < 2:
            continue
        group["segment_ids"] = segment_ids
        occurrences = sorted(
            group["occurrences"],
            key=lambda item: (float(item.get("start_seconds", 0.0)), int(item["segment_id"])),
        )
        gaps: list[dict[str, Any]] = []
        for index in range(len(occurrences) - 1):
            current = occurrences[index]
            following = occurrences[index + 1]
            delta = max(
                0.0,
                float(following.get("start_seconds", 0.0))
                - float(current.get("start_seconds", 0.0)),
            )
            gaps.append(
                {
                    "from_segment_id": int(current["segment_id"]),
                    "to_segment_id": int(following["segment_id"]),
                    "gap_seconds": delta,
                }
            )
        group["occurrences"] = occurrences
        group["gaps"] = gaps
        group["count"] = len(segment_ids)
        duplicates.append(group)

    duplicates.sort(key=lambda item: (-int(item["count"]), item["segment_ids"][0]))
    return duplicates
