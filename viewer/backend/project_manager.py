"""Workspace project state: script/audio imports and timestamp segmentation."""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable

from segment_timestamps import (
    cache_path_for_audio,
    generate_segment_timestamps,
    iter_script_segments,
)

SCRIPT_NAME = "script.json"
AUDIO_NAME = "script.mp3"
TIMESTAMPS_NAME = "segment_timestamps.json"
SELECTIONS_NAME = "broll_selections.json"
TIMESTAMPS_JOB_NAME = ".timestamps_job.json"
STALE_JOB_SECONDS = 15 * 60

_timestamps_lock = threading.Lock()
_MAX_JOB_LOGS = 200
_default_timestamps_state: dict[str, Any] = {
    "status": "idle",
    "message": "",
    "error": None,
    "started_at": None,
    "updated_at": None,
    "progress_percent": 0,
    "stage": "idle",
    "logs": [],
    "restart_required": False,
    "hardware": None,
}


def _append_job_log(
    state: dict[str, Any],
    *,
    message: str,
    stage: str,
    progress_percent: int,
) -> None:
    logs = state.setdefault("logs", [])
    if not isinstance(logs, list):
        logs = []
        state["logs"] = logs
    logs.append(
        {
            "ts": time.time(),
            "message": message,
            "stage": stage,
            "progress_percent": progress_percent,
        }
    )
    if len(logs) > _MAX_JOB_LOGS:
        del logs[: len(logs) - _MAX_JOB_LOGS]
_timestamps_states: dict[str, dict[str, Any]] = {}


def _workspace_key(workspace: Path) -> str:
    return str(workspace.resolve())


def _fresh_timestamps_state() -> dict[str, Any]:
    return dict(_default_timestamps_state)


def _get_timestamps_state_unlocked(workspace: Path) -> dict[str, Any]:
    key = _workspace_key(workspace)
    state = _timestamps_states.get(key)
    if state is None:
        state = _fresh_timestamps_state()
        _timestamps_states[key] = state
    return state


def _get_timestamps_state(workspace: Path) -> dict[str, Any]:
    with _timestamps_lock:
        return _get_timestamps_state_unlocked(workspace)


def forget_timestamps_state(workspace: Path) -> None:
    """Drop cached segmentation job state (used when a project is deleted)."""
    with _timestamps_lock:
        _timestamps_states.pop(_workspace_key(workspace), None)


def workspace_paths(workspace: Path) -> dict[str, Path]:
    workspace.mkdir(parents=True, exist_ok=True)
    return {
        "workspace": workspace,
        "script": workspace / SCRIPT_NAME,
        "audio": workspace / AUDIO_NAME,
        "timestamps": workspace / TIMESTAMPS_NAME,
        "selections": workspace / SELECTIONS_NAME,
        "cache": workspace / ".broll_cache",
        "flagged": workspace / ".broll_flagged.json",
        "export_status": workspace / ".broll_export_status.json",
        "timestamps_job": workspace / TIMESTAMPS_JOB_NAME,
    }


def _timestamps_job_path(workspace: Path) -> Path:
    return workspace_paths(workspace)["timestamps_job"]


def _persist_timestamps_state(workspace: Path) -> None:
    path = _timestamps_job_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _timestamps_lock:
        snapshot = dict(_get_timestamps_state_unlocked(workspace))
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clear_segmentation_recovery_artifacts(workspace: Path) -> list[str]:
    """Remove Whisper cache and partial timestamps after an interrupted job."""
    paths = workspace_paths(workspace)
    removed: list[str] = []

    if paths["audio"].exists():
        cache_file = cache_path_for_audio(paths["audio"])
        if cache_file.exists():
            cache_file.unlink()
            removed.append(cache_file.name)

    if paths["timestamps"].exists():
        paths["timestamps"].unlink()
        removed.append(TIMESTAMPS_NAME)

    whisper_dir = workspace / ".whisper_cache"
    if whisper_dir.exists():
        shutil.rmtree(whisper_dir, ignore_errors=True)
        removed.append(".whisper_cache/")

    return removed


def _recover_interrupted_segmentation_job(workspace: Path, state: dict[str, Any]) -> None:
    removed = clear_segmentation_recovery_artifacts(workspace)
    removed_note = ", ".join(removed) if removed else "nothing to clear"
    _append_job_log(
        state,
        message=f"Server restarted during segmentation — cleared: {removed_note}",
        stage="error",
        progress_percent=0,
    )
    state.update(
        {
            "status": "error",
            "message": "Segmentation interrupted — run Auto-segment again.",
            "error": (
                "The server restarted while segmenting. Whisper cache and any partial "
                "timestamps were cleared to avoid corrupt files."
            ),
            "progress_percent": 0,
            "stage": "error",
            "restart_required": True,
        }
    )


def load_timestamps_job_state(workspace: Path, *, recover_on_startup: bool = False) -> None:
    """Restore job state from workspace disk (survives refresh and server restart)."""
    path = _timestamps_job_path(workspace)
    state = _fresh_timestamps_state()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as infile:
                payload = json.load(infile)
            if isinstance(payload, dict):
                state.update(payload)
        except (json.JSONDecodeError, OSError):
            pass

    if state.get("status") == "running":
        recovered = False
        if recover_on_startup:
            _recover_interrupted_segmentation_job(workspace, state)
            recovered = True
        else:
            updated_at = float(state.get("updated_at") or 0)
            if updated_at and time.time() - updated_at > STALE_JOB_SECONDS:
                _recover_interrupted_segmentation_job(workspace, state)
                recovered = True
    else:
        recovered = False

    if "progress_percent" not in state:
        state["progress_percent"] = 0
    if "stage" not in state:
        state["stage"] = state.get("status", "idle")
    if "restart_required" not in state:
        state["restart_required"] = False

    with _timestamps_lock:
        _timestamps_states[_workspace_key(workspace)] = state

    if recovered:
        _persist_timestamps_state(workspace)


def _iter_project_workspaces(workspace_root: Path) -> list[Path]:
    from user_sessions import projects_root

    workspaces: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path.resolve())
        if key not in seen and path.is_dir():
            seen.add(key)
            workspaces.append(path)

    root = projects_root(workspace_root)
    if root.exists():
        for child in root.iterdir():
            add(child)

    users_dir = workspace_root / "users"
    if users_dir.exists():
        for user_dir in users_dir.iterdir():
            if not user_dir.is_dir():
                continue
            per_user = user_dir / "projects"
            if per_user.exists():
                for child in per_user.iterdir():
                    add(child)

    return workspaces


def load_all_timestamps_job_states(workspace_root: Path) -> None:
    for workspace in _iter_project_workspaces(workspace_root):
        load_timestamps_job_state(workspace, recover_on_startup=True)


def _set_timestamps_state(workspace: Path, **kwargs: Any) -> None:
    with _timestamps_lock:
        state = _get_timestamps_state_unlocked(workspace)
        kwargs["updated_at"] = time.time()
        message = kwargs.get("message")
        stage = kwargs.get("stage", state.get("stage", "idle"))
        progress = int(kwargs.get("progress_percent", state.get("progress_percent", 0)))
        if isinstance(message, str) and message:
            _append_job_log(
                state,
                message=message,
                stage=str(stage),
                progress_percent=progress,
            )
        state.update(kwargs)
    _persist_timestamps_state(workspace)


def project_status(workspace: Path) -> dict[str, Any]:
    paths = workspace_paths(workspace)
    script_exists = paths["script"].exists()
    audio_exists = paths["audio"].exists()
    timestamps_exists = paths["timestamps"].exists()

    script_title = None
    segment_count = 0
    script_format = None
    if script_exists:
        try:
            with paths["script"].open("r", encoding="utf-8") as infile:
                script_data = json.load(infile)
            script_title = script_data.get("title")
            for beat_block in script_data.get("script", []):
                segment_count += len(beat_block.get("segments", []))
            from script_format import detect_script_format

            script_format = detect_script_format(script_data)
        except (json.JSONDecodeError, OSError):
            script_title = None
            script_format = None

    aligned_segments = 0
    if timestamps_exists:
        try:
            with paths["timestamps"].open("r", encoding="utf-8") as infile:
                timestamps_data = json.load(infile)
            aligned_segments = timestamps_data.get("summary", {}).get("aligned_segments", 0)
            segment_count = timestamps_data.get("summary", {}).get("total_segments", segment_count)
        except (json.JSONDecodeError, OSError):
            pass

    ready = script_exists and audio_exists and timestamps_exists
    with _timestamps_lock:
        timestamps_job = dict(_get_timestamps_state_unlocked(workspace))

    from user_sessions import parse_workspace_scope

    project_id = parse_workspace_scope(workspace)

    return {
        "workspace": str(workspace.resolve()),
        "project_id": project_id,
        "script_uploaded": script_exists,
        "audio_uploaded": audio_exists,
        "timestamps_ready": timestamps_exists,
        "viewer_ready": ready,
        "title": script_title,
        "script_format": script_format,
        "segment_count": segment_count,
        "aligned_segments": aligned_segments,
        "timestamps_job": timestamps_job,
        "next_step": (
            "import_script"
            if not script_exists
            else "import_audio"
            if not audio_exists
            else "segment_timestamps"
            if not timestamps_exists
            else "viewer"
        ),
    }


def save_script(workspace: Path, script_data: dict[str, Any]) -> dict[str, Any]:
    paths = workspace_paths(workspace)
    paths["script"].write_text(
        json.dumps(script_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if paths["timestamps"].exists():
        paths["timestamps"].unlink()
    try:
        from user_sessions import touch_manifest

        title = script_data.get("title")
        if isinstance(title, str) and title.strip():
            touch_manifest(workspace, name=title.strip())
        else:
            touch_manifest(workspace)
    except Exception:
        pass
    try:
        from project_r2 import sync_workspace_file

        sync_workspace_file(workspace, SCRIPT_NAME)
    except Exception:
        pass
    return project_status(workspace)


def save_audio(workspace: Path, audio_bytes: bytes) -> dict[str, Any]:
    paths = workspace_paths(workspace)
    paths["audio"].write_bytes(audio_bytes)
    if paths["timestamps"].exists():
        paths["timestamps"].unlink()
    try:
        from project_r2 import sync_workspace_file

        sync_workspace_file(workspace, AUDIO_NAME)
    except Exception:
        pass
    return project_status(workspace)


def timestamps_job_snapshot(workspace: Path) -> dict[str, Any]:
    with _timestamps_lock:
        return dict(_get_timestamps_state_unlocked(workspace))


def start_segment_timestamps(
    workspace: Path,
    *,
    model: str = "small",
    on_complete: Callable[[], None] | None = None,
) -> dict[str, Any]:
    global _timestamps_workspace
    paths = workspace_paths(workspace)
    if not paths["script"].exists():
        raise RuntimeError("Upload script.json before segmenting timestamps.")
    if not paths["audio"].exists():
        raise RuntimeError("Upload script.mp3 before segmenting timestamps.")

    with _timestamps_lock:
        if _get_timestamps_state_unlocked(workspace).get("status") == "running":
            raise RuntimeError("Timestamp segmentation already in progress.")

    with _timestamps_lock:
        state = _get_timestamps_state_unlocked(workspace)
        state["logs"] = []
        state["restart_required"] = False

    _set_timestamps_state(
        workspace,
        status="running",
        message="Starting Whisper alignment…",
        error=None,
        started_at=time.time(),
        progress_percent=0,
        stage="prepare",
    )

    def on_progress(percent: int, message: str, stage: str) -> None:
        _set_timestamps_state(
            workspace,
            progress_percent=percent,
            message=message,
            stage=stage,
        )

    def on_hardware(stats: dict[str, Any]) -> None:
        hw_device[0] = str(stats.get("device", "cpu"))
        hw_info[0] = stats
        _set_timestamps_state(workspace, hardware=stats)

    hw_stop = threading.Event()
    hw_device = ["cpu"]
    hw_info: list[dict[str, Any]] = [{}]

    def hardware_monitor_loop() -> None:
        from hardware_monitor import sample_hardware_stats

        while not hw_stop.wait(1.5):
            stats = sample_hardware_stats(hw_device[0], hw_info[0] or None)
            _set_timestamps_state(workspace, hardware=stats)

    def worker() -> None:
        hw_thread = threading.Thread(target=hardware_monitor_loop, daemon=True)
        hw_thread.start()
        try:
            timeline = generate_segment_timestamps(
                paths["workspace"],
                script_path=paths["script"],
                audio_path=paths["audio"],
                model=model,
                on_progress=on_progress,
                on_hardware=on_hardware,
            )
            aligned = timeline.get("summary", {}).get("aligned_segments", 0)
            total = timeline.get("summary", {}).get("total_segments", 0)
            _set_timestamps_state(
                workspace,
                status="done",
                message=f"Aligned {aligned}/{total} segments.",
                error=None,
                progress_percent=100,
                stage="done",
                restart_required=False,
            )
            try:
                from project_r2 import sync_workspace_file

                sync_workspace_file(paths["workspace"], TIMESTAMPS_NAME)
            except Exception:
                pass
            if on_complete:
                on_complete()
        except BaseException as exc:
            if isinstance(exc, SystemExit):
                error_text = str(exc) or "Timestamp segmentation aborted."
            else:
                error_text = str(exc)
            _set_timestamps_state(
                workspace,
                status="error",
                message="Timestamp segmentation failed.",
                error=error_text,
                progress_percent=0,
                stage="error",
            )
        finally:
            hw_stop.set()

    threading.Thread(target=worker, daemon=True).start()
    return timestamps_job_snapshot(workspace)


def validate_timestamps_payload(
    timestamps_data: dict[str, Any],
    script_path: Path,
) -> None:
    segments = timestamps_data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("Timestamps JSON must include a non-empty segments array.")

    for index, entry in enumerate(segments):
        if not isinstance(entry, dict):
            raise ValueError(f"Segment at index {index} must be an object.")
        if entry.get("segment_id") is None:
            raise ValueError(f"Segment at index {index} is missing segment_id.")
        timing = entry.get("timing")
        if not isinstance(timing, dict):
            raise ValueError(f"Segment {entry.get('segment_id')} is missing timing.")
        if timing.get("start_seconds") is None:
            raise ValueError(
                f"Segment {entry.get('segment_id')} is missing timing.start_seconds."
            )

    if script_path.exists():
        with script_path.open("r", encoding="utf-8") as infile:
            script_data = json.load(infile)
        script_ids = {
            segment["segment_id"] for segment in iter_script_segments(script_data)
        }
        timestamp_ids = {
            entry["segment_id"]
            for entry in segments
            if entry.get("segment_id") is not None
        }
        missing = sorted(script_ids - timestamp_ids)
        if missing:
            raise ValueError(
                f"Timestamps are missing {len(missing)} script segment(s): {missing[:8]}"
                + ("…" if len(missing) > 8 else "")
            )


def save_timestamps(workspace: Path, timestamps_data: dict[str, Any]) -> dict[str, Any]:
    paths = workspace_paths(workspace)
    if not paths["script"].exists():
        raise RuntimeError("Upload script.json before importing timestamps.")
    if not paths["audio"].exists():
        raise RuntimeError("Upload script.mp3 before importing timestamps.")

    validate_timestamps_payload(timestamps_data, paths["script"])
    paths["timestamps"].write_text(
        json.dumps(timestamps_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        from project_r2 import sync_workspace_file

        sync_workspace_file(workspace, TIMESTAMPS_NAME)
    except Exception:
        pass
    return project_status(workspace)


def parse_multipart_form(body: bytes, content_type: str) -> dict[str, tuple[str, bytes]]:
    """Parse multipart/form-data into {field_name: (filename, content)}."""
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("Missing multipart boundary")

    boundary = match.group("boundary").strip().strip('"').encode("utf-8")
    delimiter = b"--" + boundary
    parts: dict[str, tuple[str, bytes]] = {}

    for chunk in body.split(delimiter):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue

        header_blob, _, payload = chunk.partition(b"\r\n\r\n")
        if not payload:
            continue
        payload = payload.rstrip(b"\r\n")

        headers = header_blob.decode("utf-8", errors="replace").split("\r\n")
        disposition = next((line for line in headers if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        filename = filename_match.group(1) if filename_match else ""
        parts[name] = (filename, payload)

    return parts
