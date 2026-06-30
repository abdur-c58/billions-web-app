"""Generate two A/B YouTube thumbnail image prompts via OpenAI."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from youtube_description import _script_context

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
THUMBNAIL_MODEL = "gpt-4o-mini"

# Proven formats from vidIQ's 2026 thumbnail guide:
# https://vidiq.com/blog/post/types-youtube-thumbnails/
THUMBNAIL_FORMATS = """
Proven YouTube thumbnail FORMATS (pick the best fit for this video):
1. Burning Question — curiosity hook as bold on-image text
2. Facts and Stats — one dominant number or stat
3. Before-and-After — split frame transformation
4. Versus Comparison — two subjects side by side, labeled
5. Quotes or Sound Bites — short provocative quote from the video (≤3 words on image)
6. Close-Up Reactions — genuine face reaction + one contextual element (not over-the-top shock)
7. High-Energy Action Shots — bold, colorful peak moment
8. Featured Products — hero product/object close-up
9. Humor/Satire — witty, unexpected visual
10. Stunning Landscapes — epic location as hero
11. Emotional Moments — heartfelt, human moment
12. Tutorial/How-to — highlight the result or payoff, not a bland step screenshot

2026 VISUAL STYLES (pair with a format):
- Neo-minimalist: one subject, ~50% empty space, ≤2 colors, high contrast
- Anti-Thumb: dark, quiet, serious, minimal text, tight concrete hook
- Candid Fake: slightly imperfect, human, not hyper-polished studio
- Trust the Interface: mimics familiar UI (Reddit/Twitter/App Store) when curiosity-driven
- Cinematic text: ≤3 words embedded in the scene (lighting/shadow), not a floating overlay

Best practices:
- Max 3 words of on-image text; readable at mobile thumbnail size
- One clear focal point; high contrast; avoid clutter
- Keep faces, text, and key details OUT of the bottom-right corner (YouTube duration badge)
- Thumbnail creates curiosity; it should complement the title, not repeat it verbatim
""".strip()


def _openai_thumbnail_prompts(*, title: str, narration: str) -> list[dict[str, str]]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    display_title = title or "Untitled video"
    prompt = (
        "You are a YouTube thumbnail strategist. Create TWO distinct A/B test thumbnail "
        "prompts for AI image generation (Midjourney, DALL·E, Ideogram, etc.).\n\n"
        f"Video title: {display_title}\n\n"
        "Script / narration (for context only):\n"
        f"{narration or display_title}\n\n"
        f"{THUMBNAIL_FORMATS}\n\n"
        "Task:\n"
        "- Choose TWO different formats/styles that fit THIS video best (do not pick the same format twice)\n"
        "- Each prompt must be a complete, paste-ready image-generation prompt (English)\n"
        "- Include: aspect ratio 16:9, composition, subject, lighting, color palette, "
        "on-image text (≤3 words) if any, and what to avoid (bottom-right clutter, tiny text)\n"
        "- Prompts must be accurate to the video — no misleading clickbait\n"
        "- Variation A and B should feel meaningfully different for a real A/B test\n\n"
        "Return JSON only:\n"
        '{"prompts":[{"label":"A","style":"...","visual_approach":"...","rationale":"...",'
        '"prompt":"..."},{"label":"B","style":"...","visual_approach":"...","rationale":"...",'
        '"prompt":"..."}]}'
    )

    body = json.dumps(
        {
            "model": THUMBNAIL_MODEL,
            "temperature": 0.75,
            "max_tokens": 1800,
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
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {raw}") from exc

    message = payload["choices"][0]["message"]["content"]
    parsed = json.loads(message)
    raw_prompts = parsed.get("prompts") or []
    if not isinstance(raw_prompts, list) or len(raw_prompts) < 2:
        raise RuntimeError("OpenAI did not return two thumbnail prompts")

    results: list[dict[str, str]] = []
    for index, item in enumerate(raw_prompts[:2]):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or ("A" if index == 0 else "B")).strip().upper()
        style = str(item.get("style") or "").strip()
        visual = str(item.get("visual_approach") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        image_prompt = str(item.get("prompt") or "").strip()
        if not image_prompt:
            continue
        results.append(
            {
                "label": label[:1] if label else ("A" if index == 0 else "B"),
                "style": style or "Custom",
                "visual_approach": visual,
                "rationale": rationale,
                "prompt": image_prompt,
            }
        )

    if len(results) < 2:
        raise RuntimeError("OpenAI returned incomplete thumbnail prompts")
    return results


def build_thumbnail_prompts(
    *,
    script_path: Path,
    project_name: str = "",
) -> list[dict[str, str]]:
    title, narration = _script_context(script_path)
    if not title:
        title = str(project_name or "").strip() or "Video"
    return _openai_thumbnail_prompts(title=title, narration=narration)
