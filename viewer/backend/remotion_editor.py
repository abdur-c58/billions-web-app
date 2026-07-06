#!/usr/bin/env python3
"""Save and preview Remotion segment customizations from the viewer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from script_format import (
    KNOWN_REMOTION_COMPOSITIONS,
    is_remotion_segment,
    parse_remotion_fields,
    parse_segment_render,
)

PREVIEW_WIDTH = 1280
PREVIEW_HEIGHT = 720
PREVIEW_MAX_SECONDS = 12.0
PREVIEW_MIN_SECONDS = 2.0

TEXT_ALIGNS = frozenset({"left", "center", "right"})
VERTICAL_ALIGNS = frozenset({"top", "center", "bottom"})

COMPOSITION_PROP_KEYS: dict[str, frozenset[str]] = {
    "FactCard": frozenset(
        {
            "factNumber",
            "title",
            "body",
            "accentColor",
            "textAlign",
            "verticalAlign",
            "padding",
            "titleSize",
            "bodySize",
        }
    ),
    "TitleCard": frozenset(
        {
            "title",
            "subtitle",
            "accentColor",
            "textAlign",
            "verticalAlign",
            "padding",
            "titleSize",
            "subtitleSize",
        }
    ),
}


def find_script_segment(script_data: dict[str, Any], segment_id: int) -> dict[str, Any] | None:
    for beat_block in script_data.get("script", []):
        for segment in beat_block.get("segments", []):
            if int(segment.get("segment_id", -1)) == segment_id:
                return segment
    return None


def sanitize_remotion_props(composition: str, props: dict[str, Any]) -> dict[str, Any]:
    if composition not in KNOWN_REMOTION_COMPOSITIONS:
        raise ValueError(f"Unknown Remotion composition: {composition}")

    allowed = COMPOSITION_PROP_KEYS[composition]
    cleaned: dict[str, Any] = {}
    for key, value in props.items():
        if key not in allowed:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        cleaned[key] = value

    if "factNumber" in cleaned:
        try:
            cleaned["factNumber"] = int(cleaned["factNumber"])
        except (TypeError, ValueError):
            cleaned.pop("factNumber", None)

    for size_key in ("titleSize", "bodySize", "subtitleSize", "padding"):
        if size_key in cleaned:
            try:
                number = float(cleaned[size_key])
            except (TypeError, ValueError):
                cleaned.pop(size_key, None)
                continue
            if size_key == "padding":
                cleaned[size_key] = int(max(24, min(240, round(number))))
            else:
                cleaned[size_key] = int(max(24, min(120, round(number))))

    if cleaned.get("textAlign") not in TEXT_ALIGNS:
        cleaned.pop("textAlign", None)
    if cleaned.get("verticalAlign") not in VERTICAL_ALIGNS:
        cleaned.pop("verticalAlign", None)

    if "accentColor" in cleaned:
        color = str(cleaned["accentColor"]).strip()
        if re.fullmatch(r"#[0-9a-fA-F]{3,8}", color):
            cleaned["accentColor"] = color
        else:
            cleaned.pop("accentColor", None)

    for text_key in ("title", "body", "subtitle"):
        if text_key in cleaned:
            cleaned[text_key] = str(cleaned[text_key]).strip()[:500]

    return cleaned


def merge_remotion_props(segment: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_remotion_fields(segment)
    composition = parsed["composition"]
    merged = dict(parsed.get("props") or {})
    merged.update(sanitize_remotion_props(composition, updates))
    return {
        "composition": composition,
        "props": merged,
    }


def update_remotion_segment_props(workspace: Path, segment_id: int, props: dict[str, Any]) -> dict[str, Any]:
    from project_manager import workspace_paths

    paths = workspace_paths(workspace)
    script_path = paths["script"]
    if not script_path.exists():
        raise FileNotFoundError("script.json not found.")

    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    segment = find_script_segment(script_data, segment_id)
    if segment is None:
        raise ValueError(f"Segment {segment_id} not found in script.")
    if not is_remotion_segment(segment):
        raise ValueError(f"Segment {segment_id} is not a Remotion segment.")

    merged = merge_remotion_props(segment, props)
    remotion_block = segment.get("remotion")
    if not isinstance(remotion_block, dict):
        remotion_block = {}
    remotion_block["composition"] = merged["composition"]
    remotion_block["props"] = merged["props"]
    segment["remotion"] = remotion_block

    script_path.write_text(
        json.dumps(script_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    timestamps_path = paths["timestamps"]
    if timestamps_path.exists():
        timestamps = json.loads(timestamps_path.read_text(encoding="utf-8"))
        render = parse_segment_render(segment)
        for entry in timestamps.get("segments", []):
            if int(entry.get("segment_id", -1)) != segment_id:
                continue
            entry["render_mode"] = "remotion"
            entry["remotion"] = render
            break
        timestamps_path.write_text(
            json.dumps(timestamps, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    try:
        from project_r2 import sync_workspace_file

        sync_workspace_file(workspace, "script.json")
        if timestamps_path.exists():
            sync_workspace_file(workspace, "segment_timestamps.json")
    except Exception:
        pass

    return merged


def segment_preview_duration_seconds(
    *,
    segment_id: int,
    timestamps_path: Path | None,
    fallback_seconds: float = 5.0,
) -> float:
    if timestamps_path and timestamps_path.exists():
        timestamps = json.loads(timestamps_path.read_text(encoding="utf-8"))
        for entry in timestamps.get("segments", []):
            if int(entry.get("segment_id", -1)) != segment_id:
                continue
            timing = entry.get("timing") or {}
            duration = timing.get("duration_seconds")
            if duration is not None and float(duration) > 0:
                return float(
                    max(PREVIEW_MIN_SECONDS, min(PREVIEW_MAX_SECONDS, float(duration)))
                )
    return max(PREVIEW_MIN_SECONDS, min(PREVIEW_MAX_SECONDS, fallback_seconds))


def preview_cache_name(segment_id: int, composition: str, props: dict[str, Any], duration: float) -> str:
    from remotion_render import _props_cache_key

    cache_key = _props_cache_key(
        composition,
        props,
        width=PREVIEW_WIDTH,
        height=PREVIEW_HEIGHT,
        duration_seconds=duration,
    )
    return f"preview_{segment_id:03d}_{cache_key}.mp4"


def render_remotion_segment_preview(
    *,
    workspace: Path,
    cache_dir: Path,
    segment_id: int,
    composition: str,
    props: dict[str, Any],
    duration_seconds: float,
    force: bool = False,
) -> Path:
    from export_video import normalize_segment_timestamps
    from remotion_render import render_remotion_clip

    preview_dir = cache_dir / "remotion_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    filename = preview_cache_name(segment_id, composition, props, duration_seconds)
    output_path = preview_dir / filename

    if not force and output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    render_remotion_clip(
        composition=composition,
        props=props,
        duration_seconds=duration_seconds,
        output_path=output_path,
        width=PREVIEW_WIDTH,
        height=PREVIEW_HEIGHT,
        cache_dir=None,
        force=True,
    )
    normalize_segment_timestamps(output_path)
    return output_path
