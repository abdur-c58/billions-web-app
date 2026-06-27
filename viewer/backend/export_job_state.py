"""Per-project export job state — no database; each workspace keeps .broll_export_status.json."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from export_video import summarize_export_error

_export_lock = threading.Lock()
_export_states: dict[str, dict[str, Any]] = {}
_export_cancel_events: dict[str, threading.Event] = {}


def default_export_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "stage": "",
        "current": 0,
        "total": 0,
        "message": "",
        "output": None,
        "encoder": None,
        "error": None,
        "started_at": None,
        "updated_at": None,
        "progress_percent": 0,
        "elapsed_seconds": 0,
        "eta_seconds": None,
        "hardware": None,
        "project_id": None,
        "project_name": None,
        "download_started_at": None,
        "render_started_at": None,
        "download_seconds": 0,
        "render_seconds": 0,
        "inputs_hash": None,
        "r2_key": None,
    }


def compute_export_inputs_hash(
    *,
    timestamps_path: Path,
    selections_path: Path,
    audio_path: Path,
) -> str:
    """Fingerprint of files that affect export output (selections, timing, narration)."""
    hasher = hashlib.sha256()
    for path in (timestamps_path, selections_path):
        if path.exists():
            hasher.update(path.read_bytes())
    if audio_path.exists():
        # Hash up to the first 4 MB of audio — enough to detect any replacement
        # without reading a full 100+ MB file on every request.
        with audio_path.open("rb") as fh:
            hasher.update(fh.read(4 * 1024 * 1024))
    return hasher.hexdigest()[:32]


def compute_progress_percent(stage: str, current: int, total: int, status: str) -> int:
    if status == "done":
        return 100
    if status != "running":
        return 0
    if stage == "prepare":
        if total <= 0:
            return 0
        return min(88, max(1, int((current / total) * 88)))
    if stage == "concat":
        return 91
    if stage == "audio":
        return 94
    if stage == "encode":
        return 97
    return 0


def enrich_export_state(state: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(state)
    status = enriched.get("status", "idle")
    stage = enriched.get("stage", "")
    current = int(enriched.get("current") or 0)
    total = int(enriched.get("total") or 0)

    progress_percent = compute_progress_percent(stage, current, total, status)
    enriched["progress_percent"] = progress_percent

    started_at = enriched.get("started_at")
    if status == "running" and started_at and progress_percent > 0:
        elapsed = max(0.0, time.time() - float(started_at))
        enriched["elapsed_seconds"] = int(elapsed)
        enriched["eta_seconds"] = int(elapsed * (100 - progress_percent) / progress_percent)
    elif status == "done" and started_at:
        enriched["elapsed_seconds"] = int(max(0.0, time.time() - float(started_at)))
        enriched["eta_seconds"] = 0
    else:
        enriched["elapsed_seconds"] = int(enriched.get("elapsed_seconds") or 0)
        enriched["eta_seconds"] = None

    now = time.time()
    end_time = now if status == "running" else float(enriched.get("updated_at") or now)
    dl_start = enriched.get("download_started_at")
    rn_start = enriched.get("render_started_at")
    if dl_start:
        dl_end = float(rn_start) if rn_start else end_time
        enriched["download_seconds"] = int(max(0.0, dl_end - float(dl_start)))
    else:
        enriched["download_seconds"] = int(enriched.get("download_seconds") or 0)
    if rn_start:
        enriched["render_seconds"] = int(max(0.0, end_time - float(rn_start)))
    else:
        enriched["render_seconds"] = int(enriched.get("render_seconds") or 0)

    return enriched


def _normalize_loaded_state(saved: dict[str, Any]) -> dict[str, Any]:
    if saved.get("status") == "running":
        saved["status"] = "interrupted"
        saved["stage"] = "interrupted"
        saved["message"] = "Export was interrupted when the server restarted."
        saved["error"] = saved["message"]

    if saved.get("status") == "error":
        raw = str(saved.get("error") or saved.get("message") or "")
        if len(raw) > 300:
            short = summarize_export_error(RuntimeError(raw))
            saved["error"] = short
            saved["message"] = short

    return {**default_export_state(), **saved}


def read_export_state_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_export_state()
    try:
        with path.open("r", encoding="utf-8") as infile:
            saved = json.load(infile)
    except (json.JSONDecodeError, OSError):
        return default_export_state()
    if not isinstance(saved, dict):
        return default_export_state()
    return _normalize_loaded_state(saved)


def save_export_state_file(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_cancel_event(project_id: str) -> threading.Event:
    with _export_lock:
        event = _export_cancel_events.get(project_id)
        if event is None:
            event = threading.Event()
            _export_cancel_events[project_id] = event
        return event


def clear_cancel_event(project_id: str) -> None:
    with _export_lock:
        event = _export_cancel_events.get(project_id)
        if event is not None:
            event.clear()


def set_cancel_event(project_id: str) -> None:
    get_cancel_event(project_id).set()


def load_project_export_state(project_id: str, status_file: Path) -> dict[str, Any]:
    with _export_lock:
        if project_id in _export_states:
            return _export_states[project_id]
        state = read_export_state_file(status_file) if status_file.exists() else default_export_state()
        state["project_id"] = project_id
        _export_states[project_id] = state
        return state


def export_snapshot(project_id: str, status_file: Path) -> dict[str, Any]:
    with _export_lock:
        state = _export_states.get(project_id)
        if state is None and status_file.exists():
            state = read_export_state_file(status_file)
            state["project_id"] = project_id
            _export_states[project_id] = state
        if state is None:
            state = default_export_state()
            state["project_id"] = project_id
        return enrich_export_state(dict(state))


def update_export_state(project_id: str, status_file: Path, **kwargs: Any) -> dict[str, Any]:
    # Callers sometimes pass project_id/project_name as kwargs for convenience;
    # remove them to avoid a "multiple values" error — we always set them explicitly.
    kwargs.pop("project_id", None)
    kwargs.pop("project_name", None)

    with _export_lock:
        state = _export_states.get(project_id)
        if state is None:
            state = default_export_state()
            _export_states[project_id] = state
        state["project_id"] = project_id

        if kwargs.get("status") == "running" and state.get("status") != "running":
            kwargs.setdefault("started_at", time.time())
            kwargs.setdefault("progress_percent", 0)
            kwargs.setdefault("elapsed_seconds", 0)
            kwargs.setdefault("eta_seconds", None)

        kwargs["updated_at"] = time.time()
        state.update(kwargs)

        now = time.time()
        current_stage = str(state.get("stage", ""))
        if current_stage == "download" and state.get("download_started_at") is None:
            state["download_started_at"] = now
        if current_stage in ("prepare", "concat", "audio", "encode") and state.get("render_started_at") is None:
            state["render_started_at"] = now

        stage = str(state.get("stage", ""))
        current = int(state.get("current") or 0)
        total = int(state.get("total") or 0)
        status = str(state.get("status", "idle"))
        state["progress_percent"] = compute_progress_percent(stage, current, total, status)

        save_export_state_file(status_file, state)
        return state


def project_export_running(project_id: str) -> bool:
    with _export_lock:
        state = _export_states.get(project_id)
        return bool(state and state.get("status") == "running")


def list_running_exports() -> list[dict[str, Any]]:
    with _export_lock:
        running: list[dict[str, Any]] = []
        for project_id, state in _export_states.items():
            if state.get("status") == "running":
                running.append(enrich_export_state({**state, "project_id": project_id}))
        return running


def load_all_export_states(workspace_root: Path) -> None:
    """Restore persisted export state for every project on startup."""
    from user_sessions import list_projects, project_workspace, projects_root

    root = projects_root(workspace_root)
    if not root.exists():
        return

    for project in list_projects(workspace_root):
        project_id = project["id"]
        status_file = project_workspace(workspace_root, project_id) / ".broll_export_status.json"
        load_project_export_state(project_id, status_file)
