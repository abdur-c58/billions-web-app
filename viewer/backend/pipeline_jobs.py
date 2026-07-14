"""Server-side b-roll fetch + duplicate-clear pipeline (post-Whisper)."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from project_manager import workspace_paths

PIPELINE_JOB_NAME = ".broll_pipeline.json"
STALE_JOB_SECONDS = 30 * 60
MAX_DUPLICATE_PASSES = 5
FETCH_CONCURRENCY = 2

_pipeline_lock = threading.Lock()
_pipeline_states: dict[str, dict[str, Any]] = {}

_default_pipeline_state: dict[str, Any] = {
    "status": "idle",
    "message": "",
    "error": None,
    "started_at": None,
    "updated_at": None,
    "progress_percent": 0,
    "stage": "idle",
    "done": 0,
    "total": 0,
    "cleared": 0,
    "clear_total": 0,
}


def _workspace_key(workspace: Path) -> str:
    return str(workspace.resolve())


def _fresh_pipeline_state() -> dict[str, Any]:
    return dict(_default_pipeline_state)


def _get_state_unlocked(workspace: Path) -> dict[str, Any]:
    key = _workspace_key(workspace)
    state = _pipeline_states.get(key)
    if state is None:
        state = _fresh_pipeline_state()
        _pipeline_states[key] = state
    return state


def forget_pipeline_state(workspace: Path) -> None:
    with _pipeline_lock:
        _pipeline_states.pop(_workspace_key(workspace), None)


def _pipeline_job_path(workspace: Path) -> Path:
    return workspace / PIPELINE_JOB_NAME


def _persist_state(workspace: Path) -> None:
    path = _pipeline_job_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _pipeline_lock:
        snapshot = dict(_get_state_unlocked(workspace))
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _set_pipeline_state(workspace: Path, **kwargs: Any) -> None:
    with _pipeline_lock:
        state = _get_state_unlocked(workspace)
        kwargs["updated_at"] = time.time()
        state.update(kwargs)
    _persist_state(workspace)


def pipeline_job_snapshot(workspace: Path) -> dict[str, Any]:
    with _pipeline_lock:
        return dict(_get_state_unlocked(workspace))


def reset_pipeline_job_state(workspace: Path) -> None:
    with _pipeline_lock:
        _pipeline_states[_workspace_key(workspace)] = _fresh_pipeline_state()
    _persist_state(workspace)


def load_pipeline_job_state(workspace: Path, *, recover_on_startup: bool = False) -> None:
    path = _pipeline_job_path(workspace)
    state = _fresh_pipeline_state()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as infile:
                payload = json.load(infile)
            if isinstance(payload, dict):
                state.update(payload)
        except (json.JSONDecodeError, OSError):
            pass

    if state.get("status") == "running":
        should_recover = recover_on_startup
        if not should_recover:
            updated_at = float(state.get("updated_at") or 0)
            if updated_at and time.time() - updated_at > STALE_JOB_SECONDS:
                should_recover = True
        if should_recover:
            state.update(
                {
                    "status": "error",
                    "message": "B-roll pipeline interrupted — reopen or re-run.",
                    "error": "Server restarted or job stalled during b-roll pipeline.",
                    "stage": "error",
                    "progress_percent": 0,
                }
            )

    with _pipeline_lock:
        _pipeline_states[_workspace_key(workspace)] = state
    if state.get("status") == "error" and recover_on_startup:
        _persist_state(workspace)


def load_all_pipeline_job_states(workspace_root: Path) -> None:
    from user_sessions import projects_root

    root = projects_root(workspace_root)
    if not root.exists():
        return
    for child in root.iterdir():
        if child.is_dir():
            load_pipeline_job_state(child, recover_on_startup=True)


def segment_needs_broll(segment: dict[str, Any]) -> bool:
    if segment.get("render_mode") != "remotion":
        return True
    remotion = segment.get("remotion") or {}
    layout = str(remotion.get("layout") or "").strip().lower()
    return layout in {"split-right", "overlay"}


def segment_has_broll_coverage(segment: dict[str, Any]) -> bool:
    if not segment_needs_broll(segment):
        return True
    selection = segment.get("selection") or {}
    return bool(selection.get("url"))


def compute_broll_counts(rows: list[dict[str, Any]]) -> tuple[int, int]:
    needed = [row for row in rows if segment_needs_broll(row)]
    total = len(needed)
    fetched = sum(1 for row in needed if segment_has_broll_coverage(row))
    return fetched, total


def _timed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timed: list[dict[str, Any]] = []
    for row in rows:
        timing = row.get("timing") or {}
        if timing.get("start_seconds") is None or timing.get("end_seconds") is None:
            continue
        timed.append(row)
    return timed


def _duplicate_segment_ids(rows: list[dict[str, Any]]) -> list[int]:
    from flagged_clips import find_duplicate_clips

    duplicates = find_duplicate_clips(rows)
    ids: set[int] = set()
    for group in duplicates:
        for segment_id in group.get("segment_ids") or []:
            try:
                ids.add(int(segment_id))
            except (TypeError, ValueError):
                continue
    return sorted(ids)


def compute_list_status(
    *,
    script_exists: bool,
    audio_exists: bool,
    timestamps_exists: bool,
    tts_job: dict[str, Any],
    timestamps_job: dict[str, Any],
    pipeline_job: dict[str, Any],
    export_job: dict[str, Any],
    broll_fetched: int,
    broll_total: int,
    duplicates_remaining: int,
    manual_refetch_done: bool,
) -> str:
    export_status = str(export_job.get("status") or "idle")
    if export_status == "done":
        return "complete"
    if export_status == "running":
        return "exporting"

    pipeline_status = str(pipeline_job.get("status") or "idle")
    pipeline_stage = str(pipeline_job.get("stage") or "")
    if pipeline_status == "running":
        if pipeline_stage == "clear_duplicates":
            return "clearing_duplicates"
        return "fetching_broll"

    if tts_job.get("status") == "running":
        return "generating_voice"
    if timestamps_job.get("status") == "running":
        return "segmenting"

    if not script_exists:
        return "needs_script"
    if not audio_exists:
        return "needs_audio"
    if not timestamps_exists:
        return "needs_timestamps"

    if broll_total <= 0:
        return "ready_for_refetch" if not manual_refetch_done else "ready_for_export"

    if broll_fetched < broll_total:
        return "fetching_broll" if pipeline_status == "running" else "ready_for_broll"

    if duplicates_remaining > 0:
        return "clearing_duplicates" if pipeline_status == "running" else "ready_for_broll"

    if manual_refetch_done:
        return "ready_for_export"
    return "ready_for_refetch"


def start_broll_pipeline(workspace: Path) -> dict[str, Any]:
    paths = workspace_paths(workspace)
    if not paths["script"].exists() or not paths["timestamps"].exists():
        raise RuntimeError("Script and timestamps are required before b-roll pipeline.")

    with _pipeline_lock:
        if _get_state_unlocked(workspace).get("status") == "running":
            return pipeline_job_snapshot(workspace)

    _set_pipeline_state(
        workspace,
        status="running",
        stage="fetch_broll",
        message="Starting b-roll fetch…",
        error=None,
        started_at=time.time(),
        progress_percent=0,
        done=0,
        total=0,
        cleared=0,
        clear_total=0,
    )

    def worker() -> None:
        try:
            from broll_judge import JudgmentCache
            from broll_viewer import build_segment_rows, fetch_segment_video

            cache_dir = paths["cache"]
            flagged_path = paths["flagged"]
            judgment_cache = JudgmentCache(cache_dir)

            def load_rows() -> list[dict[str, Any]]:
                return _timed_rows(
                    build_segment_rows(
                        paths["script"],
                        paths["timestamps"],
                        paths["selections"],
                    )
                )

            rows = load_rows()
            missing = [
                row
                for row in rows
                if segment_needs_broll(row) and not segment_has_broll_coverage(row)
            ]
            needed_total = sum(1 for row in rows if segment_needs_broll(row))
            already = needed_total - len(missing)
            _set_pipeline_state(
                workspace,
                stage="fetch_broll",
                message=f"Fetching b-roll ({already}/{needed_total})…",
                done=already,
                total=needed_total,
                progress_percent=int((already / needed_total) * 70) if needed_total else 70,
            )

            def fetch_one(row: dict[str, Any]) -> None:
                fetch_segment_video(
                    paths["selections"],
                    paths["script"],
                    int(row["segment_id"]),
                    str(row.get("search_query") or row.get("description") or ""),
                    refetch=False,
                    provider_override="mix",
                    segment=row,
                    cache_dir=cache_dir,
                    judgment_cache=judgment_cache,
                    flagged_path=flagged_path,
                )

            completed = already
            if missing:
                with ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY) as pool:
                    futures = {pool.submit(fetch_one, row): row for row in missing}
                    for future in as_completed(futures):
                        row = futures[future]
                        try:
                            future.result()
                        except Exception as exc:
                            print(
                                f"[pipeline] fetch failed segment "
                                f"{row.get('segment_id')}: {exc}"
                            )
                        completed += 1
                        _set_pipeline_state(
                            workspace,
                            stage="fetch_broll",
                            message=f"Fetching b-roll ({completed}/{needed_total})…",
                            done=completed,
                            total=needed_total,
                            progress_percent=int((completed / max(needed_total, 1)) * 70),
                        )

            rows = load_rows()
            fetched, total = compute_broll_counts(rows)
            if total > 0 and fetched < total:
                _set_pipeline_state(
                    workspace,
                    status="error",
                    stage="error",
                    message=f"B-roll incomplete ({fetched}/{total}).",
                    error=f"Only fetched {fetched} of {total} required segments.",
                    done=fetched,
                    total=total,
                    progress_percent=70,
                )
                return

            # Clear duplicates until none remain.
            initial_ids = _duplicate_segment_ids(rows)
            clear_total = len(initial_ids)
            cleared_ids: set[int] = set()
            _set_pipeline_state(
                workspace,
                stage="clear_duplicates",
                message=(
                    "No duplicates found."
                    if clear_total == 0
                    else f"Clearing duplicates (0/{clear_total})…"
                ),
                done=fetched,
                total=total,
                cleared=0,
                clear_total=clear_total,
                progress_percent=75 if clear_total else 100,
            )

            cleared_cleanly = clear_total == 0
            for _pass_index in range(MAX_DUPLICATE_PASSES):
                rows = load_rows()
                affected = _duplicate_segment_ids(rows)
                if not affected:
                    cleared_cleanly = True
                    break
                if clear_total == 0:
                    clear_total = len(affected)
                for segment_id in affected:
                    row = next((r for r in rows if int(r["segment_id"]) == segment_id), None)
                    if row is None or not segment_needs_broll(row):
                        continue
                    try:
                        fetch_segment_video(
                            paths["selections"],
                            paths["script"],
                            segment_id,
                            str(row.get("search_query") or row.get("description") or ""),
                            refetch=True,
                            provider_override="mix",
                            segment=row,
                            cache_dir=cache_dir,
                            judgment_cache=judgment_cache,
                            flagged_path=flagged_path,
                        )
                    except Exception as exc:
                        print(f"[pipeline] duplicate refetch failed segment {segment_id}: {exc}")
                    cleared_ids.add(segment_id)
                    _set_pipeline_state(
                        workspace,
                        stage="clear_duplicates",
                        message=f"Clearing duplicates ({len(cleared_ids)}/{max(clear_total, 1)})…",
                        cleared=len(cleared_ids),
                        clear_total=max(clear_total, len(cleared_ids)),
                        progress_percent=min(
                            99,
                            75 + int((len(cleared_ids) / max(clear_total, 1)) * 24),
                        ),
                    )

            rows = load_rows()
            if not cleared_cleanly and _duplicate_segment_ids(rows):
                remaining = len(_duplicate_segment_ids(rows))
                _set_pipeline_state(
                    workspace,
                    status="error",
                    stage="error",
                    message=f"Could not clear all duplicates ({remaining} left).",
                    error=(
                        f"Still {remaining} duplicate-affected segment(s) after "
                        f"{MAX_DUPLICATE_PASSES} passes."
                    ),
                    cleared=len(cleared_ids),
                    clear_total=max(clear_total, len(cleared_ids)),
                    progress_percent=99,
                )
                return

            fetched, total = compute_broll_counts(rows)
            _set_pipeline_state(
                workspace,
                status="done",
                stage="done",
                message="B-roll ready — review and refetch at least one clip before export.",
                error=None,
                done=fetched,
                total=total,
                cleared=len(cleared_ids),
                clear_total=max(clear_total, len(cleared_ids)),
                progress_percent=100,
            )
        except BaseException as exc:
            _set_pipeline_state(
                workspace,
                status="error",
                stage="error",
                message="B-roll pipeline failed.",
                error=str(exc) or "Pipeline failed.",
                progress_percent=0,
            )

    threading.Thread(target=worker, daemon=True).start()
    return pipeline_job_snapshot(workspace)
