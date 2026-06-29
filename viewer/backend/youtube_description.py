"""Generate a YouTube-ready description via OpenAI from the video script."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
DESCRIPTION_MODEL = "gpt-4o-mini"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _script_context(script_path: Path) -> tuple[str, str]:
    script_data = _read_json(script_path, {})
    title = str(script_data.get("title") or "").strip()

    sections: list[str] = []
    for beat_block in script_data.get("script", []):
        label = str(beat_block.get("label") or "").strip()
        lines: list[str] = []
        for segment in beat_block.get("segments", []):
            content = str(segment.get("content") or "").strip()
            if content:
                lines.append(content)
        if not lines:
            continue
        body = " ".join(lines)
        sections.append(f"{label}\n{body}" if label else body)

    narration = "\n\n".join(sections).strip()
    if len(narration) > 14_000:
        narration = narration[:14_000] + "…"
    return title, narration


def _format_hashtags(tags: list[str]) -> str:
    formatted: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = re.sub(r"[^a-zA-Z0-9]+", "", str(raw).strip().lstrip("#"))
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        formatted.append(f"#{tag}")
    return " ".join(formatted)


def _openai_youtube_copy(
    *,
    title: str,
    narration: str,
    include_emojis: bool = True,
) -> tuple[str, list[str]]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    display_title = title or "Untitled video"
    emoji_rule = (
        "- Use a few relevant emojis (roughly 3–6 across the whole description)\n"
        if include_emojis
        else "- Do NOT use any emojis anywhere in the description\n"
    )
    prompt = (
        "Write a YouTube video description for this documentary-style video.\n\n"
        f"Title: {display_title}\n\n"
        "Full narration (for your understanding only):\n"
        f"{narration or display_title}\n\n"
        "Output rules:\n"
        "- Natural English only — write for viewers, not producers\n"
        f"{emoji_rule}"
        "- The first 200 characters MUST pack in strong SEO keywords for this topic\n"
        "- 2–4 short paragraphs: hook, what viewers learn, why it matters, soft CTA\n"
        "- Do NOT mention beats, segments, JSON, chapters, timestamps, b-roll, "
        "stock footage, clip counts, Pexels, Pixabay, or any production metadata\n"
        "- No bullet lists of script structure\n"
        "- tags: 4–6 short YouTube search tags (single words or 2-word phrases, lowercase, no #)\n\n"
        'Return JSON only: {"description": "...", "tags": ["tag1", "tag2"]}'
    )

    body = json.dumps(
        {
            "model": DESCRIPTION_MODEL,
            "temperature": 0.65,
            "max_tokens": 900,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
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
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {raw}") from exc

    message = payload["choices"][0]["message"]["content"]
    parsed = json.loads(message)
    description = str(parsed.get("description") or "").strip()
    tags = [str(tag).strip() for tag in (parsed.get("tags") or []) if str(tag).strip()]
    if not description:
        raise RuntimeError("OpenAI returned an empty description")
    return description, tags


def build_youtube_description(
    *,
    script_path: Path,
    timestamps_path: Path,
    selections_path: Path,
    project_name: str,
    include_emojis: bool = True,
) -> str:
    """Build a copy-paste YouTube description (body + hashtag line)."""
    del timestamps_path, selections_path  # narration-only; no export metadata in copy

    title, narration = _script_context(script_path)
    if not title:
        title = str(project_name or "").strip() or "Video"

    description, tags = _openai_youtube_copy(
        title=title,
        narration=narration,
        include_emojis=include_emojis,
    )
    hashtag_line = _format_hashtags(tags)
    if hashtag_line:
        return f"{description}\n\n{hashtag_line}"
    return description
