"""Publish queue: finished exports plus everything needed to upload them to YouTube.

Read by the /publish page, which an external bot watches to publish videos
automatically. No AI — every field comes straight from the project's files.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from export_job_state import compute_export_inputs_hash, export_snapshot
from project_manager import workspace_paths
from script_format import script_thumbnail
from user_sessions import PROJECT_ID_RE, project_workspace, projects_root, read_manifest
from youtube_chapters import build_plain_chapters

PUBLISH_STATUS_NAME = ".publish_status.json"

# YouTube only shows chapters when there are at least 3, the first starts at
# 0:00, and every chapter is at least 10 seconds long.
MIN_CHAPTERS = 3
MIN_CHAPTER_SECONDS = 10


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_publish_status(workspace: Path) -> dict[str, Any]:
    return _read_json(workspace / PUBLISH_STATUS_NAME)


def set_published(workspace_root: Path, project_id: str, published: bool) -> dict[str, Any]:
    workspace = project_workspace(workspace_root, project_id)
    if not workspace.is_dir():
        raise ValueError(f"Project not found: {project_id}")
    path = workspace / PUBLISH_STATUS_NAME
    if published:
        status = {"published": True, "published_at": time.time()}
        path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
        status = {"published": False, "published_at": None}
    return status


def thumbnail_brief_text(thumbnail: dict[str, Any]) -> str:
    lines = [str(thumbnail.get("image_prompt") or "").strip()]
    overlay = thumbnail.get("overlay_text") or {}
    if overlay:
        lines.append("")
        lines.append("Overlay text:")
        for key, value in overlay.items():
            lines.append(f"{key.replace('_', ' ').capitalize()}: {value}")
    return "\n".join(lines)


def _chapter_problem(chapters: list[dict[str, Any]], duration_seconds: float | None) -> str | None:
    if len(chapters) < MIN_CHAPTERS:
        return f"YouTube needs at least {MIN_CHAPTERS} chapters; found {len(chapters)}."
    if chapters[0]["start_seconds"] > 0:
        return "First chapter must start at 0:00."
    ends = [chapter["start_seconds"] for chapter in chapters[1:]]
    if duration_seconds:
        ends.append(duration_seconds)
    for chapter, end in zip(chapters, ends):
        if end - chapter["start_seconds"] < MIN_CHAPTER_SECONDS:
            return (
                f'Chapter "{chapter["title"]}" at {chapter["timestamp"]} is shorter than '
                f"{MIN_CHAPTER_SECONDS} seconds."
            )
    return None


def _check(key: str, label: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "ok": bool(ok), "detail": detail}


def build_publish_entry(workspace_root: Path, project_id: str) -> dict[str, Any] | None:
    """Entry for a project whose export has finished, else None."""
    workspace = project_workspace(workspace_root, project_id)
    if not workspace.is_dir():
        return None
    paths = workspace_paths(workspace)
    export = export_snapshot(project_id, paths["export_status"])
    if export.get("status") != "done":
        return None

    script_data = _read_json(paths["script"])
    timestamps_data = _read_json(paths["timestamps"])
    manifest = read_manifest(workspace)

    title = str(script_data.get("title") or timestamps_data.get("title") or "").strip()
    channel = str(script_data.get("channel") or timestamps_data.get("channel") or "").strip()

    video_path = str(export.get("output") or "").strip()
    video_file = Path(video_path) if video_path else None
    video_exists = bool(video_file and video_file.is_file() and video_file.stat().st_size > 0)
    video_size = video_file.stat().st_size if video_exists and video_file else 0

    thumbnail = script_thumbnail(script_data)

    chapters: list[dict[str, Any]] = []
    chapters_error = ""
    if paths["timestamps"].exists():
        try:
            chapters = build_plain_chapters(timestamps_path=paths["timestamps"])
        except Exception as exc:
            chapters_error = str(exc)
    else:
        chapters_error = "Segment timestamps are missing."
    summary = timestamps_data.get("summary") if isinstance(timestamps_data.get("summary"), dict) else {}
    duration = summary.get("total_duration_seconds")
    try:
        duration_seconds = float(duration) if duration else None
    except (TypeError, ValueError):
        duration_seconds = None
    if chapters_error:
        chapter_problem = chapters_error
    elif not chapters:
        chapter_problem = "No content chapters found."
    else:
        chapter_problem = _chapter_problem(chapters, duration_seconds)

    stored_hash = export.get("inputs_hash")
    current_hash = compute_export_inputs_hash(
        timestamps_path=paths["timestamps"],
        selections_path=paths["selections"],
        audio_path=paths["audio"],
    )
    export_current = bool(stored_hash) and stored_hash == current_hash

    checks = [
        _check("export_done", "Export finished", True),
        _check(
            "video_file",
            "Video file exists on disk",
            video_exists,
            "" if video_exists else f"Not found: {video_path or '(no path recorded)'}",
        ),
        _check(
            "export_current",
            "Export matches the latest edits",
            export_current,
            "" if export_current else "B-roll, timing or narration changed after this export. Re-export it.",
        ),
        _check("title", "Title is set", bool(title), "" if title else "Script JSON has no title."),
        _check("channel", "Channel is set", bool(channel), "" if channel else "Script JSON has no channel."),
        _check(
            "thumbnail",
            "Thumbnail prompt is set",
            thumbnail is not None,
            "" if thumbnail else "Script JSON has no thumbnail block.",
        ),
        _check("chapters", "Chapters are valid for YouTube", not chapter_problem, chapter_problem or ""),
    ]
    all_checks_pass = all(check["ok"] for check in checks)

    publish_status = read_publish_status(workspace)
    published = bool(publish_status.get("published"))

    if published:
        state = "published"
    elif all_checks_pass:
        state = "ready"
    else:
        state = "not_ready"

    return {
        "project_id": project_id,
        "project_name": manifest.get("name") or title or project_id,
        "title": title,
        "channel": channel,
        "video_path": video_path,
        "video_exists": video_exists,
        "video_size_bytes": video_size,
        "exported_at": export.get("updated_at"),
        "thumbnail": thumbnail,
        "thumbnail_prompt": thumbnail_brief_text(thumbnail) if thumbnail else "",
        "chapters": chapters,
        "chapters_text": "\n".join(f"{c['timestamp']} {c['title']}" for c in chapters),
        "checks": checks,
        "ready_for_publishing": state == "ready",
        "published": published,
        "published_at": publish_status.get("published_at"),
        "state": state,
    }


def build_publish_queue(workspace_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for child in projects_root(workspace_root).iterdir():
        if not child.is_dir() or not PROJECT_ID_RE.match(child.name):
            continue
        try:
            entry = build_publish_entry(workspace_root, child.name)
        except Exception as exc:
            print(f"[publish] Skipped {child.name}: {exc}")
            continue
        if entry:
            entries.append(entry)
    entries.sort(key=lambda item: float(item.get("exported_at") or 0), reverse=True)
    return entries
