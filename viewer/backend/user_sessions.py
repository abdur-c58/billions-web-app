"""Shared project workspaces under workspace/projects/."""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from project_manager import (
    TIMESTAMPS_JOB_NAME,
    project_status,
    workspace_paths,
)

PROJECT_MANIFEST_NAME = "project.json"
STALE_JOB_SECONDS = 15 * 60
PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def projects_root(workspace_root: Path) -> Path:
    root = workspace_root / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_workspace(workspace_root: Path, project_id: str) -> Path:
    validate_project_id(project_id)
    return projects_root(workspace_root) / project_id


def validate_project_id(project_id: str) -> None:
    if not PROJECT_ID_RE.match(project_id):
        raise ValueError("Invalid project id.")


def parse_workspace_scope(workspace: Path) -> str | None:
    parts = workspace.resolve().parts
    try:
        projects_idx = parts.index("projects")
        project_id = parts[projects_idx + 1]
        if PROJECT_ID_RE.match(project_id):
            return project_id
    except (ValueError, IndexError):
        pass
    # Legacy per-user layout: users/<user>/projects/<id>
    try:
        users_idx = parts.index("users")
        if parts[users_idx + 2] == "projects":
            project_id = parts[users_idx + 3]
            if PROJECT_ID_RE.match(project_id):
                return project_id
    except (ValueError, IndexError):
        pass
    return None


def read_job_state(workspace: Path) -> dict[str, Any] | None:
    path = workspace_paths(workspace)["timestamps_job"]
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as infile:
            payload = json.load(infile)
        return payload if isinstance(payload, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def find_running_project(workspace_root: Path) -> dict[str, Any] | None:
    for entry in list_projects(workspace_root):
        if entry.get("timestamps_job", {}).get("status") == "running":
            return entry
    return None


def read_manifest(workspace: Path) -> dict[str, Any]:
    path = workspace / PROJECT_MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as infile:
            payload = json.load(infile)
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def write_manifest(workspace: Path, payload: dict[str, Any]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / PROJECT_MANIFEST_NAME
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def touch_manifest(workspace: Path, **updates: Any) -> dict[str, Any]:
    manifest = read_manifest(workspace)
    now = time.time()
    manifest.setdefault("created_at", now)
    manifest["updated_at"] = now
    manifest.update(updates)
    write_manifest(workspace, manifest)
    return manifest


def project_summary(workspace_root: Path, project_id: str) -> dict[str, Any]:
    workspace = project_workspace(workspace_root, project_id)
    if not workspace.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")

    manifest = read_manifest(workspace)
    status = project_status(workspace)
    job = status.get("timestamps_job", {})
    name = manifest.get("name") or status.get("title") or f"Project {project_id[:8]}"

    return {
        "id": project_id,
        "name": name,
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "viewer_ready": status.get("viewer_ready", False),
        "next_step": status.get("next_step"),
        "title": status.get("title"),
        "segment_count": status.get("segment_count", 0),
        "aligned_segments": status.get("aligned_segments", 0),
        "timestamps_job": job,
    }


def list_projects(workspace_root: Path) -> list[dict[str, Any]]:
    root = projects_root(workspace_root)
    projects: list[dict[str, Any]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        project_id = child.name
        if not PROJECT_ID_RE.match(project_id):
            continue
        try:
            projects.append(project_summary(workspace_root, project_id))
        except Exception:
            continue

    projects.sort(
        key=lambda item: float(item.get("updated_at") or item.get("created_at") or 0),
        reverse=True,
    )
    return projects


def create_project(
    workspace_root: Path,
    name: str | None = None,
    *,
    created_by: str | None = None,
) -> dict[str, Any]:
    project_id = uuid.uuid4().hex[:12]
    workspace = project_workspace(workspace_root, project_id)
    workspace.mkdir(parents=True, exist_ok=False)
    label = (name or "New project").strip() or "New project"
    manifest: dict[str, Any] = {"id": project_id, "name": label}
    if created_by:
        manifest["created_by"] = created_by
    touch_manifest(workspace, **manifest)
    return project_summary(workspace_root, project_id)


def migrate_legacy_workspace(workspace_root: Path) -> None:
    """Move flat workspace/ files into projects/legacy/."""
    legacy_markers = (
        workspace_root / "script.json",
        workspace_root / "script.mp3",
        workspace_root / "segment_timestamps.json",
    )
    if not any(path.exists() for path in legacy_markers):
        return

    legacy_dest = project_workspace(workspace_root, "legacy")
    if legacy_dest.exists() and any(legacy_dest.iterdir()):
        return

    legacy_dest.mkdir(parents=True, exist_ok=True)

    for name in (
        "script.json",
        "script.mp3",
        "segment_timestamps.json",
        "broll_selections.json",
        TIMESTAMPS_JOB_NAME,
        ".broll_export_status.json",
        ".broll_flagged.json",
    ):
        source = workspace_root / name
        if source.exists():
            source.rename(legacy_dest / name)

    cache_src = workspace_root / ".broll_cache"
    if cache_src.exists():
        cache_src.rename(legacy_dest / ".broll_cache")

    title = None
    script_path = legacy_dest / "script.json"
    if script_path.exists():
        try:
            with script_path.open("r", encoding="utf-8") as infile:
                title = json.load(infile).get("title")
        except (json.JSONDecodeError, OSError):
            title = None

    touch_manifest(legacy_dest, id="legacy", name=title or "Imported project")
    print("[projects] Migrated legacy workspace to projects/legacy")


def migrate_user_scoped_projects(workspace_root: Path) -> None:
    """Move users/<user>/projects/<id> into shared projects/<id>."""
    users_dir = workspace_root / "users"
    if not users_dir.exists():
        return

    global_root = projects_root(workspace_root)
    migrated = 0

    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue
        per_user_projects = user_dir / "projects"
        if not per_user_projects.exists():
            continue
        for child in per_user_projects.iterdir():
            if not child.is_dir() or not PROJECT_ID_RE.match(child.name):
                continue
            dest = global_root / child.name
            if dest.exists():
                dest = global_root / f"{user_dir.name}-{child.name}"
            shutil.move(str(child), str(dest))
            migrated += 1

    if migrated:
        print(f"[projects] Migrated {migrated} user-scoped project(s) to shared projects/")

    if users_dir.exists() and not any(users_dir.rglob("*")):
        shutil.rmtree(users_dir, ignore_errors=True)
