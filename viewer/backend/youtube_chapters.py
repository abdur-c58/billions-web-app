"""YouTube chapter timestamps from script beats + OpenAI title cleanup."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai_http import openai_json_message

CHAPTER_MODEL = "gpt-4o-mini"

_TEASE_PATTERN = re.compile(
    r"\b(tease|retention|hook\s*tease|mid[\s-]*video|subscribe|cta|outro)\b",
    re.IGNORECASE,
)
_NUMBERED_BEAT = re.compile(r"number\s*(\d+)", re.IGNORECASE)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def format_youtube_timestamp(total_seconds: float) -> str:
    rounded = max(0, int(total_seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def collect_beat_chapters(timestamps_path: Path) -> list[dict[str, Any]]:
    """One chapter candidate per beat using the first segment's start time."""
    timestamps_data = _read_json(timestamps_path, {})
    segments = timestamps_data.get("segments", [])
    if not segments:
        raise ValueError("No segments found in timestamps file.")

    chapters: list[dict[str, Any]] = []
    seen_beats: set[int] = set()

    for segment in sorted(segments, key=lambda item: item.get("segment_id") or 0):
        beat = segment.get("beat")
        if beat is None:
            continue
        beat_id = int(beat)
        if beat_id in seen_beats:
            continue

        timing = segment.get("timing") or {}
        start_seconds = timing.get("start_seconds")
        if start_seconds is None:
            continue

        seen_beats.add(beat_id)
        chapters.append(
            {
                "beat": beat_id,
                "label": str(segment.get("label") or f"Beat {beat_id}").strip(),
                "segment_id": segment.get("segment_id"),
                "start_seconds": float(start_seconds),
            }
        )

    if not chapters:
        raise ValueError("Could not resolve any beat start times.")

    chapters.sort(key=lambda item: item["start_seconds"])
    return chapters


def _beat_narration_snippets(script_data: dict[str, Any]) -> dict[int, str]:
    snippets: dict[int, str] = {}
    for beat_block in script_data.get("script", []):
        beat = beat_block.get("beat")
        if beat is None:
            continue
        parts: list[str] = []
        for segment in beat_block.get("segments", []):
            content = str(segment.get("content") or "").strip()
            if content:
                parts.append(content)
        if parts:
            snippets[int(beat)] = " ".join(parts)[:280]
    return snippets


def _heuristic_chapter_titles(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fallback when OpenAI is unavailable."""
    included: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters):
        label = str(chapter.get("label") or "").strip()
        if index > 0 and _TEASE_PATTERN.search(label):
            continue
        title = "Intro" if index == 0 else label
        included.append({**chapter, "title": title})

    if included:
        included[0]["title"] = "Intro"
        _apply_number_one_title(included, chapters)
    return included


def _extract_number_one_subject(label: str) -> str:
    cleaned = re.sub(r"^number\s*1\s*[-–—:]\s*", "", label, flags=re.IGNORECASE).strip()
    return cleaned or label.strip()


def _apply_number_one_title(
    included: list[dict[str, Any]],
    all_chapters: list[dict[str, Any]],
) -> None:
    """If this is a countdown list, ensure the #1 beat uses 'Number 1 - …'."""
    numbered = [
        (ch["beat"], _NUMBERED_BEAT.search(str(ch.get("label") or "")))
        for ch in all_chapters
        if _NUMBERED_BEAT.search(str(ch.get("label") or ""))
    ]
    if len(numbered) < 2:
        return

    numbers = [int(match.group(1)) for _, match in numbered if match]
    if not numbers or min(numbers) != 1:
        return

    one_beat = next((beat for beat, match in numbered if match and int(match.group(1)) == 1), None)
    if one_beat is None:
        return

    for entry in included:
        if entry["beat"] == one_beat:
            raw_label = next(
                (str(ch.get("label") or "") for ch in all_chapters if ch["beat"] == one_beat),
                entry.get("title", ""),
            )
            subject = _extract_number_one_subject(raw_label)
            entry["title"] = f"Number 1 — {subject}"
            break


def _openai_chapter_titles(
    *,
    title: str,
    chapters: list[dict[str, Any]],
    script_data: dict[str, Any],
) -> list[dict[str, Any]]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _heuristic_chapter_titles(chapters)

    snippets = _beat_narration_snippets(script_data)
    beat_lines: list[str] = []
    for chapter in chapters:
        beat = chapter["beat"]
        snippet = snippets.get(beat, "")
        beat_lines.append(
            f"- beat {beat} @ {format_youtube_timestamp(chapter['start_seconds'])}: "
            f'label="{chapter["label"]}"'
            + (f' | narration: "{snippet}"' if snippet else "")
        )

    prompt = (
        "Select and rename YouTube video chapters for this documentary.\n\n"
        f"Video title: {title or 'Untitled'}\n\n"
        "Beat list (in playback order):\n"
        + "\n".join(beat_lines)
        + "\n\nRules:\n"
        '- Include ONLY beats that are real viewer-facing sections of the video.\n'
        "- EXCLUDE beats that are retention teases, mid-video hooks, subscribe reminders, "
        'meta production beats, or anything labeled with "tease" that is not actual content.\n'
        '- The FIRST included chapter must be titled exactly: Intro\n'
        "- Use short, clean YouTube chapter titles (no 'Beat 3', no JSON jargon).\n"
        "- If this is a ranked/countdown video (Number 10, Number 9, … Number 1), keep countdown "
        'entries but title the final #1 entry as: Number 1 — {topic} (use an em dash).\n'
        "- Preserve chronological order by beat number / timestamp.\n\n"
        'Return JSON only: {"chapters":[{"beat":1,"title":"Intro"}, ...]}'
    )

    parsed = openai_json_message(
        model=CHAPTER_MODEL,
        prompt=prompt,
        temperature=0.2,
        max_tokens=1200,
        timeout=90,
    )
    raw_items = parsed.get("chapters") or []
    if not isinstance(raw_items, list) or not raw_items:
        return _heuristic_chapter_titles(chapters)

    by_beat = {int(ch["beat"]): ch for ch in chapters}
    included: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        try:
            beat = int(item.get("beat"))
        except (TypeError, ValueError):
            continue
        if beat not in by_beat:
            continue
        title_text = str(item.get("title") or "").strip() or str(by_beat[beat]["label"])
        if index == 0:
            title_text = "Intro"
        included.append(
            {
                "beat": beat,
                "title": title_text,
                "start_seconds": by_beat[beat]["start_seconds"],
                "label": by_beat[beat]["label"],
            }
        )

    if not included:
        return _heuristic_chapter_titles(chapters)

    included[0]["title"] = "Intro"
    _apply_number_one_title(included, chapters)
    included.sort(key=lambda item: item["start_seconds"])
    return included


def build_chapter_lines(chapters: list[dict[str, Any]]) -> list[str]:
    return [
        f"{format_youtube_timestamp(chapter['start_seconds'])} {chapter['title']}"
        for chapter in chapters
    ]


def build_youtube_chapters_block(
    *,
    script_path: Path,
    timestamps_path: Path,
    project_name: str = "",
) -> str:
    script_data = _read_json(script_path, {})
    title = str(script_data.get("title") or project_name or "").strip()
    raw_chapters = collect_beat_chapters(timestamps_path)
    curated = _openai_chapter_titles(
        title=title,
        chapters=raw_chapters,
        script_data=script_data,
    )
    lines = build_chapter_lines(curated)
    return "Chapters:\n" + "\n".join(lines)
