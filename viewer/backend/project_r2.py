"""Sync workspace project files to R2 (direct S3 API, no Next.js body limit)."""

from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from project_manager import (
    AUDIO_NAME,
    SCRIPT_NAME,
    SELECTIONS_NAME,
    TIMESTAMPS_NAME,
    workspace_paths,
)
from user_sessions import PROJECT_ID_RE, parse_workspace_scope

PROJECT_STORAGE_PREFIX = ".project/"
PROJECT_TTL_SECONDS = 7 * 24 * 60 * 60

PROJECT_FILE_NAMES = (
    SCRIPT_NAME,
    AUDIO_NAME,
    TIMESTAMPS_NAME,
    SELECTIONS_NAME,
)

PATH_KEYS = {
    SCRIPT_NAME: "script",
    AUDIO_NAME: "audio",
    TIMESTAMPS_NAME: "timestamps",
    SELECTIONS_NAME: "selections",
}

_LEGACY_WORKSPACE_PREFIX = f"{PROJECT_STORAGE_PREFIX}workspace/"


def _web_base() -> str:
    return os.environ.get("BROLL_WEB_BASE_URL", "http://127.0.0.1:3001").rstrip("/")


def _r2_configured() -> bool:
    return bool(
        os.environ.get("R2_ACCOUNT_ID")
        and os.environ.get("R2_ACCESS_KEY_ID")
        and os.environ.get("R2_SECRET_ACCESS_KEY")
        and os.environ.get("R2_BUCKET_NAME")
    )


def _r2_client():
    import boto3

    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _project_key(workspace: Path, name: str) -> str | None:
    safe = name.replace("\\", "/").split("/")[-1].strip()
    if safe not in PROJECT_FILE_NAMES:
        raise ValueError(f"Unsupported project file: {name}")
    project_id = parse_workspace_scope(workspace)
    if not project_id:
        return None
    return f"{PROJECT_STORAGE_PREFIX}projects/{project_id}/{safe}"


def _parse_r2_project_id(key: str) -> str | None:
    if not key.startswith(PROJECT_STORAGE_PREFIX):
        return None
    remainder = key[len(PROJECT_STORAGE_PREFIX) :]
    if remainder.startswith("projects/"):
        parts = remainder.split("/")
        if len(parts) >= 3 and PROJECT_ID_RE.match(parts[1]):
            return parts[1]
        return None
    if remainder.startswith("users/"):
        parts = remainder.split("/")
        try:
            projects_idx = parts.index("projects")
            project_id = parts[projects_idx + 1]
            if PROJECT_ID_RE.match(project_id):
                return project_id
        except (ValueError, IndexError):
            return None
        return None
    if remainder.startswith("workspace/"):
        return "legacy"
    return None


def _iter_r2_object_keys(prefix: str = PROJECT_STORAGE_PREFIX) -> list[str]:
    if not _r2_configured():
        return []
    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    keys: list[str] = []
    continuation: str | None = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if continuation:
            kwargs["ContinuationToken"] = continuation
        response = client.list_objects_v2(**kwargs)
        for entry in response.get("Contents") or []:
            key = entry.get("Key")
            if key and not key.endswith("/"):
                keys.append(str(key))
        if not response.get("IsTruncated"):
            break
        continuation = response.get("NextContinuationToken")
    return keys


def _delete_r2_keys(keys: list[str]) -> list[str]:
    if not keys or not _r2_configured():
        return []
    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    deleted: list[str] = []
    for key in keys:
        try:
            client.delete_object(Bucket=bucket, Key=key)
            deleted.append(key)
        except Exception as exc:
            print(f"[project-r2] Failed to delete {key}: {exc}")
    return deleted


def delete_project_from_r2(project_id: str) -> list[str]:
    """Remove all R2 backups for a project id."""
    if not _r2_configured():
        return []
    if not PROJECT_ID_RE.match(project_id):
        raise ValueError("Invalid project id.")

    prefixes = [f"{PROJECT_STORAGE_PREFIX}projects/{project_id}/"]
    if project_id == "legacy":
        prefixes.append(_LEGACY_WORKSPACE_PREFIX)

    keys: list[str] = []
    for prefix in prefixes:
        keys.extend(_iter_r2_object_keys(prefix))

    # User-scoped layout: .project/users/<user>/projects/<id>/...
    for key in _iter_r2_object_keys(f"{PROJECT_STORAGE_PREFIX}users/"):
        parsed = _parse_r2_project_id(key)
        if parsed == project_id:
            keys.append(key)

    unique_keys = sorted(set(keys))
    deleted = _delete_r2_keys(unique_keys)
    if deleted:
        print(f"[project-r2] Deleted {len(deleted)} R2 object(s) for project {project_id}")
    return deleted


def purge_r2_orphan_projects(workspace_root: Path) -> list[str]:
    """Delete R2 project backups that have no matching local workspace folder."""
    from user_sessions import list_local_project_ids

    if not _r2_configured():
        return []

    local_ids = list_local_project_ids(workspace_root)
    orphan_keys: list[str] = []
    orphan_projects: set[str] = set()

    for key in _iter_r2_object_keys():
        project_id = _parse_r2_project_id(key)
        if not project_id or project_id in local_ids:
            continue
        orphan_keys.append(key)
        orphan_projects.add(project_id)

    if orphan_keys:
        _delete_r2_keys(orphan_keys)
        print(
            "[project-r2] Purged R2 backup(s) for removed local project(s): "
            + ", ".join(sorted(orphan_projects))
        )
    return sorted(orphan_projects)


def sync_local_projects_with_r2(workspace_root: Path) -> dict[str, Any]:
    """Align R2 project backups with folders on local disk (disk is source of truth)."""
    purged = purge_r2_orphan_projects(workspace_root)
    from user_sessions import list_local_project_ids

    return {
        "purged_project_ids": purged,
        "local_project_count": len(list_local_project_ids(workspace_root)),
    }


def sync_project_path(path: Path, workspace: Path, name: str) -> None:
    if not path.exists():
        return
    if not _r2_configured():
        print("[project-r2] R2 not configured; skipping sync.")
        return
    key = _project_key(workspace, name)
    if not key:
        print(f"[project-r2] Skipping sync for non-scoped workspace: {workspace}")
        return
    try:
        client = _r2_client()
        bucket = os.environ["R2_BUCKET_NAME"]
        expires_at = int(time.time()) + PROJECT_TTL_SECONDS
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=path.read_bytes(),
            ContentType=content_type,
            Metadata={
                "expires-at": str(expires_at),
                "project-file": name,
            },
        )
        print(f"[project-r2] Synced {name} to R2 ({key})")
    except Exception as exc:
        print(f"[project-r2] Failed to sync {name}: {exc}")


def sync_workspace_file(workspace: Path, name: str) -> None:
    key = PATH_KEYS.get(name)
    if not key:
        return
    paths = workspace_paths(workspace)
    sync_project_path(paths[key], workspace, name)


def sync_workspace_files(workspace: Path) -> None:
    for name in PROJECT_FILE_NAMES:
        sync_workspace_file(workspace, name)


def restore_workspace_from_r2(workspace: Path) -> None:
    project_id = parse_workspace_scope(workspace)
    if not project_id:
        return
    try:
        request = urllib.request.Request(
            f"{_web_base()}/api/storage/project?project={urllib.parse.quote(project_id, safe='')}"
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"[project-r2] Restore list failed: {exc}")
        return

    if not payload.get("configured", True):
        return

    paths = workspace_paths(workspace)
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        key = str(item.get("key") or "")
        path_key = PATH_KEYS.get(name)
        if not path_key or not key:
            continue
        dest = paths[path_key]
        if dest.exists():
            continue
        try:
            media_url = f"{_web_base()}/api/storage/media?key={urllib.parse.quote(key, safe='')}"
            with urllib.request.urlopen(media_url, timeout=300) as response:
                dest.write_bytes(response.read())
            print(f"[project-r2] Restored {name} from R2")
        except Exception as exc:
            print(f"[project-r2] Failed to restore {name}: {exc}")
