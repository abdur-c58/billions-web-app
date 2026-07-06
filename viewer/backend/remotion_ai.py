#!/usr/bin/env python3
"""Turn natural-language layout prompts into Remotion composition props."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai_http import openai_json_message
from remotion_schemas import prop_docs_for_composition, sanitize_remotion_props

REMOTION_AI_MODEL = "gpt-4o-mini"


def _heuristic_props(composition: str, prompt: str) -> dict[str, Any]:
    """Cheap fallback when OpenAI is unavailable."""
    text = prompt.lower()
    props: dict[str, Any] = {}

    if re.search(r"\b(centered?|centred|middle)\b", text):
        props["textAlign"] = "center"
        if re.search(r"\b(vertical|vertically)\b", text) or re.search(
            r"\bcenter(ed)?\s+(everything|all|text)\b", text
        ):
            props["verticalAlign"] = "center"
    if re.search(r"\b(left aligned|align left|left side)\b", text):
        props["textAlign"] = "left"
    if re.search(r"\b(right aligned|align right|right side)\b", text):
        props["textAlign"] = "right"
    if re.search(r"\b(top|upper)\b", text):
        props["verticalAlign"] = "top"
    if re.search(r"\b(bottom|lower)\b", text):
        props["verticalAlign"] = "bottom"

    if re.search(r"\b(smaller|reduce|compact)\b", text):
        if composition == "FactCard":
            props["titleSize"] = 56
            props["bodySize"] = 28
        else:
            props["titleSize"] = 68
            props["subtitleSize"] = 30
    if re.search(r"\b(larger|bigger|hero|large text)\b", text):
        if composition == "FactCard":
            props["titleSize"] = 80
            props["bodySize"] = 38
        else:
            props["titleSize"] = 96
            props["subtitleSize"] = 42

    if re.search(r"\b(more padding|more space|spacious)\b", text):
        props["padding"] = 140
    if re.search(r"\b(less padding|tight|compact layout)\b", text):
        props["padding"] = 64

    if re.search(r"\b(brown|tan|sepia)\b", text) and re.search(r"\bgradient|background\b", text):
        props["backgroundGradient"] = (
            "linear-gradient(145deg, #2a1810 0%, #4a2c1a 55%, #3d2318 100%)"
        )
    elif re.search(r"\b(blue|navy)\b", text) and re.search(r"\bgradient|background\b", text):
        props["backgroundGradient"] = (
            "linear-gradient(160deg, #05070d 0%, #10182a 55%, #1a2744 100%)"
        )
    elif re.search(r"\b(black|dark)\b", text) and re.search(r"\bgradient|background\b", text):
        props["backgroundGradient"] = (
            "linear-gradient(145deg, #050505 0%, #121212 55%, #1a1a1a 100%)"
        )

    for color_name, hex_value in (
        ("green", "#5ecf8a"),
        ("blue", "#7db7ff"),
        ("purple", "#a78bfa"),
        ("brown", "#a66b3f"),
        ("red", "#f87171"),
        ("gold", "#fbbf24"),
        ("white", "#f4f7fb"),
    ):
        if re.search(rf"\b{re.escape(color_name)}\b", text):
            props["accentColor"] = hex_value
            break

    return sanitize_remotion_props(composition, props)


def _build_prompt(
    *,
    composition: str,
    segment_content: str,
    segment_description: str,
    current_props: dict[str, Any],
    user_prompt: str,
) -> str:
    allowed = prop_docs_for_composition(composition)
    schema_lines = "\n".join(f'- "{key}": {desc}' for key, desc in allowed.items())
    current_json = json.dumps(current_props, ensure_ascii=False, indent=2)

    return f"""You adjust Remotion motion-graphic cards for a documentary YouTube video.

Composition: {composition}
Segment narration excerpt:
{segment_content[:600]}

Visual brief:
{segment_description[:300] or "(none)"}

Current props (JSON):
{current_json}

User request:
{user_prompt.strip()}

Return JSON with exactly these keys:
{{
  "props": {{ ...only props to change... }},
  "summary": "one short sentence explaining what you changed"
}}

Rules:
- Only use these prop keys for {composition}:
{schema_lines}
- Include ONLY keys you are changing; omit unchanged keys.
- You may set any documented prop key, plus other safe camelCase keys supported by the composition.
- Do not invent new keys.
- Keep copy edits concise and readable on screen.
- Prefer layout changes (align, padding, sizes, accentColor) unless the user explicitly asks to rewrite text.
- Colors must be hex (#rrggbb).
"""


def suggest_remotion_props(
    *,
    composition: str,
    segment_content: str,
    segment_description: str,
    current_props: dict[str, Any],
    user_prompt: str,
    ai_budget: Any | None = None,
) -> dict[str, Any]:
    prompt = (user_prompt or "").strip()
    if not prompt:
        raise ValueError("Describe how the motion segment should look.")

    base = dict(current_props or {})
    if not os.environ.get("OPENAI_API_KEY"):
        updates = _heuristic_props(composition, prompt)
        if not updates:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Set it for AI layout suggestions, "
                "or use simple phrases like 'center text' or 'more padding'."
            )
        merged = {**base, **updates}
        return {
            "props": sanitize_remotion_props(composition, merged),
            "updates": updates,
            "summary": "Applied keyword-based layout tweaks (no OpenAI key).",
            "ai_used": False,
        }

    if ai_budget is not None and not ai_budget.can_use():
        raise RuntimeError(
            f"Daily AI budget exhausted ({ai_budget.max_calls} calls). Try again tomorrow "
            "or edit fields manually."
        )

    parsed = openai_json_message(
        model=REMOTION_AI_MODEL,
        prompt=_build_prompt(
            composition=composition,
            segment_content=segment_content,
            segment_description=segment_description,
            current_props=base,
            user_prompt=prompt,
        ),
        temperature=0.35,
        max_tokens=500,
        timeout=60,
    )

    raw_updates = parsed.get("props")
    if not isinstance(raw_updates, dict):
        raw_updates = {}

    updates = sanitize_remotion_props(composition, raw_updates)
    merged = {**base, **updates}

    if ai_budget is not None:
        ai_budget.consume()

    summary = str(parsed.get("summary") or "").strip()
    if not summary:
        summary = (
            f"Updated {len(updates)} prop(s) from your prompt."
            if updates
            else "No prop changes were suggested."
        )

    return {
        "props": sanitize_remotion_props(composition, merged),
        "updates": updates,
        "summary": summary,
        "ai_used": True,
    }
