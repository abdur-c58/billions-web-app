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
    clear_resegment_artifacts,
    generate_segment_timestamps,
    iter_script_segments,
)

SCRIPT_NAME = "script.json"
AUDIO_NAME = "script.mp3"
TIMESTAMPS_NAME = "segment_timestamps.json"
SELECTIONS_NAME = "broll_selections.json"
TIMESTAMPS_JOB_NAME = ".timestamps_job.json"
TTS_JOB_NAME = ".tts_job.json"
STALE_JOB_SECONDS = 15 * 60

_timestamps_lock = threading.Lock()
_tts_lock = threading.Lock()
_tts_cancel_events: dict[str, threading.Event] = {}
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
    "alignment_summary": None,
}

_default_tts_state: dict[str, Any] = {
    "status": "idle",
    "message": "",
    "error": None,
    "started_at": None,
    "updated_at": None,
    "progress_percent": 0,
    "stage": "idle",
    "logs": [],
    "restart_required": False,
    "chunk_total": 0,
    "chunk_done": 0,
    "word_count": 0,
    "estimated_duration_seconds": 0.0,
    "estimated_duration_label": "",
}


def _alignment_summary_from_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    summary = timeline.get("summary") or {}
    total = int(summary.get("total_segments") or 0)
    aligned = int(summary.get("aligned_segments") or 0)
    timed = int(summary.get("timed_segments") or 0)
    return {
        "total_segments": total,
        "aligned_segments": aligned,
        "timed_segments": timed,
        "interpolated_segments": int(summary.get("interpolated_segments") or 0),
        "estimated_segments": int(summary.get("estimated_segments") or 0),
        "total_duration_seconds": float(summary.get("total_duration_seconds") or 0),
        "total_duration_timecode": str(summary.get("total_duration_timecode") or ""),
    }


def _alignment_summary_from_timestamps_file(timestamps_data: dict[str, Any]) -> dict[str, Any] | None:
    file_summary = timestamps_data.get("summary")
    if not isinstance(file_summary, dict):
        return None
    timed_segments = file_summary.get("timed_segments")
    if timed_segments is None:
        segments = timestamps_data.get("segments") or []
        timed_segments = sum(
            1
            for segment in segments
            if segment.get("timing", {}).get("start_seconds") is not None
            and segment.get("timing", {}).get("end_seconds") is not None
        )
    total_segments = int(file_summary.get("total_segments") or 0)
    return {
        "total_segments": total_segments,
        "aligned_segments": int(file_summary.get("aligned_segments") or 0),
        "timed_segments": int(timed_segments),
        "interpolated_segments": int(file_summary.get("interpolated_segments") or 0),
        "estimated_segments": int(file_summary.get("estimated_segments") or 0),
        "total_duration_seconds": float(file_summary.get("total_duration_seconds") or 0),
        "total_duration_timecode": str(file_summary.get("total_duration_timecode") or ""),
        "whisper_model": str((timestamps_data.get("timing_method") or {}).get("whisper_model") or ""),
    }


def _format_alignment_message(summary: dict[str, Any]) -> str:
    aligned = summary.get("aligned_segments", 0)
    total = summary.get("total_segments", 0)
    timed = summary.get("timed_segments", 0)
    duration = summary.get("total_duration_timecode") or ""
    parts = [f"Whisper aligned {aligned}/{total} segments"]
    if timed != total:
        parts.append(f"{timed}/{total} timestamps assigned")
    else:
        parts.append(f"{timed} timestamps assigned")
    if duration:
        parts.append(f"span {duration}")
    return " · ".join(parts) + "."


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
_tts_states: dict[str, dict[str, Any]] = {}


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


def _fresh_tts_state() -> dict[str, Any]:
    return dict(_default_tts_state)


def _get_tts_state_unlocked(workspace: Path) -> dict[str, Any]:
    key = _workspace_key(workspace)
    state = _tts_states.get(key)
    if state is None:
        state = _fresh_tts_state()
        _tts_states[key] = state
    return state


def forget_tts_state(workspace: Path) -> None:
    with _tts_lock:
        _tts_states.pop(_workspace_key(workspace), None)
        _tts_cancel_events.pop(_workspace_key(workspace), None)


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
        "tts_job": workspace / TTS_JOB_NAME,
    }


def _timestamps_job_path(workspace: Path) -> Path:
    return workspace_paths(workspace)["timestamps_job"]


def _tts_job_path(workspace: Path) -> Path:
    return workspace_paths(workspace)["tts_job"]


def _persist_timestamps_state(workspace: Path) -> None:
    path = _timestamps_job_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _timestamps_lock:
        snapshot = dict(_get_timestamps_state_unlocked(workspace))
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _persist_tts_state(workspace: Path) -> None:
    path = _tts_job_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _tts_lock:
        snapshot = dict(_get_tts_state_unlocked(workspace))
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _set_tts_state(workspace: Path, **kwargs: Any) -> None:
    with _tts_lock:
        state = _get_tts_state_unlocked(workspace)
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
    _persist_tts_state(workspace)


def clear_tts_recovery_artifacts(workspace: Path) -> list[str]:
    paths = workspace_paths(workspace)
    removed: list[str] = []
    tts_dir = paths["workspace"] / ".tts_chunks"
    if tts_dir.exists():
        shutil.rmtree(tts_dir, ignore_errors=True)
        removed.append(".tts_chunks/")
    return removed


def _recover_interrupted_tts_job(workspace: Path, state: dict[str, Any]) -> None:
    removed = clear_tts_recovery_artifacts(workspace)
    removed_note = ", ".join(removed) if removed else "nothing to clear"
    _append_job_log(
        state,
        message=f"Server restarted during narration generation — cleared: {removed_note}",
        stage="error",
        progress_percent=0,
    )
    state.update(
        {
            "status": "error",
            "message": "Narration generation interrupted — try again.",
            "error": (
                "The server restarted while generating narration. Partial audio chunks "
                "were cleared to avoid corrupt files."
            ),
            "progress_percent": 0,
            "stage": "error",
            "restart_required": True,
        }
    )


def load_tts_job_state(workspace: Path, *, recover_on_startup: bool = False) -> None:
    path = _tts_job_path(workspace)
    state = _fresh_tts_state()
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
            _recover_interrupted_tts_job(workspace, state)
            recovered = True
        else:
            updated_at = float(state.get("updated_at") or 0)
            if updated_at and time.time() - updated_at > STALE_JOB_SECONDS:
                _recover_interrupted_tts_job(workspace, state)
                recovered = True
    else:
        recovered = False

    if "progress_percent" not in state:
        state["progress_percent"] = 0
    if "stage" not in state:
        state["stage"] = state.get("status", "idle")
    if "restart_required" not in state:
        state["restart_required"] = False

    with _tts_lock:
        _tts_states[_workspace_key(workspace)] = state

    if recovered:
        _persist_tts_state(workspace)


def load_all_tts_job_states(workspace_root: Path) -> None:
    for workspace in _iter_project_workspaces(workspace_root):
        load_tts_job_state(workspace, recover_on_startup=True)


def tts_job_snapshot(workspace: Path) -> dict[str, Any]:
    with _tts_lock:
        return dict(_get_tts_state_unlocked(workspace))


def reset_tts_job_state(workspace: Path) -> None:
    with _tts_lock:
        _tts_states[_workspace_key(workspace)] = _fresh_tts_state()
    _persist_tts_state(workspace)


def _build_transcript_preview(script_path: Path) -> dict[str, Any] | None:
    if not script_path.exists():
        return None
    try:
        from fish_audio_tts import build_transcript_preview
        from script_format import build_narration_transcript, iter_content_segments

        with script_path.open("r", encoding="utf-8") as infile:
            script_data = json.load(infile)
        transcript = build_narration_transcript(script_data)
        segment_count = len(iter_content_segments(script_data))
        return build_transcript_preview(transcript, segment_count)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def cancel_audio_generation(workspace: Path, *, reason: str = "Cancelled.") -> dict[str, Any]:
    key = _workspace_key(workspace)
    with _tts_lock:
        state = _get_tts_state_unlocked(workspace)
        if state.get("status") != "running":
            return dict(state)
        cancel_event = _tts_cancel_events.get(key)
        if cancel_event:
            cancel_event.set()

    _set_tts_state(
        workspace,
        status="error",
        message="Narration generation cancelled.",
        error=reason,
        progress_percent=0,
        stage="error",
    )
    clear_tts_recovery_artifacts(workspace)
    return tts_job_snapshot(workspace)


def start_audio_generation(
    workspace: Path,
    *,
    on_complete: Callable[[], None] | None = None,
) -> dict[str, Any]:
    from fish_audio_tts import (
        synthesize_transcript_to_file,
        validate_fish_config,
    )
    from script_format import build_narration_transcript

    paths = workspace_paths(workspace)
    if not paths["script"].exists():
        raise RuntimeError("Upload script.json before generating narration.")

    with _tts_lock:
        if _get_tts_state_unlocked(workspace).get("status") == "running":
            raise RuntimeError("Narration generation already in progress.")
        if paths["audio"].exists():
            raise RuntimeError("script.mp3 already exists — upload manually or delete it first.")

    config = validate_fish_config()
    preview = _build_transcript_preview(paths["script"])
    if not preview:
        raise RuntimeError("Could not build transcript from script.json.")

    key = _workspace_key(workspace)
    cancel_event = threading.Event()
    with _tts_lock:
        _tts_cancel_events[key] = cancel_event
        state = _get_tts_state_unlocked(workspace)
        state["logs"] = []
        state["restart_required"] = False

    _set_tts_state(
        workspace,
        status="running",
        message="Preparing narration transcript…",
        error=None,
        started_at=time.time(),
        progress_percent=0,
        stage="prepare",
        chunk_total=0,
        chunk_done=0,
        word_count=preview["word_count"],
        estimated_duration_seconds=preview["estimated_duration_seconds"],
        estimated_duration_label=preview["estimated_duration_label"],
    )

    def on_progress(
        percent: int,
        message: str,
        stage: str,
        chunk_done: int,
        chunk_total: int,
    ) -> None:
        _set_tts_state(
            workspace,
            progress_percent=percent,
            message=message,
            stage=stage,
            chunk_done=chunk_done,
            chunk_total=chunk_total,
        )

    def worker() -> None:
        temp_output = paths["workspace"] / ".tts_output.mp3"
        try:
            with paths["script"].open("r", encoding="utf-8") as infile:
                script_data = json.load(infile)
            transcript = build_narration_transcript(script_data)

            _set_tts_state(
                workspace,
                message="Starting Fish Audio synthesis…",
                stage="prepare",
                progress_percent=2,
            )

            synthesize_transcript_to_file(
                transcript,
                temp_output,
                config,
                on_progress=on_progress,
                should_cancel=cancel_event.is_set,
            )

            if cancel_event.is_set():
                raise RuntimeError("Narration generation cancelled.")

            audio_bytes = temp_output.read_bytes()
            save_audio(workspace, audio_bytes, from_tts=True)

            _set_tts_state(
                workspace,
                status="done",
                message="Narration audio saved — starting Whisper alignment…",
                error=None,
                progress_percent=100,
                stage="done",
                restart_required=False,
            )

            start_segment_timestamps(workspace, model="medium", on_complete=on_complete)
        except BaseException as exc:
            if isinstance(exc, SystemExit):
                error_text = str(exc) or "Narration generation aborted."
            else:
                error_text = str(exc)
            if cancel_event.is_set() and "cancel" in error_text.lower():
                _set_tts_state(
                    workspace,
                    status="error",
                    message="Narration generation cancelled.",
                    error=error_text,
                    progress_percent=0,
                    stage="error",
                )
            else:
                _set_tts_state(
                    workspace,
                    status="error",
                    message="Narration generation failed.",
                    error=error_text,
                    progress_percent=0,
                    stage="error",
                )
            clear_tts_recovery_artifacts(workspace)
        finally:
            temp_output.unlink(missing_ok=True)
            with _tts_lock:
                _tts_cancel_events.pop(key, None)

    threading.Thread(target=worker, daemon=True).start()
    return tts_job_snapshot(workspace)


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
    remotion_summary: dict[str, Any] | None = None
    script_summary: dict[str, Any] | None = None
    if script_exists:
        try:
            with paths["script"].open("r", encoding="utf-8") as infile:
                script_data = json.load(infile)
            from script_format import analyze_script_remotion, build_script_summary, detect_script_format

            script_summary = build_script_summary(script_data)
            script_title = script_summary.get("title")
            segment_count = int(script_summary.get("segment_count") or 0)
            script_format = script_summary.get("script_format")
            remotion_summary = script_summary.get("remotion")
        except (json.JSONDecodeError, OSError, ValueError):
            script_title = None
            script_format = None
            remotion_summary = None
            script_summary = None

    aligned_segments = 0
    timed_segments = 0
    timestamp_alignment: dict[str, Any] | None = None
    if timestamps_exists:
        try:
            with paths["timestamps"].open("r", encoding="utf-8") as infile:
                timestamps_data = json.load(infile)
            timestamp_alignment = _alignment_summary_from_timestamps_file(timestamps_data)
            if timestamp_alignment:
                aligned_segments = timestamp_alignment["aligned_segments"]
                timed_segments = timestamp_alignment["timed_segments"]
                segment_count = timestamp_alignment["total_segments"] or segment_count
        except (json.JSONDecodeError, OSError):
            pass

    ready = script_exists and audio_exists and timestamps_exists
    with _timestamps_lock:
        timestamps_job = dict(_get_timestamps_state_unlocked(workspace))
    with _tts_lock:
        tts_job = dict(_get_tts_state_unlocked(workspace))

    transcript_preview = _build_transcript_preview(paths["script"]) if script_exists else None

    from user_sessions import parse_workspace_scope

    project_id = parse_workspace_scope(workspace)
    from remotion_render import remotion_available

    return {
        "workspace": str(workspace.resolve()),
        "project_id": project_id,
        "script_uploaded": script_exists,
        "audio_uploaded": audio_exists,
        "timestamps_ready": timestamps_exists,
        "viewer_ready": ready,
        "title": script_title,
        "script_format": script_format,
        "remotion": remotion_summary,
        "remotion_runtime_ready": remotion_available(),
        "segment_count": segment_count,
        "aligned_segments": aligned_segments,
        "timed_segments": timed_segments,
        "timestamp_alignment": timestamp_alignment,
        "timestamps_job": timestamps_job,
        "tts_job": tts_job,
        "transcript_preview": transcript_preview,
        "script_summary": script_summary,
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
    from script_format import analyze_script_remotion, validate_script_payload

    validate_script_payload(script_data)
    paths = workspace_paths(workspace)
    paths["script"].write_text(
        json.dumps(script_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if paths["timestamps"].exists():
        paths["timestamps"].unlink()
    if paths["audio"].exists():
        paths["audio"].unlink()
    reset_tts_job_state(workspace)
    clear_tts_recovery_artifacts(workspace)
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


def save_audio(workspace: Path, audio_bytes: bytes, *, from_tts: bool = False) -> dict[str, Any]:
    paths = workspace_paths(workspace)
    if not from_tts:
        with _tts_lock:
            tts_status = _get_tts_state_unlocked(workspace).get("status")
        if tts_status == "running":
            cancel_audio_generation(workspace, reason="Manual audio upload cancelled generation.")
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
    model: str = "medium",
    retranscribe: bool = False,
    on_complete: Callable[[], None] | None = None,
) -> dict[str, Any]:
    from segment_timestamps import normalize_whisper_model

    model = normalize_whisper_model(model)
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

    if retranscribe:
        cleared = clear_resegment_artifacts(
            paths["workspace"],
            audio_path=paths["audio"],
            output_path=paths["timestamps"],
        )
        if cleared:
            message = f"Cleared {', '.join(cleared[:3])}"
            if len(cleared) > 3:
                message += f" (+{len(cleared) - 3} more)"
            _set_timestamps_state(
                workspace,
                message=message,
                stage="prepare",
                progress_percent=1,
            )

    _set_timestamps_state(
        workspace,
        status="running",
        message="Starting Whisper alignment…",
        error=None,
        started_at=time.time(),
        progress_percent=0,
        stage="prepare",
        alignment_summary=None,
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
                retranscribe=retranscribe,
                on_progress=on_progress,
                on_hardware=on_hardware,
            )
            alignment_summary = _alignment_summary_from_timeline(timeline)
            _set_timestamps_state(
                workspace,
                status="done",
                message=_format_alignment_message(alignment_summary),
                error=None,
                progress_percent=100,
                stage="done",
                restart_required=False,
                alignment_summary=alignment_summary,
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
