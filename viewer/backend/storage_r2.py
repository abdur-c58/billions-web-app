"""List and cache background audio/video from the shared R2 storage library."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any

from project_r2 import _r2_client, _r2_configured

EXPORTED_VIDEOS_PREFIX = "Exported Videos/"
EXPORTED_VIDEO_TTL_SECONDS = 7 * 24 * 60 * 60  # 1 week of no download activity

STORAGE_AUDIO_PREFIX = "Audio/"
STORAGE_BROLL_PREFIX = "B-Roll/"

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma"}
VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".avi",
    ".mkv",
    ".m4v",
    ".wmv",
    ".flv",
}


def validate_audio_storage_key(key: str) -> None:
    normalized = key.strip().replace("\\", "/")
    if not normalized or normalized.endswith("/"):
        raise ValueError("Invalid audio storage key.")
    if not normalized.startswith(STORAGE_AUDIO_PREFIX):
        raise ValueError("Background audio must be in the Audio storage folder.")
    name = normalized.split("/")[-1]
    ext = Path(name).suffix.lower()
    if ext not in AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio type: {ext}")


def list_r2_background_audio() -> list[dict[str, Any]]:
    if not _r2_configured():
        return []

    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    files: list[dict[str, Any]] = []

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=STORAGE_AUDIO_PREFIX):
        for entry in page.get("Contents") or []:
            key = str(entry.get("Key") or "")
            if not key or key.endswith("/"):
                continue
            ext = Path(key).suffix.lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            files.append(
                {
                    "key": key,
                    "name": key.split("/")[-1],
                    "size_bytes": int(entry.get("Size") or 0),
                    "duration_seconds": None,
                }
            )

    return sorted(files, key=lambda item: str(item["key"]).lower())


def broll_category_prefix(category: str) -> str:
    safe = category.strip().replace("\\", "/").strip("/")
    return f"{STORAGE_BROLL_PREFIX}{safe}/"


def list_r2_videos(prefix: str) -> list[dict[str, Any]]:
    if not _r2_configured():
        return []

    normalized = prefix.strip().replace("\\", "/")
    if not normalized:
        return []
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    if not normalized.startswith(STORAGE_BROLL_PREFIX):
        return []

    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    files: list[dict[str, Any]] = []

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=normalized):
        for entry in page.get("Contents") or []:
            key = str(entry.get("Key") or "")
            if not key or key.endswith("/"):
                continue
            name = key.split("/")[-1]
            ext = Path(name).suffix.lower()
            if ext not in VIDEO_EXTENSIONS:
                continue
            files.append(
                {
                    "key": key,
                    "name": name,
                    "size_bytes": int(entry.get("Size") or 0),
                }
            )

    return sorted(files, key=lambda item: str(item["key"]).lower())


def _cache_path_for_key(key: str, cache_dir: Path) -> Path:
    validate_audio_storage_key(key)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    ext = Path(key).suffix.lower()
    cache_root = cache_dir / "r2_audio"
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root / f"{digest}{ext}"


def upload_exported_video(local_path: Path, project_name: str) -> str:
    """Upload a rendered export to R2 under 'Exported Videos/' and return its key."""
    if not _r2_configured():
        raise RuntimeError("R2 is not configured — cannot upload exported video.")
    if not local_path.exists() or local_path.stat().st_size == 0:
        raise FileNotFoundError(f"Export file not found: {local_path}")

    safe_name = "".join(
        c if (c.isalnum() or c in " _-") else "_" for c in project_name
    ).strip() or "export"
    date_tag = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{date_tag}.mp4"
    key = f"{EXPORTED_VIDEOS_PREFIX}{filename}"

    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    now_str = str(int(time.time()))
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=local_path.read_bytes(),
        ContentType="video/mp4",
        Metadata={
            "last-downloaded": now_str,
            "uploaded-at": now_str,
            "project-name": project_name[:256],
        },
    )
    print(f"[export-r2] Uploaded export to R2: {key}")
    return key


def touch_exported_video_access(key: str) -> None:
    """Update last-downloaded timestamp on an exported video object."""
    if not _r2_configured():
        return
    if not key.startswith(EXPORTED_VIDEOS_PREFIX):
        return
    try:
        client = _r2_client()
        bucket = os.environ["R2_BUCKET_NAME"]
        head = client.head_object(Bucket=bucket, Key=key)
        meta = head.get("Metadata") or {}
        meta["last-downloaded"] = str(int(time.time()))
        client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": key},
            Key=key,
            Metadata=meta,
            MetadataDirective="REPLACE",
            ContentType="video/mp4",
        )
    except Exception as exc:
        print(f"[export-r2] touch_access failed for {key}: {exc}")


def purge_stale_exported_videos() -> list[str]:
    """Delete exported videos whose last-downloaded timestamp is older than 1 week."""
    if not _r2_configured():
        return []
    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    now = int(time.time())
    cutoff = now - EXPORTED_VIDEO_TTL_SECONDS
    deleted: list[str] = []
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=EXPORTED_VIDEOS_PREFIX):
            for obj in page.get("Contents") or []:
                key = str(obj.get("Key") or "")
                if not key or key.endswith("/"):
                    continue
                head = client.head_object(Bucket=bucket, Key=key)
                meta = head.get("Metadata") or {}
                last_dl = int(meta.get("last-downloaded") or meta.get("uploaded-at") or 0)
                if last_dl < cutoff:
                    client.delete_object(Bucket=bucket, Key=key)
                    deleted.append(key)
                    print(f"[export-r2] Purged stale export: {key}")
    except Exception as exc:
        print(f"[export-r2] purge_stale_exported_videos failed: {exc}")
    return deleted


def resolve_r2_background_audio(key: str, cache_dir: Path) -> Path:
    """Download an R2 Audio/ object to a local cache path for ffmpeg."""
    if not _r2_configured():
        raise RuntimeError("R2 is not configured for background audio.")

    validate_audio_storage_key(key)
    local_path = _cache_path_for_key(key, cache_dir)

    if local_path.exists() and local_path.stat().st_size > 0:
        return local_path

    client = _r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    local_path.write_bytes(body)
    return local_path
