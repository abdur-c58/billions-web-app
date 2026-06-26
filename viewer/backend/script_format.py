"""Parse script.json in legacy (type array) or folder (type string) format."""

from __future__ import annotations

from typing import Any


def parse_segment_broll_fields(segment: dict[str, Any]) -> tuple[str, str]:
    """Return (search_query, category) for a script segment."""
    raw_type = segment.get("type", ["", ""])
    description = str(segment.get("description", "")).strip()

    if isinstance(raw_type, str):
        category = raw_type.strip()
        search_query = description or category
        return search_query, category

    if isinstance(raw_type, list):
        search_query, category = (raw_type + ["", ""])[:2]
        return str(search_query).strip(), str(category).strip()

    return description, ""


def detect_script_format(script_data: dict[str, Any]) -> str:
    """Return ``folder`` when every typed segment uses a string ``type``."""
    kinds: set[str] = set()
    for beat_block in script_data.get("script", []):
        for segment in beat_block.get("segments", []):
            raw_type = segment.get("type")
            if isinstance(raw_type, str):
                kinds.add("folder")
            elif isinstance(raw_type, list):
                kinds.add("legacy")
            elif raw_type is not None:
                kinds.add("other")

    if kinds == {"folder"}:
        return "folder"
    return "legacy"


def iter_broll_script_segments(script_data: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for beat_block in script_data.get("script", []):
        beat = beat_block.get("beat")
        label = beat_block.get("label")
        for segment in beat_block.get("segments", []):
            if "segment_id" not in segment or "content" not in segment:
                continue
            search_query, category = parse_segment_broll_fields(segment)
            segments.append(
                {
                    "segment_id": segment["segment_id"],
                    "beat": beat,
                    "label": label,
                    "content": segment.get("content", ""),
                    "description": segment.get("description", ""),
                    "search_query": search_query,
                    "category": category,
                }
            )
    segments.sort(key=lambda item: item["segment_id"])
    return segments
