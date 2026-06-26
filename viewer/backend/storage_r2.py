"""List and cache background audio from the shared R2 storage library (Audio/ folder)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from project_r2 import _r2_client, _r2_configured

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
