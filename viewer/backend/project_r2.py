"""Sync workspace project files to R2 (direct S3 API, no Next.js body limit)."""

from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from project_manager import (
    AUDIO_NAME,
    SCRIPT_NAME,
    SELECTIONS_NAME,
    TIMESTAMPS_NAME,
    workspace_paths,
)
from user_sessions import parse_workspace_scope

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
