"""Global automation watchdog: resume stalled projects and sequential export queue."""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from automation_settings import automation_enabled, read_automation_settings
from export_job_state import project_export_running, read_export_state_file
from export_runner import start_export_for_workspace, wait_for_export_done
from pipeline_jobs import pipeline_job_snapshot, start_broll_pipeline
from project_manager import (
    project_status,
    start_audio_generation,
    start_segment_timestamps,
    timestamps_job_snapshot,
    tts_job_snapshot,
)
from user_sessions import list_projects, project_workspace, read_manifest, touch_manifest

WATCHDOG_INTERVAL_SECONDS = 30
EXPORT_RETRY_ATTEMPTS = 2
STALE_EXPORT_SECONDS = 45 * 60

_lock = threading.Lock()
_export_queue: deque[str] = deque()
_queued_ids: set[str] = set()
_exporting_id: str | None = None
_worker_started = False
_last_scan_at: float | None = None


def automation_status(workspace_root: Path) -> dict[str, Any]:
    settings = read_automation_settings(workspace_root)
    with _lock:
        return {
            "enabled": bool(settings.get("enabled", True)),
            "exporting_project_id": _exporting_id,
            "queue_length": len(_export_queue),
            "queued_project_ids": list(_export_queue),
            "last_scan_at": _last_scan_at,
        }


def enqueue_export(project_id: str) -> None:
    with _lock:
        if project_id == _exporting_id or project_id in _queued_ids:
            return
        _export_queue.append(project_id)
        _queued_ids.add(project_id)


def is_queued_for_export(project_id: str) -> bool:
    with _lock:
        return project_id in _queued_ids or project_id == _exporting_id


def _dequeue_export() -> str | None:
    with _lock:
        while _export_queue:
            project_id = _export_queue.popleft()
            _queued_ids.discard(project_id)
            return project_id
    return None


def _set_exporting(project_id: str | None) -> None:
    global _exporting_id
    with _lock:
        _exporting_id = project_id


def _manifest_goal(workspace: Path) -> str:
    manifest = read_manifest(workspace)
    goal = str(manifest.get("automation_goal") or "none").strip().lower()
    if goal in {"fetch_review", "auto_export", "none"}:
        return goal
    return "none"


def _should_automate(workspace_root: Path, workspace: Path, *, force: bool = False) -> bool:
    if not force and not automation_enabled(workspace_root):
        return False
    return _manifest_goal(workspace) != "none"


def _maybe_start_tts(
    workspace_root: Path, workspace: Path, project_id: str, *, force: bool = False
) -> None:
    if not _should_automate(workspace_root, workspace, force=force):
        return
    status = project_status(workspace)
    if status.get("audio_uploaded"):
        return
    if tts_job_snapshot(workspace).get("status") == "running":
        return
    try:
        start_audio_generation(workspace)
        print(f"[automation] Started TTS for {project_id}")
    except Exception as exc:
        print(f"[automation] TTS start skipped for {project_id}: {exc}")


def _maybe_start_whisper(
    workspace_root: Path, workspace: Path, project_id: str, *, force: bool = False
) -> None:
    if not _should_automate(workspace_root, workspace, force=force):
        return
    status = project_status(workspace)
    if not status.get("audio_uploaded") or status.get("timestamps_ready"):
        return
    if timestamps_job_snapshot(workspace).get("status") == "running":
        return
    try:
        start_segment_timestamps(workspace, model="medium")
        print(f"[automation] Started Whisper for {project_id}")
    except Exception as exc:
        print(f"[automation] Whisper start skipped for {project_id}: {exc}")


def _maybe_start_pipeline(
    workspace_root: Path, workspace: Path, project_id: str, *, force: bool = False
) -> None:
    if not _should_automate(workspace_root, workspace, force=force):
        return
    status = project_status(workspace)
    if not status.get("viewer_ready"):
        return
    pipeline = pipeline_job_snapshot(workspace)
    pipeline_status = str(pipeline.get("status") or "idle")
    list_status = str(status.get("list_status") or "")
    if pipeline_status == "running":
        return
    needs_pipeline = list_status in {
        "ready_for_broll",
        "fetching_broll",
        "clearing_duplicates",
    } or pipeline_status in {"error", "interrupted", "warning"}
    if not needs_pipeline:
        return
    try:
        start_broll_pipeline(workspace)
        print(f"[automation] Started b-roll pipeline for {project_id}")
    except Exception as exc:
        print(f"[automation] Pipeline start skipped for {project_id}: {exc}")


def _maybe_queue_export(
    workspace_root: Path, workspace: Path, project_id: str, *, force: bool = False
) -> None:
    if not force and not automation_enabled(workspace_root):
        return
    if _manifest_goal(workspace) != "auto_export":
        return
    status = project_status(workspace)
    list_status = str(status.get("list_status") or "")
    export_status = str((status.get("export_job") or {}).get("status") or "idle")
    if export_status == "running":
        return
    if list_status == "ready_for_export":
        enqueue_export(project_id)
    elif list_status == "complete":
        return
    elif list_status == "ready_for_refetch" and status.get("broll_fetched", 0) >= status.get(
        "broll_total", 0
    ):
        # Auto-export path: bypass manual refetch gate once b-roll is complete.
        touch_manifest(workspace, manual_refetch_done=True)
        enqueue_export(project_id)


def _resume_single_project(
    workspace_root: Path, workspace: Path, project_id: str, *, force: bool
) -> None:
    _maybe_start_tts(workspace_root, workspace, project_id, force=force)
    _maybe_start_whisper(workspace_root, workspace, project_id, force=force)
    _maybe_start_pipeline(workspace_root, workspace, project_id, force=force)
    _maybe_queue_export(workspace_root, workspace, project_id, force=force)


def scan_projects(workspace_root: Path, *, force: bool = False) -> None:
    global _last_scan_at
    _last_scan_at = time.time()
    if not force and not automation_enabled(workspace_root):
        return
    for project in list_projects(workspace_root):
        project_id = str(project.get("id") or "")
        if not project_id:
            continue
        try:
            workspace = project_workspace(workspace_root, project_id)
        except Exception:
            continue
        try:
            _resume_single_project(workspace_root, workspace, project_id, force=force)
        except Exception as exc:
            print(f"[automation] Resume failed for {project_id}: {exc}")


def _export_worker_loop(workspace_root: Path) -> None:
    while True:
        project_id = _dequeue_export()
        if not project_id:
            time.sleep(1.0)
            continue
        try:
            workspace = project_workspace(workspace_root, project_id)
        except Exception:
            continue
        _set_exporting(project_id)
        try:
            for attempt in range(1, EXPORT_RETRY_ATTEMPTS + 2):
                if project_export_running(project_id):
                    state = wait_for_export_done(workspace, project_id)
                else:
                    start_export_for_workspace(workspace, project_id)
                    state = wait_for_export_done(workspace, project_id)
                if str(state.get("status")) == "done":
                    print(f"[automation] Export complete for {project_id}")
                    break
                print(
                    f"[automation] Export failed for {project_id} "
                    f"(attempt {attempt}): {state.get('error')}"
                )
                if attempt > EXPORT_RETRY_ATTEMPTS:
                    break
                time.sleep(5.0)
        except Exception as exc:
            print(f"[automation] Export queue error for {project_id}: {exc}")
        finally:
            _set_exporting(None)


def _watchdog_loop(workspace_root: Path) -> None:
    while True:
        try:
            scan_projects(workspace_root)
        except Exception as exc:
            print(f"[automation] Watchdog scan failed: {exc}")
        time.sleep(WATCHDOG_INTERVAL_SECONDS)


def start_automation_orchestrator(workspace_root: Path) -> None:
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    threading.Thread(target=_export_worker_loop, args=(workspace_root,), daemon=True).start()
    threading.Thread(target=_watchdog_loop, args=(workspace_root,), daemon=True).start()
    print("[automation] Orchestrator started")


def resume_automation(
    workspace_root: Path,
    *,
    project_id: str | None = None,
    force: bool = True,
) -> dict[str, Any]:
    """Manually nudge automation forward — used by the UI's Resume / Resume all buttons.

    force=True bypasses the global automation-enabled toggle so a stuck project
    can be nudged even while automation is paused; it never bypasses a
    project's own automation_goal (goal "none" is always left untouched).
    """
    if project_id:
        try:
            workspace = project_workspace(workspace_root, project_id)
            _resume_single_project(workspace_root, workspace, project_id, force=force)
        except Exception as exc:
            print(f"[automation] Manual resume failed for {project_id}: {exc}")
    else:
        scan_projects(workspace_root, force=force)
    return automation_status(workspace_root)
