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

# Projects are auto-pruned after a week of inactivity to save local disk.
# Local and R2 backups are kept in sync — deleting a local folder removes R2 too.
PROJECT_TTL_SECONDS = 7 * 24 * 60 * 60

# Files whose mtime reflects real activity on a project (uploads, b-roll
# selections, exports, segmentation jobs).
_ACTIVITY_FILES = (
    "project.json",
    "script.json",
    "script.mp3",
    "segment_timestamps.json",
    "broll_selections.json",
    ".broll_export_status.json",
    ".broll_flagged.json",
    ".timestamps_job.json",
)


def project_last_activity(workspace: Path, manifest: dict[str, Any] | None = None) -> float | None:
    """Most recent activity timestamp for a project (epoch seconds)."""
    times: list[float] = []
    manifest = manifest if manifest is not None else read_manifest(workspace)
    updated = manifest.get("updated_at")
    if isinstance(updated, (int, float)):
        times.append(float(updated))
    for name in _ACTIVITY_FILES:
        path = workspace / name
        try:
            if path.exists():
                times.append(path.stat().st_mtime)
        except OSError:
            continue
    return max(times) if times else None


def projects_root(workspace_root: Path) -> Path:
    root = workspace_root / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_local_project_ids(workspace_root: Path) -> set[str]:
    """Project folder names currently on local disk."""
    root = projects_root(workspace_root)
    if not root.exists():
        return set()
    ids: set[str] = set()
    for child in root.iterdir():
        if child.is_dir() and PROJECT_ID_RE.match(child.name):
            ids.add(child.name)
    return ids


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

    last_activity = project_last_activity(workspace, manifest)
    expires_at = (last_activity + PROJECT_TTL_SECONDS) if last_activity else None

    return {
        "id": project_id,
        "name": name,
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "last_activity": last_activity,
        "expires_at": expires_at,
        "ttl_seconds": PROJECT_TTL_SECONDS,
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


def delete_project(workspace_root: Path, project_id: str) -> None:
    """Remove a project's local workspace and its R2 backup."""
    workspace = project_workspace(workspace_root, project_id)
    resolved = workspace.resolve()
    root = projects_root(workspace_root).resolve()
    # Safety: never delete outside the projects root.
    if root not in resolved.parents:
        raise ValueError("Refusing to delete project outside the projects root.")
    if resolved.exists():
        shutil.rmtree(resolved, ignore_errors=True)
    # Drop any in-memory segmentation job state for this workspace.
    try:
        from project_manager import forget_timestamps_state

        forget_timestamps_state(workspace)
    except Exception:
        pass
    try:
        from project_r2 import delete_project_from_r2

        delete_project_from_r2(project_id)
    except Exception as exc:
        print(f"[project-r2] Failed to delete R2 backup for {project_id}: {exc}")


def prune_stale_projects(
    workspace_root: Path,
    *,
    ttl_seconds: float = PROJECT_TTL_SECONDS,
    is_protected: Any = None,
) -> list[str]:
    """Delete projects inactive longer than ttl_seconds. Returns deleted ids.

    `is_protected(project_id)` may be supplied to skip projects with an active
    job (export/segmentation) so we never delete something mid-run.
    """
    root = projects_root(workspace_root)
    now = time.time()
    deleted: list[str] = []
    if not root.exists():
        return deleted

    for child in root.iterdir():
        if not child.is_dir() or not PROJECT_ID_RE.match(child.name):
            continue
        project_id = child.name
        if callable(is_protected) and is_protected(project_id):
            continue
        last_activity = project_last_activity(child)
        if last_activity is None:
            continue
        if now - last_activity <= ttl_seconds:
            continue
        try:
            delete_project(workspace_root, project_id)
            deleted.append(project_id)
            print(f"[projects] Pruned inactive project {project_id}")
        except Exception as exc:  # noqa: BLE001
            print(f"[projects] Failed to prune {project_id}: {exc}")

    return deleted


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
