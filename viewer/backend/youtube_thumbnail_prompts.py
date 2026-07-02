"""Generate two A/B YouTube thumbnail image prompts via OpenAI."""

from __future__ import annotations

from pathlib import Path

from openai_http import openai_json_message
from youtube_description import _script_context

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


def _ensure_youtube_thumbnail_prompt(text: str) -> str:
    """Guarantee the paste-ready prompt names YouTube thumbnail specs."""
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    lower = cleaned.lower()
    has_youtube = "youtube" in lower
    has_thumbnail = "thumbnail" in lower
    has_ratio = "16:9" in lower or "16×9" in lower or "1280" in lower
    if has_youtube and has_thumbnail and has_ratio:
        return cleaned
    prefix = (
        "YouTube video thumbnail, 16:9 aspect ratio (1280×720), "
        "click-optimized for the YouTube home/browse feed. "
    )
    return prefix + cleaned


def _openai_thumbnail_prompts(*, title: str, narration: str) -> list[dict[str, str]]:
    display_title = title or "Untitled video"
    context = narration or display_title
    if len(context) > 8_000:
        context = context[:8_000] + "…"
    prompt = (
        "You are a YouTube thumbnail strategist. Create TWO distinct A/B test thumbnail "
        "prompts for AI image generation (Midjourney, DALL·E, Ideogram, etc.).\n\n"
        f"Video title: {display_title}\n\n"
        "Script / narration (for context only):\n"
        f"{context}\n\n"
        f"{THUMBNAIL_FORMATS}\n\n"
        "Task:\n"
        "- Choose TWO different formats/styles that fit THIS video best (do not pick the same format twice)\n"
        "- Each `prompt` must be a complete, paste-ready AI image-generation prompt (English)\n"
        "- EVERY `prompt` MUST explicitly state it is a **YouTube video thumbnail** (use those words near the start)\n"
        "- EVERY `prompt` MUST include: 16:9 aspect ratio, 1280×720 resolution, optimized for the YouTube home/browse feed\n"
        "- Also include: composition, subject, lighting, color palette, on-image text (≤3 words) if any, "
        "and what to avoid (bottom-right clutter, tiny text, movie poster, generic wallpaper)\n"
        "- Do NOT write a generic scene or movie still — this is specifically a click-optimized YouTube thumbnail\n"
        "- Prompts must be accurate to the video — no misleading clickbait\n"
        "- Variation A and B should feel meaningfully different for a real A/B test\n\n"
        "Example prompt opening: "
        "YouTube video thumbnail, 16:9 (1280x720), click-optimized for the YouTube feed, ...\n\n"
        "Return JSON only:\n"
        '{"prompts":[{"label":"A","style":"...","visual_approach":"...","rationale":"...",'
        '"prompt":"..."},{"label":"B","style":"...","visual_approach":"...","rationale":"...",'
        '"prompt":"..."}]}'
    )

    parsed = openai_json_message(
        model=THUMBNAIL_MODEL,
        prompt=prompt,
        temperature=0.75,
        max_tokens=1800,
        timeout=120,
    )
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
        image_prompt = _ensure_youtube_thumbnail_prompt(image_prompt)
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
