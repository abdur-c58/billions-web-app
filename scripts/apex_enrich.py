"""Post-process Apex Archives scripts for Remotion density and runtime targets."""

from __future__ import annotations

import re
from typing import Any

from apex_helpers import ApexScriptBuilder


def _entry_num(label: str) -> str | None:
    match = re.match(r"Entry #(\d+)", str(label))
    return f"#{match.group(1)}" if match else None


def _is_rank_reveal(seg: dict[str, Any]) -> bool:
    rem = seg.get("remotion") or {}
    return (
        str(seg.get("type", "")).startswith("remotion")
        and rem.get("layout") == "full"
        and rem.get("composition") == "TitleCard"
        and bool((rem.get("props") or {}).get("factNumber"))
    )


def _entry_name(label: str) -> str:
    parts = str(label).split(" - ", 1)
    return parts[1] if len(parts) > 1 else label


def remotion_segments(script_data: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for beat in script_data.get("script", []):
        for seg in beat.get("segments", []):
            if isinstance(seg.get("type"), str) and seg["type"].startswith("remotion"):
                found.append(seg)
    return found


def word_count(script_data: dict[str, Any]) -> int:
    total = 0
    for beat in script_data.get("script", []):
        for seg in beat.get("segments", []):
            total += len(str(seg.get("content", "")).split())
    return total


def trim_segment_text(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    trimmed = words[:max_words]
    if trimmed[-1].endswith((",", ";", "—")):
        trimmed[-1] = trimmed[-1].rstrip(",;—")
    return " ".join(trimmed).strip() + "."


def trim_script_to_target(
    script_data: dict[str, Any],
    target: int = 8610,
    entry_min: int = 700,
) -> dict[str, Any]:
    current = word_count(script_data)
    if current <= target:
        return script_data

    excess = current - target
    non_entry_segments: list[dict[str, Any]] = []
    entry_beats: list[dict[str, Any]] = []

    for beat in script_data.get("script", []):
        if str(beat.get("label", "")).startswith("Entry #"):
            entry_beats.append(beat)
        else:
            for seg in beat.get("segments", []):
                non_entry_segments.append(seg)

    non_entry_words = sum(len(str(s.get("content", "")).split()) for s in non_entry_segments)
    trim_non_entry = min(non_entry_words // 8, excess // 3)
    for seg in non_entry_segments:
        words = str(seg.get("content", "")).split()
        if trim_non_entry <= 0:
            break
        cut = min(trim_non_entry, max(0, len(words) - 40))
        if cut:
            seg["content"] = trim_segment_text(str(seg.get("content", "")), len(words) - cut)
            trim_non_entry -= cut
            excess -= cut

    current = word_count(script_data)
    if current <= target:
        return script_data

    for beat in entry_beats:
        segments = beat.get("segments", [])
        entry_words = sum(len(str(s.get("content", "")).split()) for s in segments)
        if entry_words <= entry_min:
            continue
        removable = entry_words - entry_min
        need = current - target
        if need <= 0:
            break
        cut_total = min(removable, need)
        ratio = cut_total / entry_words
        for seg in segments:
            content = str(seg.get("content", ""))
            words = content.split()
            cut = int(len(words) * ratio)
            if cut > 0:
                seg["content"] = trim_segment_text(content, max(35, len(words) - cut))
        current = word_count(script_data)

    return script_data


def enrich_remotion(script_data: dict[str, Any]) -> dict[str, Any]:
    """Ensure ~22-28 Remotion segments via per-entry stat overlays and mid-list split cards."""
    builder = ApexScriptBuilder()
    max_id = 0
    for beat in script_data.get("script", []):
        for seg in beat.get("segments", []):
            max_id = max(max_id, int(seg.get("segment_id", 0)))
    builder._sid = max_id

    for beat in script_data.get("script", []):
        label = str(beat.get("label", ""))
        if not label.startswith("Entry #"):
            continue

        segments = beat.get("segments", [])
        if not segments:
            continue

        name = _entry_name(label)
        num = _entry_num(label) or ""
        rank_seg = segments[0] if _is_rank_reveal(segments[0]) else None
        stat_line = ""
        if rank_seg:
            stat_line = str((rank_seg.get("remotion") or {}).get("props", {}).get("subtitle", ""))

        has_overlay_stat = any(
            str(s.get("type", "")).startswith("remotion")
            and (s.get("remotion") or {}).get("layout") == "overlay"
            and (s.get("remotion") or {}).get("composition") == "FactCard"
            and not any(
                kw in str(((s.get("remotion") or {}).get("props") or {}).get("title", "")).lower()
                for kw in ("subscribe", "like", "coming", "still")
            )
            for s in segments
        )
        has_split = any((s.get("remotion") or {}).get("layout") == "split-right" for s in segments)

        stock_indices = [
            i
            for i, s in enumerate(segments)
            if isinstance(s.get("type"), list) and i > 0
        ]
        query = "wildlife documentary b-roll"
        if stock_indices:
            first_stock = segments[stock_indices[0]]
            if isinstance(first_stock.get("type"), list):
                query = first_stock["type"][0]

        insert_at = stock_indices[3] + 1 if len(stock_indices) >= 4 else len(segments)

        if not has_overlay_stat:
            stat_title = name.upper() if len(name) < 28 else name
            stat_body = stat_line or f"Key data point for {name} in this ranking."
            overlay = builder.overlay_stat(
                f"The sourced figure for {name} appears on screen while this habitat shot continues — "
                f"the number is {stat_line.lower() if stat_line else 'on the ranking card'}. "
                f"Viewers who only remember the animal name still leave with the scale.",
                f"Quick stat overlay for {name}",
                query,
                stat_title,
                stat_body,
                position="center",
            )
            segments.insert(insert_at, overlay)

        if num in {"#5", "#2"} and not has_split:
            split = builder.split_card(
                f"At {num}, the ranking logic shifts — comparisons that felt academic at number ten "
                f"become personal stakes here. {name} is not a footnote; it redefines the scale "
                f"for every entry still ahead on the countdown.",
                f"Split comparison panel for {name}",
                query,
                "Ranking Scale Shift",
                f"{name} — {stat_line or 'mid-list inflection point'}",
                "Comparison",
            )
            segments.append(split)

        beat["segments"] = segments

    return script_data


def finalize_script(script_data: dict[str, Any], target_words: int = 8610) -> dict[str, Any]:
    script_data = enrich_remotion(script_data)
    script_data = trim_script_to_target(script_data, target=target_words)
    return script_data
