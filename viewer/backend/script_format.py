"""Parse script.json in legacy (type array) or folder (type string) format."""

from __future__ import annotations

import re
from typing import Any

REMOTION_TYPE_PREFIX = "remotion:"
KNOWN_REMOTION_COMPOSITIONS = frozenset({"FactCard", "TitleCard"})


def parse_segment_broll_fields(segment: dict[str, Any]) -> tuple[str, str]:
    """Return (search_query, category) for a script segment."""
    if is_remotion_segment(segment):
        composition = parse_remotion_fields(segment)["composition"]
        return "", f"{REMOTION_TYPE_PREFIX}{composition}"

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


def _raw_type_value(segment: dict[str, Any]) -> str:
    raw_type = segment.get("type", "")
    if isinstance(raw_type, str):
        return raw_type.strip()
    if isinstance(raw_type, list) and raw_type:
        return str(raw_type[0]).strip()
    return ""


def is_remotion_segment(segment: dict[str, Any]) -> bool:
    raw = _raw_type_value(segment).lower()
    if raw.startswith(REMOTION_TYPE_PREFIX):
        return True
    if raw == "remotion":
        return True
    if isinstance(segment.get("type"), list):
        parts = [str(part).strip().lower() for part in segment["type"]]
        if parts and parts[0] == "remotion":
            return True
    explicit = segment.get("remotion")
    return isinstance(explicit, dict) and bool(explicit.get("composition"))


def _composition_slug_to_id(slug: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", slug.strip()).strip()
    if not cleaned:
        return "FactCard"
    return "".join(word[:1].upper() + word[1:].lower() for word in cleaned.split())


def _infer_fact_number(content: str, label: str) -> int | None:
    for source in (content, label):
        match = re.search(r"\bfact\s+(\d+)\b", source, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        word_match = re.search(
            r"\bfact\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
            source,
            flags=re.IGNORECASE,
        )
        if word_match:
            words = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
                "seven": 7,
                "eight": 8,
                "nine": 9,
                "ten": 10,
                "eleven": 11,
                "twelve": 12,
            }
            return words.get(word_match.group(1).lower())
    return None


def _infer_title(content: str, label: str, description: str) -> str:
    if label.strip():
        return label.strip()
    if description.strip():
        return description.strip()
    sentence = re.split(r"(?<=[.!?])\s+", content.strip(), maxsplit=1)[0]
    return sentence[:120].strip() or "Segment"


def remotion_broll_search_query(segment: dict[str, Any]) -> str:
    """Search query for the left panel of split-screen FactCard segments."""
    explicit = segment.get("remotion")
    if isinstance(explicit, dict):
        broll = explicit.get("broll")
        if isinstance(broll, dict):
            query = str(broll.get("search_query") or broll.get("query") or "").strip()
            if query:
                return query
        direct = str(explicit.get("brollQuery") or "").strip()
        if direct:
            return direct

    description = str(segment.get("description") or "").strip()
    description = re.sub(
        r"^(left side b-roll|left b-roll|b-roll)\s*:\s*",
        "",
        description,
        flags=re.IGNORECASE,
    )
    if description:
        first = re.split(r"[.;]\s+", description, maxsplit=1)[0].strip()
        return (first or description)[:120]
    return "documentary landscape"


def remotion_broll_category(segment: dict[str, Any]) -> str:
    explicit = segment.get("remotion")
    if isinstance(explicit, dict):
        broll = explicit.get("broll")
        if isinstance(broll, dict):
            category = str(broll.get("category") or "").strip().lower()
            if category in {"stock", "commons"}:
                return category
    return "stock"


def remotion_layout_mode(segment: dict[str, Any], composition: str) -> str:
    """Return ``split-right``, ``overlay``, or ``full``."""
    explicit = segment.get("remotion")
    if isinstance(explicit, dict):
        layout = str(explicit.get("layout") or "").strip().lower()
        if layout in {"split-right", "full", "overlay"}:
            return layout
        design = explicit.get("design")
        if isinstance(design, dict):
            layout_block = design.get("layout")
            if isinstance(layout_block, dict):
                mode = str(layout_block.get("mode") or "").strip().lower()
                if mode in {"split-right", "full", "overlay"}:
                    return mode
                content_width = str(layout_block.get("contentMaxWidth") or "").lower()
                if "overlay" in content_width or "popup" in content_width or "lower-third" in content_width:
                    return "overlay"
                if "split" in content_width or "right half" in content_width:
                    return "split-right"
                if "full" in content_width and "frame" in content_width:
                    return "full"

    if composition == "TitleCard":
        return "full"
    if composition == "FactCard":
        return "split-right"
    return "full"


def parse_remotion_fields(segment: dict[str, Any]) -> dict[str, Any]:
    """Return normalized Remotion render instructions for a segment."""
    explicit = segment.get("remotion")
    if not isinstance(explicit, dict):
        explicit = {}

    composition = str(explicit.get("composition") or "").strip()
    raw_type = _raw_type_value(segment)

    if not composition:
        if raw_type.lower().startswith(REMOTION_TYPE_PREFIX):
            composition = _composition_slug_to_id(raw_type[len(REMOTION_TYPE_PREFIX) :])
        elif isinstance(segment.get("type"), list):
            parts = [str(part).strip() for part in segment["type"]]
            if len(parts) >= 2 and parts[0].lower() == "remotion":
                composition = _composition_slug_to_id(parts[1])
        if not composition:
            composition = "FactCard"

    if composition not in KNOWN_REMOTION_COMPOSITIONS:
        composition = _composition_slug_to_id(composition)
        if composition not in KNOWN_REMOTION_COMPOSITIONS:
            composition = "FactCard"

    content = str(segment.get("content", "")).strip()
    label = str(segment.get("label", "")).strip()
    description = str(segment.get("description", "")).strip()

    props: dict[str, Any] = {}
    explicit_props = explicit.get("props")
    if isinstance(explicit_props, dict):
        props.update(explicit_props)

    if composition == "FactCard":
        if "factNumber" not in props:
            inferred = _infer_fact_number(content, label)
            if inferred is not None:
                props["factNumber"] = inferred
        if props.get("factNumber") is None:
            props.pop("factNumber", None)
            props.setdefault("showFactBadge", False)
        props.setdefault("title", _infer_title(content, label, description))
        body = re.sub(r"^fact\s+[\w-]+\s*[.:—-]\s*", "", content, flags=re.IGNORECASE)
        props.setdefault("body", body.strip() or content)
    elif composition == "TitleCard":
        props.setdefault("title", _infer_title(content, label, description))
        props.setdefault("subtitle", description or content[:160])

    layout = remotion_layout_mode(segment, composition)
    design = explicit.get("design")
    prompt = explicit.get("prompt")
    if isinstance(prompt, str):
        prompt = prompt.strip() or None
    else:
        prompt = None

    result: dict[str, Any] = {
        "composition": composition,
        "props": props,
        "layout": layout,
    }
    if isinstance(design, dict) and design:
        result["design"] = design
    if prompt:
        result["prompt"] = prompt
    if layout in {"split-right", "overlay"}:
        result["broll"] = {
            "search_query": remotion_broll_search_query(segment),
            "category": remotion_broll_category(segment),
        }
    overlay = explicit.get("overlay")
    if layout == "overlay":
        if isinstance(overlay, dict) and overlay:
            result["overlay"] = overlay
        else:
            result["overlay"] = {"position": "lower-third"}
    return result


def remotion_payload_from_render(render: dict[str, Any]) -> dict[str, Any] | None:
    if render.get("mode") != "remotion":
        return None
    keys = ("composition", "props", "design", "prompt", "layout", "broll", "overlay")
    return {key: render[key] for key in keys if key in render}


def parse_segment_render(segment: dict[str, Any]) -> dict[str, Any]:
    if is_remotion_segment(segment):
        remotion = parse_remotion_fields(segment)
        return {
            "mode": "remotion",
            **remotion,
        }
    search_query, category = parse_segment_broll_fields(segment)
    return {
        "mode": "broll",
        "search_query": search_query,
        "category": category,
    }


def detect_script_format(script_data: dict[str, Any]) -> str:
    """Return ``folder`` when every typed segment uses a string ``type``."""
    kinds: set[str] = set()
    for beat_block in script_data.get("script", []):
        for segment in beat_block.get("segments", []):
            if is_remotion_segment(segment):
                kinds.add("remotion")
                continue
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


def analyze_script_remotion(script_data: dict[str, Any]) -> dict[str, Any]:
    """Summarize Remotion segments in a script payload."""
    compositions: set[str] = set()
    remotion_ids: list[int] = []
    total = 0

    for beat_block in script_data.get("script", []):
        for segment in beat_block.get("segments", []):
            if "segment_id" not in segment or "content" not in segment:
                continue
            total += 1
            if not is_remotion_segment(segment):
                continue
            remotion_ids.append(int(segment["segment_id"]))
            compositions.add(parse_remotion_fields(segment)["composition"])

    return {
        "detected": bool(remotion_ids),
        "segment_count": len(remotion_ids),
        "segment_ids": remotion_ids,
        "compositions": sorted(compositions),
        "total_segments": total,
        "broll_segment_count": max(0, total - len(remotion_ids)),
    }


def validate_script_payload(script_data: dict[str, Any]) -> None:
    if not isinstance(script_data, dict):
        raise ValueError("Script JSON must be an object.")
    beats = script_data.get("script")
    if not isinstance(beats, list) or not beats:
        raise ValueError("Script must include a non-empty 'script' array.")

    seen_ids: set[int] = set()
    for beat_index, beat_block in enumerate(beats):
        if not isinstance(beat_block, dict):
            raise ValueError(f"Beat block {beat_index + 1} must be an object.")
        segments = beat_block.get("segments")
        if not isinstance(segments, list) or not segments:
            raise ValueError(f"Beat block {beat_index + 1} must include segments.")
        for segment in segments:
            if not isinstance(segment, dict):
                raise ValueError("Each segment must be an object.")
            if "segment_id" not in segment:
                raise ValueError("Each segment needs a segment_id.")
            segment_id = int(segment["segment_id"])
            if segment_id in seen_ids:
                raise ValueError(f"Duplicate segment_id: {segment_id}")
            seen_ids.add(segment_id)
            if not str(segment.get("content", "")).strip():
                raise ValueError(f"Segment {segment_id} is missing content.")
            if is_remotion_segment(segment):
                composition = parse_remotion_fields(segment)["composition"]
                if composition not in KNOWN_REMOTION_COMPOSITIONS:
                    allowed = ", ".join(sorted(KNOWN_REMOTION_COMPOSITIONS))
                    raise ValueError(
                        f"Segment {segment_id} uses unknown Remotion composition "
                        f"'{composition}'. Supported: {allowed}."
                    )


def iter_content_segments(script_data: dict[str, Any]) -> list[tuple[int, str]]:
    """Return narration text segments sorted by segment_id (format-agnostic)."""
    segments: list[tuple[int, str]] = []
    for beat_block in script_data.get("script", []):
        for segment in beat_block.get("segments", []):
            if "content" not in segment:
                continue
            text = str(segment["content"]).strip()
            if not text:
                continue
            segment_id = int(segment.get("segment_id", len(segments) + 1))
            segments.append((segment_id, text))
    segments.sort(key=lambda item: item[0])
    return segments


def build_narration_transcript(script_data: dict[str, Any], *, separator: str = " ") -> str:
    """Join all segment content into one narration string."""
    parts = [text for _, text in iter_content_segments(script_data)]
    if not parts:
        raise ValueError("No segment content found in script.")
    return separator.join(parts)


def iter_broll_script_segments(script_data: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for beat_block in script_data.get("script", []):
        beat = beat_block.get("beat")
        label = beat_block.get("label")
        for segment in beat_block.get("segments", []):
            if "segment_id" not in segment or "content" not in segment:
                continue
            render = parse_segment_render(segment)
            search_query, category = parse_segment_broll_fields(segment)
            if render["mode"] == "remotion" and render.get("layout") in {"split-right", "overlay"}:
                broll = render.get("broll") or {}
                search_query = str(broll.get("search_query") or search_query).strip()
                category = str(broll.get("category") or category or "stock").strip()
            segments.append(
                {
                    "segment_id": segment["segment_id"],
                    "beat": beat,
                    "label": label,
                    "content": segment.get("content", ""),
                    "description": segment.get("description", ""),
                    "search_query": search_query,
                    "category": category,
                    "render_mode": render["mode"],
                    "remotion": (
                        {
                            key: render[key]
                            for key in (
                                "composition",
                                "props",
                                "design",
                                "prompt",
                                "layout",
                                "broll",
                                "overlay",
                            )
                            if key in render
                        }
                        if render["mode"] == "remotion"
                        else None
                    ),
                }
            )
    segments.sort(key=lambda item: item["segment_id"])
    return segments
