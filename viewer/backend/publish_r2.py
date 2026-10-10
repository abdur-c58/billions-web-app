"""Mirror ready-to-publish exports into R2 so they can be published while this PC is off.

Each ready video gets its own folder:

    Publish/<project_id>/<title>.mp4
    Publish/<project_id>/publish.json   (written last — its presence means the video is there)
    Publish/<project_id>/published.json (written by the website once the video is published)

The deployed /publish page reads only these objects, never this backend.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from project_r2 import _r2_client, _r2_configured
from publish_queue import build_publish_entry
from user_sessions import PROJECT_ID_RE, projects_root

PUBLISH_PREFIX = "Publish/"
MANIFEST_NAME = "publish.json"
PUBLISHED_MARKER_NAME = "published.json"
# Published videos stay downloadable for a week, then their folder is removed.
PUBLISHED_RETENTION_SECONDS = 7 * 24 * 60 * 60
# R2/S3 single-request copy limit; larger files are re-uploaded from disk.
MAX_COPY_BYTES = 5 * 1024 * 1024 * 1024

_sync_lock = threading.Lock()


def _folder(project_id: str) -> str:
    return f"{PUBLISH_PREFIX}{project_id}/"


def _safe_filename(title: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip().rstrip(".")
    return f"{(cleaned or fallback)[:150]}.mp4"


def _read_object_json(client: Any, bucket: str, key: str) -> dict[str, Any] | None:
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except client.exceptions.NoSuchKey:
        return None
    except Exception as exc:
        if "NoSuchKey" in str(exc) or "404" in str(exc):
            return None
        raise
    try:
        payload = json.loads(response["Body"].read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _object_size(client: Any, bucket: str, key: str) -> int | None:
    try:
        return int(client.head_object(Bucket=bucket, Key=key).get("ContentLength") or 0)
    except Exception:
        return None


def _put_video(
    client: Any,
    bucket: str,
    *,
    video_key: str,
    local_path: Path,
    exported_r2_key: str | None,
) -> int:
    local_size = local_path.stat().st_size
    if exported_r2_key:
        source_size = _object_size(client, bucket, exported_r2_key)
        if source_size == local_size and source_size <= MAX_COPY_BYTES:
            client.copy_object(
                Bucket=bucket,
                Key=video_key,
                CopySource={"Bucket": bucket, "Key": exported_r2_key},
                ContentType="video/mp4",
                MetadataDirective="REPLACE",
            )
            print(f"[publish-r2] Copied {exported_r2_key} -> {video_key}")
            return local_size

    from boto3.s3.transfer import TransferConfig

    print(f"[publish-r2] Uploading {local_size / (1024 * 1024):.0f} MB to {video_key}")
    client.upload_file(
        Filename=str(local_path),
        Bucket=bucket,
        Key=video_key,
        ExtraArgs={"ContentType": "video/mp4"},
        Config=TransferConfig(
            multipart_threshold=64 * 1024 * 1024,
            multipart_chunksize=64 * 1024 * 1024,
            max_concurrency=4,
            use_threads=True,
        ),
    )
    return local_size


def sync_publish_entry(workspace_root: Path, project_id: str) -> str | None:
    """Mirror one project into Publish/ if its export passes every check. Returns the manifest key."""
    if not _r2_configured():
        return None
    entry = build_publish_entry(workspace_root, project_id)
    if not entry or not all(check["ok"] for check in entry["checks"]):
        return None

    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    folder = _folder(project_id)
    manifest_key = f"{folder}{MANIFEST_NAME}"

    existing = _read_object_json(client, bucket, manifest_key)
    if (
        existing
        and existing.get("inputs_hash") == entry["inputs_hash"]
        and existing.get("video_size_bytes") == entry["video_size_bytes"]
        and _object_size(client, bucket, str(existing.get("video_key") or "")) == entry["video_size_bytes"]
    ):
        return manifest_key

    video_filename = _safe_filename(entry["title"], project_id)
    video_key = f"{folder}{video_filename}"
    size = _put_video(
        client,
        bucket,
        video_key=video_key,
        local_path=Path(entry["video_path"]),
        exported_r2_key=entry.get("exported_r2_key"),
    )
    if existing and existing.get("video_key") and existing["video_key"] != video_key:
        client.delete_object(Bucket=bucket, Key=existing["video_key"])

    manifest = {
        "project_id": project_id,
        "title": entry["title"],
        "channel": entry["channel"],
        "thumbnail": entry["thumbnail"],
        "chapters": entry["chapters"],
        "chapters_text": entry["chapters_text"],
        "video_key": video_key,
        "video_filename": video_filename,
        "video_size_bytes": size,
        "exported_at": entry["exported_at"],
        "synced_at": time.time(),
        "inputs_hash": entry["inputs_hash"],
    }
    client.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"[publish-r2] Ready for publishing in R2: {manifest_key}")
    return manifest_key


def purge_old_published(client: Any, bucket: str) -> list[str]:
    """Delete Publish/ folders whose video was published more than a week ago."""
    removed: list[str] = []
    cutoff = time.time() - PUBLISHED_RETENTION_SECONDS
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=PUBLISH_PREFIX):
        for obj in page.get("Contents") or []:
            key = str(obj.get("Key") or "")
            if not key.endswith(f"/{PUBLISHED_MARKER_NAME}"):
                continue
            marker = _read_object_json(client, bucket, key) or {}
            published_at = float(marker.get("published_at") or 0)
            if not marker.get("published") or published_at > cutoff:
                continue
            folder = key[: -len(PUBLISHED_MARKER_NAME)]
            for folder_page in paginator.paginate(Bucket=bucket, Prefix=folder):
                for item in folder_page.get("Contents") or []:
                    client.delete_object(Bucket=bucket, Key=item["Key"])
            removed.append(folder)
            print(f"[publish-r2] Removed published folder {folder}")
    return removed


def sync_all_publish_entries(workspace_root: Path) -> None:
    """Mirror every ready export and clear out long-published ones."""
    if not _r2_configured():
        return
    with _sync_lock:
        for child in projects_root(workspace_root).iterdir():
            if not child.is_dir() or not PROJECT_ID_RE.match(child.name):
                continue
            try:
                sync_publish_entry(workspace_root, child.name)
            except Exception as exc:
                print(f"[publish-r2] Sync failed for {child.name}: {exc}")
        try:
            purge_old_published(_r2_client(), os.environ["R2_BUCKET_NAME"])
        except Exception as exc:
            print(f"[publish-r2] Purge failed: {exc}")


def sync_publish_entry_safely(workspace_root: Path | None, project_id: str) -> None:
    if workspace_root is None:
        return
    with _sync_lock:
        try:
            sync_publish_entry(workspace_root, project_id)
        except Exception as exc:
            print(f"[publish-r2] Sync failed for {project_id}: {exc}")
