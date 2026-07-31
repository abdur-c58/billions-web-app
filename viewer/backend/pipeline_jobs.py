"""Server-side b-roll fetch + duplicate-clear pipeline (post-Whisper)."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from typing import Any

from project_manager import workspace_paths

PIPELINE_JOB_NAME = ".broll_pipeline.json"
STALE_JOB_SECONDS = 30 * 60
# If fetched/cleared count doesn't move for this long while status=running,
# treat the worker as silently hung and restart the pipeline.
PROGRESS_STALL_SECONDS = 60
MAX_DUPLICATE_PASSES = 10
FETCH_CONCURRENCY = 2

_pipeline_lock = threading.Lock()
_pipeline_states: dict[str, dict[str, Any]] = {}
# Bumped every time a new worker is launched for a workspace so a hung
# previous worker stops writing state / claiming work.
_pipeline_run_ids: dict[str, int] = {}

_default_pipeline_state: dict[str, Any] = {
    "status": "idle",
    "message": "",
    "error": None,
    "started_at": None,
    "updated_at": None,
    "progress_changed_at": None,
    "progress_percent": 0,
    "stage": "idle",
    "done": 0,
    "total": 0,
    "cleared": 0,
    "clear_total": 0,
    "failed_segment_ids": [],
}


def _workspace_key(workspace: Path) -> str:
    return str(workspace.resolve())


def _nudge_export_queue(workspace: Path) -> None:
    """Queue export immediately once b-roll is ready, instead of waiting up to
    WATCHDOG_INTERVAL_SECONDS for the next automation scan to notice."""
    try:
        from automation_orchestrator import enqueue_export
        from user_sessions import parse_workspace_scope

        project_id = parse_workspace_scope(workspace)
        if project_id:
            enqueue_export(project_id)
    except Exception as exc:
        print(f"[pipeline] Could not nudge export queue: {exc}")


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
        now = time.time()
        kwargs["updated_at"] = now
        # Track when fetch/clear progress actually moves so we can detect
        # silent hangs (status stays "running" but done/cleared never changes).
        progress_keys = ("done", "cleared", "total", "clear_total", "stage")
        if any(key in kwargs and kwargs[key] != state.get(key) for key in progress_keys):
            kwargs["progress_changed_at"] = now
        elif state.get("progress_changed_at") is None and kwargs.get("status") == "running":
            kwargs["progress_changed_at"] = now
        state.update(kwargs)
    _persist_state(workspace)


def pipeline_job_snapshot(workspace: Path) -> dict[str, Any]:
    with _pipeline_lock:
        return dict(_get_state_unlocked(workspace))


def is_pipeline_stalled(workspace: Path, *, stall_seconds: float = PROGRESS_STALL_SECONDS) -> bool:
    """True when status=running but done/cleared hasn't moved for stall_seconds."""
    state = pipeline_job_snapshot(workspace)
    if str(state.get("status") or "") != "running":
        return False
    marker = state.get("progress_changed_at") or state.get("updated_at") or state.get("started_at")
    if not marker:
        return False
    return (time.time() - float(marker)) >= stall_seconds


def interrupt_stalled_pipeline(workspace: Path) -> bool:
    """Mark a hung running pipeline as interrupted so it can be restarted.

    Returns True if the job was interrupted.
    """
    if not is_pipeline_stalled(workspace):
        return False
    state = pipeline_job_snapshot(workspace)
    done = int(state.get("done") or 0)
    total = int(state.get("total") or 0)
    # Invalidate any hung worker so it stops writing after this point.
    key = _workspace_key(workspace)
    with _pipeline_lock:
        _pipeline_run_ids[key] = int(_pipeline_run_ids.get(key, 0)) + 1
    _set_pipeline_state(
        workspace,
        status="interrupted",
        stage="interrupted",
        message=f"B-roll fetch stalled at {done}/{total} — restarting…",
        error=f"No progress for {PROGRESS_STALL_SECONDS}s while fetching ({done}/{total}).",
    )
    print(f"[pipeline] Stalled fetch interrupted for {workspace.name} at {done}/{total}")
    return True


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
                    "status": "interrupted",
                    "message": "B-roll pipeline interrupted — will resume automatically.",
                    "error": "Server restarted or job stalled during b-roll pipeline.",
                    "stage": "interrupted",
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
    """True when export needs a stock/API clip for this segment.

    Full-frame Remotion (TitleCard / layout=full) is rendered at export time and
    should not block Ready for export. Overlay / split Remotion still need b-roll.
    """
    if segment.get("render_mode") != "remotion":
        return True
    remotion = segment.get("remotion") or {}
    layout = str(remotion.get("layout") or "").strip().lower()
    if layout in {"split-right", "overlay"}:
        return True
    if layout == "full":
        return False
    # Match frontend remotionLayout() defaults when layout is omitted.
    composition = str(remotion.get("composition") or "").strip()
    if composition == "FactCard":
        return True
    if composition == "TitleCard":
        return False
    # Remotion without layout/composition defaults to full-frame.
    return False


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


def broll_rows_for_duplicates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only count duplicates among segments that actually need b-roll clips."""
    return [row for row in rows if segment_needs_broll(row)]


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

    duplicates = find_duplicate_clips(broll_rows_for_duplicates(rows))
    ids: set[int] = set()
    for group in duplicates:
        for segment_id in group.get("segment_ids") or []:
            try:
                ids.add(int(segment_id))
            except (TypeError, ValueError):
                continue
    return sorted(ids)


def as_completed_wait(
    pending: set[Any], *, timeout: float
) -> tuple[set[Any], set[Any]]:
    """Wait up to timeout for at least one future; return (done, still_pending)."""
    if not pending:
        return set(), set()
    done, not_done = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
    return done, not_done


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
    automation_goal: str = "none",
    automation_enabled_flag: bool = True,
    queued_for_export: bool = False,
) -> str:
    export_status = str(export_job.get("status") or "idle")
    if export_status == "done":
        return "complete"
    if queued_for_export and export_status != "running":
        return "queued_for_export"
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

    goal = (automation_goal or "none").strip().lower()
    if goal != "none" and not automation_enabled_flag:
        return "automation_paused"

    export_ready = manual_refetch_done or goal == "auto_export"

    if broll_total <= 0:
        return "ready_for_export" if export_ready else "ready_for_refetch"

    if broll_fetched < broll_total:
        return "fetching_broll" if pipeline_status == "running" else "ready_for_broll"

    if duplicates_remaining > 0:
        return "clearing_duplicates" if pipeline_status == "running" else "ready_for_broll"

    if export_ready:
        return "ready_for_export"
    return "ready_for_refetch"


def start_broll_pipeline(workspace: Path) -> dict[str, Any]:
    paths = workspace_paths(workspace)
    if not paths["script"].exists() or not paths["timestamps"].exists():
        raise RuntimeError("Script and timestamps are required before b-roll pipeline.")

    # If a "running" job hasn't moved progress in PROGRESS_STALL_SECONDS, treat
    # it as hung and reclaim the slot so we can restart from the current
    # fetched count instead of waiting forever on a dead worker.
    interrupt_stalled_pipeline(workspace)

    key = _workspace_key(workspace)
    # Claim "running" atomically under the lock so a direct call (e.g. right
    # after Whisper finishes) and a concurrent watchdog scan can never both
    # pass the check and launch duplicate pipeline runs for the same project.
    with _pipeline_lock:
        state = _get_state_unlocked(workspace)
        if state.get("status") == "running":
            return dict(state)
        state["status"] = "running"
        run_id = int(_pipeline_run_ids.get(key, 0)) + 1
        _pipeline_run_ids[key] = run_id

    _set_pipeline_state(
        workspace,
        status="running",
        stage="fetch_broll",
        message="Starting b-roll fetch…",
        error=None,
        started_at=time.time(),
        progress_changed_at=time.time(),
        progress_percent=0,
        done=0,
        total=0,
        cleared=0,
        clear_total=0,
    )

    def still_current() -> bool:
        with _pipeline_lock:
            return _pipeline_run_ids.get(key) == run_id

    def worker() -> None:
        try:
            from broll_judge import JudgmentCache
            from broll_viewer import build_segment_rows, fetch_segment_video
            from fetch_retry import run_with_retry
            from user_sessions import read_manifest, touch_manifest

            cache_dir = paths["cache"]
            flagged_path = paths["flagged"]
            judgment_cache = JudgmentCache(cache_dir)
            manifest = read_manifest(workspace)
            automation_goal = str(manifest.get("automation_goal") or "none").strip().lower()

            def load_rows() -> list[dict[str, Any]]:
                return _timed_rows(
                    build_segment_rows(
                        paths["script"],
                        paths["timestamps"],
                        paths["selections"],
                    )
                )

            def fetch_row(row: dict[str, Any], *, refetch: bool) -> None:
                if not still_current():
                    raise RuntimeError("Pipeline superseded by a newer run.")
                segment_id = int(row["segment_id"])

                def do_fetch() -> None:
                    if not still_current():
                        raise RuntimeError("Pipeline superseded by a newer run.")
                    fetch_segment_video(
                        paths["selections"],
                        paths["script"],
                        segment_id,
                        str(row.get("search_query") or row.get("description") or ""),
                        refetch=refetch,
                        provider_override="mix",
                        segment=row,
                        cache_dir=cache_dir,
                        judgment_cache=judgment_cache,
                        flagged_path=flagged_path,
                    )

                run_with_retry(do_fetch, label=f"segment-{segment_id}")

            if not still_current():
                return

            rows = load_rows()
            missing = [
                row
                for row in rows
                if segment_needs_broll(row) and not segment_has_broll_coverage(row)
            ]
            needed_total = sum(1 for row in rows if segment_needs_broll(row))
            fetched_ok = needed_total - len(missing)
            failed_ids: list[int] = []

            _set_pipeline_state(
                workspace,
                stage="fetch_broll",
                message=f"Fetching b-roll ({fetched_ok}/{needed_total})…",
                done=fetched_ok,
                total=needed_total,
                failed_segment_ids=[],
                progress_percent=int((fetched_ok / needed_total) * 70) if needed_total else 70,
            )

            def fetch_batch(batch: list[dict[str, Any]]) -> list[int]:
                still_failed: list[int] = []
                if not batch:
                    return still_failed
                # Don't use `with ThreadPoolExecutor` — its shutdown(wait=True) would
                # block forever on a hung HTTP fetch and prevent the stall watchdog
                # from launching a replacement worker. shutdown(wait=False) lets us
                # abandon hung futures after still_current() flips.
                pool = ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY)
                try:
                    futures = {pool.submit(fetch_row, row, refetch=False): row for row in batch}
                    pending = set(futures.keys())
                    while pending:
                        if not still_current():
                            for future in pending:
                                future.cancel()
                            return still_failed
                        done_set, pending = as_completed_wait(pending, timeout=5.0)
                        for future in done_set:
                            row = futures[future]
                            segment_id = int(row["segment_id"])
                            try:
                                future.result()
                                fetched_ok_nonlocal[0] += 1
                            except Exception as exc:
                                print(f"[pipeline] fetch failed segment {segment_id}: {exc}")
                                still_failed.append(segment_id)
                            if still_current():
                                _set_pipeline_state(
                                    workspace,
                                    stage="fetch_broll",
                                    message=f"Fetching b-roll ({fetched_ok_nonlocal[0]}/{needed_total})…",
                                    done=fetched_ok_nonlocal[0],
                                    total=needed_total,
                                    failed_segment_ids=sorted(set(still_failed + failed_ids)),
                                    progress_percent=int(
                                        (fetched_ok_nonlocal[0] / max(needed_total, 1)) * 70
                                    ),
                                )
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)
                return still_failed

            fetched_ok_nonlocal = [fetched_ok]
            failed_ids = fetch_batch(missing)
            if not still_current():
                return
            retry_round = 0
            while failed_ids and retry_round < 5:
                if not still_current():
                    return
                retry_round += 1
                rows_by_id = {int(row["segment_id"]): row for row in load_rows()}
                retry_rows = [
                    rows_by_id[segment_id]
                    for segment_id in failed_ids
                    if segment_id in rows_by_id
                ]
                failed_ids = fetch_batch(retry_rows)
                if failed_ids:
                    time.sleep(3.0)
            if not still_current():
                return
            fetched_ok = fetched_ok_nonlocal[0]

            rows = load_rows()
            fetched, total = compute_broll_counts(rows)
            if total > 0 and fetched < total:
                _set_pipeline_state(
                    workspace,
                    status="interrupted",
                    stage="fetch_broll",
                    message=f"B-roll incomplete ({fetched}/{total}) — will retry.",
                    error=f"Only fetched {fetched} of {total} required segments.",
                    done=fetched,
                    total=total,
                    failed_segment_ids=sorted(set(failed_ids)),
                    progress_percent=70,
                )
                return

            initial_ids = _duplicate_segment_ids(rows)
            if not initial_ids:
                if automation_goal == "auto_export":
                    touch_manifest(workspace, manual_refetch_done=True)
                _set_pipeline_state(
                    workspace,
                    status="done",
                    stage="done",
                    message=(
                        "B-roll ready — auto-export queued."
                        if automation_goal == "auto_export"
                        else "B-roll ready — review and refetch at least one clip before export."
                    ),
                    error=None,
                    done=fetched,
                    total=total,
                    cleared=0,
                    clear_total=0,
                    progress_percent=100,
                )
                if automation_goal == "auto_export":
                    _nudge_export_queue(workspace)
                return

            clear_total = len(initial_ids)
            cleared_ids: set[int] = set()
            _set_pipeline_state(
                workspace,
                stage="clear_duplicates",
                message=f"Clearing duplicates (0/{clear_total})…",
                done=fetched,
                total=total,
                cleared=0,
                clear_total=clear_total,
                progress_percent=75,
            )

            cleared_cleanly = False
            for _pass_index in range(MAX_DUPLICATE_PASSES):
                if not still_current():
                    return
                rows = load_rows()
                affected = _duplicate_segment_ids(rows)
                if not affected:
                    cleared_cleanly = True
                    break
                for segment_id in affected:
                    if not still_current():
                        return
                    row = next((r for r in rows if int(r["segment_id"]) == segment_id), None)
                    if row is None or not segment_needs_broll(row):
                        continue
                    try:
                        fetch_row(row, refetch=True)
                    except Exception as exc:
                        print(f"[pipeline] duplicate refetch failed segment {segment_id}: {exc}")
                    cleared_ids.add(segment_id)
                    if still_current():
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

            if not still_current():
                return

            rows = load_rows()
            remaining_dupes = len(_duplicate_segment_ids(rows))
            if not cleared_cleanly and remaining_dupes > 0:
                if automation_goal == "auto_export":
                    _set_pipeline_state(
                        workspace,
                        status="warning",
                        stage="clear_duplicates",
                        message=f"Duplicates remain ({remaining_dupes}) — orchestrator will retry.",
                        error=f"{remaining_dupes} duplicate-affected segment(s) remain.",
                        cleared=len(cleared_ids),
                        clear_total=max(clear_total, len(cleared_ids)),
                        progress_percent=99,
                    )
                    return
                _set_pipeline_state(
                    workspace,
                    status="error",
                    stage="error",
                    message=f"Could not clear all duplicates ({remaining_dupes} left).",
                    error=(
                        f"Still {remaining_dupes} duplicate-affected segment(s) after "
                        f"{MAX_DUPLICATE_PASSES} passes."
                    ),
                    cleared=len(cleared_ids),
                    clear_total=max(clear_total, len(cleared_ids)),
                    progress_percent=99,
                )
                return

            fetched, total = compute_broll_counts(rows)
            if automation_goal == "auto_export":
                touch_manifest(workspace, manual_refetch_done=True)
            _set_pipeline_state(
                workspace,
                status="done",
                stage="done",
                message=(
                    "B-roll ready — auto-export queued."
                    if automation_goal == "auto_export"
                    else "B-roll ready — review and refetch at least one clip before export."
                ),
                error=None,
                done=fetched,
                total=total,
                cleared=len(cleared_ids),
                clear_total=max(clear_total, len(cleared_ids)),
                progress_percent=100,
            )
            if automation_goal == "auto_export":
                _nudge_export_queue(workspace)
        except BaseException as exc:
            if not still_current():
                return
            if "superseded" in str(exc).lower():
                return
            _set_pipeline_state(
                workspace,
                status="interrupted",
                stage="error",
                message="B-roll pipeline failed — will retry.",
                error=str(exc) or "Pipeline failed.",
                progress_percent=0,
            )

    threading.Thread(target=worker, daemon=True).start()
    return pipeline_job_snapshot(workspace)
