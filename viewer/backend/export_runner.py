"""Programmatic export start for automation orchestrator."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from export_job_state import (
    clear_cancel_event,
    compute_export_inputs_hash,
    get_cancel_event,
    project_export_running,
    update_export_state,
)
from export_video import (
    ExportCancelled,
    build_export_output_path,
    export_video,
    set_export_context,
    summarize_export_error,
)
from project_manager import workspace_paths
from storage_r2 import upload_exported_video
from user_sessions import read_manifest
from youtube_description import build_youtube_description


def _start_background_r2_upload(
    *,
    local_path: Path,
    project_name: str,
    project_id: str,
    status_file: Path,
) -> None:
    """Upload after export is already marked done — never block the queue."""

    def _run() -> None:
        try:
            key = upload_exported_video(local_path, project_name)
            update_export_state(project_id, status_file, r2_key=key)
        except Exception as exc:
            print(f"[export-r2] Background upload failed: {exc}")

    threading.Thread(
        target=_run,
        daemon=True,
        name=f"r2-upload-{project_id[:8]}",
    ).start()


def start_export_for_workspace(
    workspace: Path,
    project_id: str,
    *,
    resolution: str = "4k",
    quality: str = "balanced",
    include_subtitles: bool = False,
) -> None:
    if project_export_running(project_id):
        raise RuntimeError("Export already in progress for this project")

    paths = workspace_paths(workspace)
    status_file = paths["export_status"]
    script_path = paths["script"]
    timestamps_path = paths["timestamps"]
    selections_path = paths["selections"]
    audio_path = paths["audio"]
    cache_dir = paths["cache"]

    import json

    script_data: dict[str, Any] = {}
    timestamps_data: dict[str, Any] = {}
    if script_path.exists():
        script_data = json.loads(script_path.read_text(encoding="utf-8"))
    if timestamps_path.exists():
        timestamps_data = json.loads(timestamps_path.read_text(encoding="utf-8"))
    title = script_data.get("title") or timestamps_data.get("title")
    channel = script_data.get("channel") or timestamps_data.get("channel")
    output_path = build_export_output_path(channel, title)

    manifest = read_manifest(workspace)
    project_name = manifest.get("name") or title or project_id[:8]

    clear_cancel_event(project_id)
    cancel_event = get_cancel_event(project_id)

    def set_state(**kwargs: Any) -> None:
        # project_id is already the first positional arg to update_export_state —
        # never pass it again as a keyword or Python raises TypeError before the
        # function body (and its kwargs.pop guard) can run.
        kwargs.pop("project_id", None)
        update_export_state(project_id, status_file, **kwargs)

    set_state(
        status="running",
        stage="queued",
        current=0,
        total=0,
        message="Starting export…",
        output=str(output_path.resolve()),
        encoder=None,
        error=None,
        started_at=time.time(),
        progress_percent=0,
        elapsed_seconds=0,
        eta_seconds=None,
        hardware=None,
        project_name=project_name,
        download_started_at=None,
        render_started_at=None,
        download_seconds=0,
        render_seconds=0,
        inputs_hash=None,
        youtube_description=None,
    )

    def on_progress(stage: str, current: int, total: int, message: str) -> None:
        set_state(stage=stage, current=current, total=total, message=message)

    def worker() -> None:
        set_export_context(project_id)
        try:
            result = export_video(
                audio_path=audio_path,
                timestamps_path=timestamps_path,
                selections_path=selections_path,
                script_path=script_path,
                output_path=output_path,
                on_progress=on_progress,
                cache_dir=cache_dir,
                fresh=True,
                should_cancel=cancel_event.is_set,
                resolution=resolution,
                quality=quality,
                include_subtitles=include_subtitles,
            )
            if cancel_event.is_set():
                return
            inputs_hash = compute_export_inputs_hash(
                timestamps_path=timestamps_path,
                selections_path=selections_path,
                audio_path=audio_path,
            )
            youtube_description: str | None = None
            set_state(
                stage="finalize",
                message="Generating YouTube description…",
                progress_percent=99,
                output=result["output"],
                encoder=result["encoder"],
            )
            try:
                youtube_description = build_youtube_description(
                    script_path=script_path,
                    timestamps_path=timestamps_path,
                    selections_path=selections_path,
                    project_name=project_name or project_id[:8],
                )
            except Exception as desc_exc:
                print(f"[export] Description generation skipped: {desc_exc}")
            # Local MP4 is the source of truth — mark done before any cloud work
            # so a hung R2 upload can never pin the sequential export queue.
            set_state(
                status="done",
                stage="done",
                current=1,
                total=1,
                message=f"Export complete: {result['output']}",
                output=result["output"],
                encoder=result["encoder"],
                error=None,
                progress_percent=100,
                eta_seconds=0,
                inputs_hash=inputs_hash,
                r2_key=None,
                youtube_description=youtube_description,
            )
            _start_background_r2_upload(
                local_path=Path(result["output"]),
                project_name=project_name or project_id[:8],
                project_id=project_id,
                status_file=status_file,
            )
        except ExportCancelled:
            if not cancel_event.is_set():
                set_state(
                    status="interrupted",
                    stage="cancelled",
                    message="Export cancelled",
                    error=None,
                )
        except Exception as exc:
            if cancel_event.is_set():
                return
            summary = summarize_export_error(exc)
            set_state(
                status="error",
                stage="error",
                message=summary,
                error=summary,
            )
        finally:
            set_export_context(None)
            clear_cancel_event(project_id)

    threading.Thread(target=worker, daemon=True).start()


def wait_for_export_done(
    workspace: Path,
    project_id: str,
    *,
    poll_seconds: float = 2.0,
    timeout_seconds: float = 6 * 3600,
) -> dict[str, Any]:
    from export_job_state import export_snapshot, project_export_running, read_export_state_file

    status_file = workspace_paths(workspace)["export_status"]
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        # Prefer in-memory state while this process owns the export — reading
        # the file through the old startup normalizer used to rewrite every
        # live "running" job to "interrupted" and abort exports instantly.
        if project_export_running(project_id):
            state = export_snapshot(project_id, status_file)
        else:
            state = read_export_state_file(status_file) if status_file.exists() else {}
        status = str(state.get("status") or "idle")
        if status in {"done", "error", "interrupted"}:
            return state
        time.sleep(poll_seconds)
    return {"status": "error", "error": "Export timed out"}
