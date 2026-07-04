"""In-memory YouTube audio download jobs with progress tracking."""

from __future__ import annotations

import shutil
import threading
import uuid
from typing import Any, Callable

from storage_r2 import upload_storage_audio, validate_audio_storage_prefix
from youtube_audio import download_youtube_audio_to_temp, sanitize_audio_filename

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _update_job(job_id: str, **fields: Any) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.update(fields)


def get_youtube_audio_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_running_youtube_audio_jobs() -> list[dict[str, Any]]:
    with _lock:
        return [
            dict(job)
            for job in _jobs.values()
            if job.get("status") == "running"
        ]


def start_youtube_audio_job(url: str, prefix: str) -> str:
    validate_audio_storage_prefix(prefix)
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress_percent": 0,
            "message": "Starting download…",
            "stage": "starting",
            "url": url,
            "prefix": prefix,
            "title": None,
            "key": None,
            "name": None,
            "error": None,
        }

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, url, prefix),
        daemon=True,
        name=f"yt-audio-{job_id}",
    )
    thread.start()
    return job_id


def _run_job(job_id: str, url: str, prefix: str) -> None:
    temp_root = None

    def on_progress(percent: int, message: str, stage: str) -> None:
        _update_job(
            job_id,
            progress_percent=max(0, min(99, int(percent))),
            message=message,
            stage=stage,
        )

    try:
        local_path, title = download_youtube_audio_to_temp(url, on_progress=on_progress)
        temp_root = local_path.parent
        _update_job(job_id, title=title, progress_percent=95, message="Uploading to storage…", stage="upload")
        filename = f"{sanitize_audio_filename(title)}.mp3"
        result = upload_storage_audio(prefix, local_path, filename=filename)
        _update_job(
            job_id,
            status="done",
            progress_percent=100,
            message="Saved to storage",
            stage="done",
            title=title,
            key=result["key"],
            name=result["name"],
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="error",
            progress_percent=0,
            message=str(exc),
            stage="error",
            error=str(exc),
        )
    finally:
        if temp_root and temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
