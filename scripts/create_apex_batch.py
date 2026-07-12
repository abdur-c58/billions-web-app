#!/usr/bin/env python3
"""Validate Apex Archives scripts and create project folders with script.json."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "viewer" / "backend"
WORKSPACE = BACKEND / "workspace"
TOPICS_DIR = Path(__file__).resolve().parent / "apex_topics"

sys.path.insert(0, str(BACKEND))


from apex_enrich import finalize_script  # noqa: E402


def load_build_function(module_path: Path):
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise AttributeError(f"{module_path} must define build() -> dict")
    return module.build


def word_count(script_data: dict[str, Any]) -> int:
    total = 0
    for beat in script_data.get("script", []):
        for seg in beat.get("segments", []):
            total += len(str(seg.get("content", "")).split())
    return total


def remotion_segments(script_data: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for beat in script_data.get("script", []):
        for seg in beat.get("segments", []):
            if isinstance(seg.get("type"), str) and seg["type"].startswith("remotion"):
                found.append(seg)
    return found


def entry_beats(script_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        beat
        for beat in script_data.get("script", [])
        if str(beat.get("label", "")).startswith("Entry #")
    ]


def validate_script(script_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if "script" not in script_data or "segments" in script_data:
        errors.append("Top-level must contain `script`, not `segments`.")

    total = word_count(script_data)
    if total < 8000:
        errors.append(f"Word count {total} is under 8,000 minimum.")

    entries = entry_beats(script_data)
    if len(entries) != 10:
        errors.append(f"Expected 10 numbered entries, found {len(entries)}.")

    for beat in entries:
        entry_words = sum(len(str(s.get("content", "")).split()) for s in beat.get("segments", []))
        if entry_words < 700:
            errors.append(f"{beat.get('label')} has only {entry_words} words (minimum 700).")
        reveals = [
            s
            for s in beat.get("segments", [])
            if isinstance(s.get("type"), str)
            and s["type"].startswith("remotion")
            and (s.get("remotion") or {}).get("layout") == "full"
            and (s.get("remotion") or {}).get("composition") == "TitleCard"
        ]
        if not reveals:
            errors.append(f"{beat.get('label')} missing full TitleCard rank reveal.")
        elif not (reveals[0].get("remotion", {}).get("props") or {}).get("factNumber"):
            errors.append(f"{beat.get('label')} rank reveal missing factNumber.")

    remotion = remotion_segments(script_data)
    if len(remotion) < 22:
        errors.append(f"Only {len(remotion)} Remotion segments (minimum ~22).")
    if len(remotion) > 35:
        errors.append(f"{len(remotion)} Remotion segments exceeds maximum 35.")

    overlay_ctas = [
        s
        for s in remotion
        if (s.get("remotion") or {}).get("layout") == "overlay"
        and any(
            kw in str(((s.get("remotion") or {}).get("props") or {}).get("title", "")).lower()
            for kw in ("subscribe", "like")
        )
    ]
    if len(overlay_ctas) < 2:
        errors.append("Need at least 2 overlay subscribe/like CTAs.")

    for seg in script_data.get("script", [{}])[0].get("segments", []):
        pass  # hook CTA checked below

    hook_cta = False
    for beat in script_data.get("script", []):
        if beat.get("label") == "Hook":
            for seg in beat.get("segments", []):
                rem = seg.get("remotion") or {}
                if rem.get("layout") == "overlay" and "subscribe" in str(
                    (rem.get("props") or {}).get("title", "")
                ).lower():
                    hook_cta = True
    if not hook_cta:
        errors.append("Hook beat missing overlay subscribe CTA.")

    for beat in script_data.get("script", []):
        for seg in beat.get("segments", []):
            seg_type = seg.get("type")
            if isinstance(seg_type, list):
                if len(seg_type) != 2:
                    errors.append(f"Segment {seg.get('segment_id')} has invalid stock type array.")
                if seg_type[1] not in {"stock", "commons"}:
                    errors.append(f"Segment {seg.get('segment_id')} invalid category.")
            elif isinstance(seg_type, str) and seg_type.startswith("remotion"):
                rem = seg.get("remotion") or {}
                if not rem.get("composition") or not rem.get("layout"):
                    errors.append(f"Segment {seg.get('segment_id')} missing remotion composition/layout.")
                if not rem.get("props") or not rem.get("design") or not rem.get("prompt"):
                    errors.append(f"Segment {seg.get('segment_id')} missing props/design/prompt.")
                props = rem.get("props") or {}
                if props.get("fontFamily") != "Anton, Impact, sans-serif":
                    errors.append(f"Segment {seg.get('segment_id')} title font must be Anton.")
                if props.get("bodyFontFamily") != "Barlow Condensed, Arial Narrow, sans-serif":
                    errors.append(f"Segment {seg.get('segment_id')} body font must be Barlow Condensed.")

    title = str(script_data.get("title", ""))
    if len(title.split()) < 8:
        errors.append("Title may be too short/vague for proven formula.")

    return errors


def create_project_with_script(name: str, script_data: dict[str, Any]) -> Path:
    from user_sessions import create_project, project_workspace, touch_manifest

    project = create_project(WORKSPACE, name=name)
    workspace = project_workspace(WORKSPACE, project["id"])
    script_path = workspace / "script.json"
    script_path.write_text(
        json.dumps(script_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    touch_manifest(workspace, name=name)
    return workspace


def process_topic(module_name: str, project_name: str) -> dict[str, Any]:
    module_path = TOPICS_DIR / f"{module_name}.py"
    build = load_build_function(module_path)
    script_data = finalize_script(build(), target_words=8610)
    script_data["channel"] = "Apex Archives"

    errors = validate_script(script_data)
    total = word_count(script_data)
    runtime = round(total / 145, 1)
    remotion_count = len(remotion_segments(script_data))

    if errors:
        raise ValueError(f"{module_name} failed validation:\n" + "\n".join(f"  - {e}" for e in errors))

    workspace = create_project_with_script(project_name, script_data)
    return {
        "module": module_name,
        "project_id": workspace.name,
        "workspace": str(workspace),
        "title": script_data["title"],
        "words": total,
        "runtime_min": runtime,
        "remotion_segments": remotion_count,
    }


def main() -> None:
    topics = [
        ("topic_disease_vectors", "Disease Vectors Ranking"),
        ("topic_harmless_marine", "Harmless-Looking Marine Killers"),
        ("topic_invasive_damage", "Invasive Species Economic Damage"),
        ("topic_extreme_senses", "Extreme Animal Senses Ranking"),
        ("topic_american_killers", "Animals Killing More Americans Than Predators"),
    ]

    results = []
    for module_name, project_name in topics:
        print(f"\n=== {project_name} ({module_name}) ===")
        try:
            result = process_topic(module_name, project_name)
            results.append(result)
            print(f"OK  id={result['project_id']}  words={result['words']}  runtime={result['runtime_min']}m")
            print(f"    {result['title']}")
        except Exception as exc:
            print(f"FAILED: {exc}")
            raise

    print("\n=== BATCH COMPLETE ===")
    for r in results:
        print(f"- [{r['project_id']}] {r['title']} ({r['words']} words, {r['runtime_min']} min)")


if __name__ == "__main__":
    main()
