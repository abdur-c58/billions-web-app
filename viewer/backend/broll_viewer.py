#!/usr/bin/env python3
"""Local server for the Billions b-roll viewer."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import random
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from export_video import (
    EXPORT_API_VERSION,
    ExportCancelled,
    apply_mix_adjustments,
    build_mixed_audio,
    clamp_mix_adjust_db,
    compute_mix_gains,
    compute_solo_narration_gains,
    export_video,
    probe_duration,
    render_narration_audio,
    request_export_cancel,
    sanitize_output_name,
    summarize_export_error,
)
from flagged_clips import (
    clip_key,
    filter_flagged_videos,
    find_duplicate_clips,
    find_segments_with_clip,
    flag_clip,
    is_clip_flagged,
    list_flagged_clips,
    unflag_clip,
)
from broll_judge import (
    AiBudget,
    JudgmentCache,
    enrich_selection_judgment,
    pick_best_candidate,
    summarize_judgments,
)
from project_manager import (
    load_all_timestamps_job_states,
    load_timestamps_job_state,
    parse_multipart_form,
    project_status,
    save_audio,
    save_script,
    save_timestamps,
    start_segment_timestamps,
    timestamps_job_snapshot,
    workspace_paths,
)
from storage_r2 import (
    list_r2_background_audio,
    resolve_r2_background_audio,
    validate_audio_storage_key,
)
from user_sessions import (
    create_project,
    list_projects,
    migrate_legacy_workspace,
    migrate_user_scoped_projects,
    project_workspace,
)

ROOT = Path(__file__).resolve().parent
WORKSPACE_DIR = ROOT / "workspace"
VIDEO_DIR = ROOT / "video"
DEFAULT_SCRIPT = VIDEO_DIR / "script.json"
DEFAULT_TIMESTAMPS = VIDEO_DIR / "segment_timestamps.json"
DEFAULT_SELECTIONS = VIDEO_DIR / "broll_selections.json"
DEFAULT_AUDIO = VIDEO_DIR / "script.mp3"
DEFAULT_OUTPUT = VIDEO_DIR / "final_video.mp4"
HTML_FILE = ROOT / "broll_viewer.html"
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/videos/search"
PIXABAY_VIDEO_SEARCH_URL = "https://pixabay.com/api/videos/"

export_lock = threading.Lock()
export_cancel_event = threading.Event()
PEXELS_MAX_RETRIES = 24
MIN_PEXELS_INTERVAL_S = 0.45


class PexelsKeyPool:
    _ENV_KEY_NAMES = ("PEXELS_API_KEY", "PEXELS_API_KEY_2", "PEXELS_API_KEY_3")

    def __init__(self, keys: list[str], min_interval_s: float = MIN_PEXELS_INTERVAL_S):
        if not keys:
            raise RuntimeError("PEXELS_API_KEY is missing. Add it to .env")
        self._keys = keys
        self._min_interval = min_interval_s
        self._last_call = [0.0] * len(keys)
        self._locks = [threading.Lock() for _ in keys]
        self._round_robin = 0
        self._rr_lock = threading.Lock()

    @property
    def size(self) -> int:
        return len(self._keys)

    @classmethod
    def from_env(cls) -> PexelsKeyPool:
        keys: list[str] = []
        for name in cls._ENV_KEY_NAMES:
            value = os.environ.get(name, "").strip()
            if value and value not in keys:
                keys.append(value)
        return cls(keys)

    def _next_slot(self) -> int:
        with self._rr_lock:
            slot = self._round_robin % len(self._keys)
            self._round_robin += 1
            return slot

    def search(self, query: str, page: int = 1, per_page: int = 15) -> dict[str, Any]:
        last_error: Exception | None = None
        max_attempts = len(self._keys) * PEXELS_MAX_RETRIES

        for attempt in range(max_attempts):
            slot = self._next_slot()
            api_key = self._keys[slot]
            try:
                with self._locks[slot]:
                    wait = self._min_interval - (time.time() - self._last_call[slot])
                    if wait > 0:
                        time.sleep(wait)
                    result = _pexels_search_once(query, page, per_page, api_key)
                    self._last_call[slot] = time.time()
                    return result
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"Pexels API error {exc.code}: {body}")
                retryable = exc.code in {429, 500, 502, 503, 504} or (
                    exc.code == 400 and "rate" in body.lower()
                )
                if exc.code == 429:
                    print(
                        f"Pexels key {slot + 1}/{len(self._keys)} rate limited "
                        f"for '{query}' — rotating to next key"
                    )
                    continue
                if retryable and attempt < max_attempts - 1:
                    backoff = min(45.0, 2.0 * (2 ** (attempt // max(1, len(self._keys)))))
                    print(
                        f"Pexels retry {attempt + 1}/{max_attempts} "
                        f"for '{query}' after HTTP {exc.code} (sleep {backoff:.1f}s)"
                    )
                    time.sleep(backoff)
                    continue
                raise last_error from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = RuntimeError(f"Pexels request failed: {exc}")
                if attempt < max_attempts - 1:
                    backoff = min(20.0, 1.5 * ((attempt % len(self._keys)) + 1))
                    print(
                        f"Pexels retry {attempt + 1}/{max_attempts} "
                        f"for '{query}' after network error (sleep {backoff:.1f}s)"
                    )
                    time.sleep(backoff)
                    continue
                raise last_error from exc

        if last_error:
            raise last_error
        raise RuntimeError(f"Pexels search failed for '{query}'")


pexels_pool: PexelsKeyPool | None = None


def get_pexels_pool() -> PexelsKeyPool:
    global pexels_pool
    if pexels_pool is None:
        pexels_pool = PexelsKeyPool.from_env()
    return pexels_pool


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
    }


export_state: dict[str, Any] = default_export_state()


def compute_progress_percent(
    stage: str,
    current: int,
    total: int,
    status: str,
) -> int:
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

    return enriched


def load_persisted_export_state(export_status_file: Path) -> None:
    global export_state
    saved = read_json(export_status_file, {})
    if not saved:
        export_state = default_export_state()
        return

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

    export_state = {**default_export_state(), **saved}


def save_export_state(export_status_file: Path) -> None:
    export_status_file.parent.mkdir(parents=True, exist_ok=True)
    write_json(export_status_file, export_state)


def _apply_env_file(path: Path, *, override: bool = False) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if override:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def load_env_file(env_path: Path | None = None) -> None:
    server_root = ROOT.parent.parent
    candidates: list[tuple[Path, bool]] = []

    if env_path:
        candidates.append((env_path, True))

    candidates.extend(
        [
            (ROOT / ".env", False),
            (server_root / ".env", False),
            (server_root / ".env.local", True),
        ]
    )

    for path, override in candidates:
        if path.exists():
            _apply_env_file(path, override=override)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as infile:
        return json.load(infile)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def iter_script_segments(script_data: dict[str, Any]) -> list[dict[str, Any]]:
    from script_format import iter_broll_script_segments

    return iter_broll_script_segments(script_data)


def selection_matches_segment(
    selection: dict[str, Any] | None,
    segment: dict[str, Any],
    script_path: Path,
    selections_data: dict[str, Any],
) -> bool:
    if not selection:
        return False

    saved_script = selections_data.get("source_script")
    if saved_script and saved_script != str(script_path.resolve()):
        return False

    saved_query = selection.get("search_query")
    if saved_query and saved_query != segment["search_query"]:
        return False

    return True


def build_segment_rows(
    script_path: Path,
    timestamps_path: Path,
    selections_path: Path,
) -> list[dict[str, Any]]:
    script_data = read_json(script_path, {})
    timestamps_data = read_json(timestamps_path, {})
    selections_data = read_json(selections_path, {"segments": {}})

    timing_by_id = {
        entry["segment_id"]: entry
        for entry in timestamps_data.get("segments", [])
        if entry.get("segment_id") is not None
    }

    rows: list[dict[str, Any]] = []
    for segment in iter_script_segments(script_data):
        segment_id = segment["segment_id"]
        timing_entry = timing_by_id.get(segment_id, {})
        timing = timing_entry.get("timing", {})
        selection_key = str(segment_id)
        selection = selections_data.get("segments", {}).get(selection_key)
        if not selection_matches_segment(selection, segment, script_path, selections_data):
            selection = None

        rows.append(
            {
                **segment,
                "timing": timing,
                "selection": enrich_selection_judgment(selection),
            }
        )

    enrich_export_timing(rows)
    enrich_selection_flags(rows, selections_path.parent / ".broll_flagged.json")
    return rows


def enrich_selection_flags(rows: list[dict[str, Any]], flagged_path: Path) -> None:
    for row in rows:
        selection = row.get("selection")
        row["selection_flagged"] = bool(selection and is_clip_flagged(selection, flagged_path))


def enrich_export_timing(rows: list[dict[str, Any]]) -> None:
    cursor = 0.0
    for row in sorted(rows, key=lambda item: item["segment_id"]):
        timing = row.get("timing") or {}
        duration = timing.get("duration_seconds")
        if duration is None or float(duration) <= 0:
            timing["export_start_seconds"] = None
            timing["export_end_seconds"] = None
            row["timing"] = timing
            continue

        export_start = cursor
        export_end = cursor + float(duration)
        timing["export_start_seconds"] = round(export_start, 3)
        timing["export_end_seconds"] = round(export_end, 3)
        row["timing"] = timing
        cursor = export_end


def pick_video_file(video_files: list[dict[str, Any]]) -> dict[str, Any] | None:
    mp4_files = [item for item in video_files if item.get("file_type") == "video/mp4"]
    if not mp4_files:
        return None
    mp4_files.sort(key=lambda item: item.get("width", 0), reverse=True)
    for target_width in (1920, 1280, 854, 640):
        for item in mp4_files:
            if item.get("width") == target_width:
                return item
    return mp4_files[0]


def normalize_pexels_video(video: dict[str, Any]) -> dict[str, Any] | None:
    video_file = pick_video_file(video.get("video_files", []))
    if not video_file:
        return None

    pictures = video.get("video_pictures") or []
    thumbnail = pictures[0]["picture"] if pictures else None

    return {
        "video_id": video.get("id"),
        "provider": "pexels",
        "url": video_file.get("link"),
        "width": video_file.get("width"),
        "height": video_file.get("height"),
        "duration": video.get("duration"),
        "thumbnail": thumbnail,
        "photographer": (video.get("user") or {}).get("name"),
        "pexels_url": video.get("url"),
    }


def normalize_pixabay_video(video: dict[str, Any]) -> dict[str, Any] | None:
    variants = video.get("videos") or {}
    choice = None
    for key in ("large", "medium", "small", "tiny"):
        item = variants.get(key)
        if item and item.get("url"):
            choice = item
            break
    if not choice:
        return None

    return {
        "video_id": video.get("id"),
        "provider": "pixabay",
        "url": choice.get("url"),
        "width": choice.get("width"),
        "height": choice.get("height"),
        "duration": video.get("duration"),
        "thumbnail": choice.get("thumbnail"),
        "photographer": video.get("user"),
        "pixabay_url": f"https://pixabay.com/videos/id-{video.get('id')}/",
        "tags": video.get("tags"),
    }


def simplify_search_query(query: str) -> str:
    words = [word for word in query.split() if word]
    if len(words) <= 2:
        return query
    return " ".join(words[:2])


def _pexels_search_once(
    query: str,
    page: int,
    per_page: int,
    api_key: str,
) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "page": page,
            "per_page": per_page,
            "orientation": "landscape",
        }
    )
    request = urllib.request.Request(
        f"{PEXELS_SEARCH_URL}?{params}",
        headers={
            "Authorization": api_key,
            "User-Agent": "Billions-BrollViewer/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)

    videos = []
    for video in payload.get("videos", []):
        normalized = normalize_pexels_video(video)
        if normalized:
            videos.append(normalized)

    return {
        "videos": videos,
        "page": payload.get("page", page),
        "per_page": payload.get("per_page", per_page),
        "total_results": payload.get("total_results", len(videos)),
        "next_page": payload.get("next_page"),
        "query_used": query,
    }


def pexels_search(query: str, page: int = 1, per_page: int = 15) -> dict[str, Any]:
    return get_pexels_pool().search(query, page, per_page)


def pixabay_search(query: str, page: int = 1, per_page: int = 15) -> dict[str, Any]:
    api_key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PIXABAY_API_KEY is missing. Add it to .env")

    params = urllib.parse.urlencode(
        {
            "key": api_key,
            "q": query,
            "page": page,
            "per_page": per_page,
            "video_type": "all",
            "orientation": "horizontal",
            "safesearch": "true",
        }
    )
    request = urllib.request.Request(
        f"{PIXABAY_VIDEO_SEARCH_URL}?{params}",
        headers={"User-Agent": "Billions-BrollViewer/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)

    videos: list[dict[str, Any]] = []
    for video in payload.get("hits", []):
        normalized = normalize_pixabay_video(video)
        if normalized:
            videos.append(normalized)

    total_hits = int(payload.get("totalHits") or len(videos))
    has_next_page = page * per_page < total_hits
    return {
        "videos": videos,
        "page": page,
        "per_page": per_page,
        "total_results": int(payload.get("total") or total_hits),
        "next_page": page + 1 if has_next_page else None,
        "query_used": query,
    }


def mixed_search(query: str, page: int = 1, per_page: int = 15) -> dict[str, Any]:
    pexels_result = pexels_search(query, page=page, per_page=per_page)
    pixabay_result: dict[str, Any] = {"videos": []}
    try:
        pixabay_result = pixabay_search(query, page=page, per_page=per_page)
    except Exception as exc:
        print(f"Pixabay fallback skipped for '{query}': {exc}")

    merged: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    pexels_videos = pexels_result.get("videos", [])
    pixabay_videos = pixabay_result.get("videos", [])
    max_len = max(len(pexels_videos), len(pixabay_videos))
    for index in range(max_len):
        for pool in (pexels_videos, pixabay_videos):
            if index >= len(pool):
                continue
            item = pool[index]
            url = str(item.get("url") or "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            merged.append(item)

    next_page = pexels_result.get("next_page") or pixabay_result.get("next_page")
    return {
        "videos": merged,
        "page": page,
        "per_page": per_page,
        "total_results": int(pexels_result.get("total_results") or 0)
        + int(pixabay_result.get("total_results") or 0),
        "next_page": next_page,
        "query_used": query,
    }



ROOT_STORAGE_FOLDERS = ("Audio", "B-Roll", "Other")
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


def storage_video_id(storage_key: str) -> str:
    digest = hashlib.sha1(storage_key.encode("utf-8")).hexdigest()[:12]
    return f"storage_{digest}"


def validate_storage_video_key(storage_key: str) -> None:
    key = storage_key.strip()
    if not key or key.endswith("/"):
        raise ValueError("Invalid storage file key.")
    root = key.split("/")[0]
    if root not in ROOT_STORAGE_FOLDERS:
        raise ValueError("Storage clips must live under Audio, B-Roll, or Other.")
    name = key.split("/")[-1]
    ext = f".{name.split('.')[-1].lower()}" if "." in name else ""
    if ext not in VIDEO_EXTENSIONS:
        raise ValueError("Storage b-roll must be a video file.")


def build_storage_selection(
    storage_key: str,
    *,
    duration: float | None = None,
    loop: bool = False,
) -> dict[str, Any]:
    validate_storage_video_key(storage_key)
    file_name = storage_key.split("/")[-1]
    media_url = f"/api/storage/media?key={urllib.parse.quote(storage_key, safe='')}"
    selection: dict[str, Any] = {
        "provider": "storage",
        "video_id": storage_video_id(storage_key),
        "storage_key": storage_key,
        "url": media_url,
        "thumbnail": "",
        "name": file_name,
        "loop": bool(loop),
    }
    if duration is not None and duration > 0:
        selection["duration"] = round(float(duration), 3)
    return selection


def get_selection_state(selections_path: Path) -> dict[str, Any]:
    data = read_json(selections_path, {"segments": {}})
    if "segments" not in data:
        data["segments"] = {}
    return data


def save_segment_selection(
    selections_path: Path,
    script_path: Path,
    segment_id: int,
    search_query: str,
    video: dict[str, Any],
    page: int,
    result_index: int,
    *,
    query_used: str | None = None,
    custom_query: str | None = None,
    fetch_provider: str | None = None,
    judgment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = get_selection_state(selections_path)
    data["source_script"] = str(script_path.resolve())
    key = str(segment_id)
    entry: dict[str, Any] = {
        **video,
        "search_query": search_query,
        "page": page,
        "result_index": result_index,
    }
    if query_used:
        entry["query_used"] = query_used
    if custom_query:
        entry["custom_query"] = custom_query
    if fetch_provider:
        entry["fetch_provider"] = fetch_provider
    if judgment:
        for field in (
            "confidence",
            "confidence_source",
            "needs_review",
            "ai_model",
            "ai_reason",
            "ai_skipped",
            "subject_match",
            "tone_match",
        ):
            if field in judgment:
                entry[field] = judgment[field]
    enriched = enrich_selection_judgment(entry)
    if enriched:
        entry["quality_tier"] = enriched["quality_tier"]
        entry["quality_label"] = enriched["quality_label"]
    data["segments"][key] = entry
    write_json(selections_path, data)
    try:
        from project_r2 import sync_project_path
        from project_manager import SELECTIONS_NAME

        sync_project_path(selections_path, SELECTIONS_NAME)
    except Exception:
        pass
    return data["segments"][key]


def fetch_segment_video(
    selections_path: Path,
    script_path: Path,
    segment_id: int,
    search_query: str,
    refetch: bool,
    page_override: int | None = None,
    index_override: int | None = None,
    query_override: str | None = None,
    provider_override: str | None = None,
    *,
    segment: dict[str, Any] | None = None,
    cache_dir: Path | None = None,
    use_ai: bool = True,
    ai_budget: AiBudget | None = None,
    judgment_cache: JudgmentCache | None = None,
    flagged_path: Path | None = None,
) -> dict[str, Any]:
    script_query = search_query.strip()
    active_query = (
        query_override.strip()
        if query_override and query_override.strip()
        else script_query
    )
    is_custom = active_query != script_query
    fetch_provider_mode = (provider_override or "mix").strip().lower()
    if fetch_provider_mode not in {"pexels", "pixabay", "mix", "random"}:
        fetch_provider_mode = "mix"

    search_provider_mode = fetch_provider_mode

    data = get_selection_state(selections_path)
    key = str(segment_id)
    current = data["segments"].get(key, {})
    used_clip_keys_elsewhere: set[str] = set()
    if refetch:
        for existing_segment_id, existing_selection in data.get("segments", {}).items():
            if str(existing_segment_id) == key:
                continue
            existing_key = clip_key(existing_selection)
            if existing_key:
                used_clip_keys_elsewhere.add(existing_key)
    prev_query_used = (current.get("query_used") or script_query).strip()
    prev_fetch_provider = str(current.get("fetch_provider") or "mix").strip().lower()
    same_query = (
        prev_query_used == active_query and prev_fetch_provider == fetch_provider_mode
    )

    if page_override is not None:
        page = page_override
    elif same_query:
        page = int(current.get("page", 1))
    else:
        page = 1

    if index_override is not None:
        result_index = index_override
    elif same_query:
        result_index = int(current.get("result_index", 0))
    else:
        result_index = 0

    if refetch and index_override is None and same_query:
        result_index += 1

    if (
        not refetch
        and current.get("url")
        and current.get("search_query") == script_query
        and prev_query_used == active_query
        and page_override is None
        and index_override is None
    ):
        return {
            "segment_id": segment_id,
            "search_query": script_query,
            "query_used": prev_query_used,
            "selection": current,
            "page": int(current.get("page", 1)),
            "result_index": int(current.get("result_index", 0)),
            "alternatives": [],
            "cached": True,
        }

    if is_custom:
        queries_to_try = [active_query]
    else:
        queries_to_try = [script_query]
        fallback = simplify_search_query(script_query)
        if fallback != script_query:
            queries_to_try.append(fallback)

    search: dict[str, Any] | None = None
    videos: list[dict[str, Any]] = []
    query_used = active_query

    for candidate_query in queries_to_try:
        page_for_query = page
        search = None
        videos = []
        pages_checked = 0
        while pages_checked < 10:
            if search_provider_mode == "pexels":
                search = pexels_search(candidate_query, page=page_for_query, per_page=15)
            elif search_provider_mode == "pixabay":
                search = pixabay_search(candidate_query, page=page_for_query, per_page=15)
            else:
                search = mixed_search(candidate_query, page=page_for_query, per_page=15)
            raw_videos = search.get("videos", [])
            videos = (
                filter_flagged_videos(raw_videos, flagged_path)
                if flagged_path
                else raw_videos
            )
            if refetch and used_clip_keys_elsewhere:
                videos = [
                    video
                    for video in videos
                    if clip_key(video) not in used_clip_keys_elsewhere
                ]
            query_used = candidate_query
            pages_checked += 1
            if videos:
                page = page_for_query
                break
            if not search.get("next_page"):
                break
            page_for_query += 1
            result_index = 0

        if videos:
            break

    if not videos:
        raise RuntimeError(
            f"No unflagged non-duplicate videos found for '{active_query}' with provider {fetch_provider_mode}"
        )

    while result_index >= len(videos):
        if not search or not search.get("next_page"):
            result_index = 0
            page = 1
            if search_provider_mode == "pexels":
                search = pexels_search(query_used, page=page, per_page=15)
            elif search_provider_mode == "pixabay":
                search = pixabay_search(query_used, page=page, per_page=15)
            else:
                search = mixed_search(query_used, page=page, per_page=15)
            raw_videos = search.get("videos", [])
            videos = (
                filter_flagged_videos(raw_videos, flagged_path)
                if flagged_path
                else raw_videos
            )
            if refetch and used_clip_keys_elsewhere:
                videos = [
                    video
                    for video in videos
                    if clip_key(video) not in used_clip_keys_elsewhere
                ]
            if not videos:
                raise RuntimeError(
                    f"No unflagged non-duplicate videos found for '{active_query}' with provider {fetch_provider_mode}"
                )
            break
        page += 1
        result_index = 0
        if search_provider_mode == "pexels":
            search = pexels_search(query_used, page=page, per_page=15)
        elif search_provider_mode == "pixabay":
            search = pixabay_search(query_used, page=page, per_page=15)
        else:
            search = mixed_search(query_used, page=page, per_page=15)
        raw_videos = search.get("videos", [])
        videos = (
            filter_flagged_videos(raw_videos, flagged_path)
            if flagged_path
            else raw_videos
        )
        if refetch and used_clip_keys_elsewhere:
            videos = [
                video for video in videos if clip_key(video) not in used_clip_keys_elsewhere
            ]
        if not videos and not search.get("next_page"):
            raise RuntimeError(
                f"No unflagged non-duplicate videos found for '{active_query}' with provider {fetch_provider_mode}"
            )

    if result_index >= len(videos):
        result_index = 0

    if fetch_provider_mode == "random" and videos:
        choices = list(range(len(videos)))
        current_key = clip_key(current)
        if current_key:
            filtered_choices = [
                i for i, item in enumerate(videos) if clip_key(item) != current_key
            ]
            choices = filtered_choices or choices
        result_index = random.choice(choices)

    judgment: dict[str, Any] | None = None
    auto_pick = (
        not refetch
        and index_override is None
        and segment is not None
        and cache_dir is not None
    )
    if auto_pick:
        judgment = pick_best_candidate(
            segment,
            videos,
            query_used,
            segment_id=segment_id,
            cache_dir=cache_dir,
            use_ai=use_ai,
            budget=ai_budget,
            judgment_cache=judgment_cache,
        )
        result_index = int(judgment.get("best_index", result_index))

    video = videos[result_index]
    saved = save_segment_selection(
        selections_path,
        script_path,
        segment_id,
        script_query,
        video,
        page,
        result_index,
        query_used=query_used,
        custom_query=active_query if is_custom else None,
        fetch_provider=fetch_provider_mode,
        judgment=judgment,
    )

    return {
        "segment_id": segment_id,
        "search_query": script_query,
        "query_used": query_used,
        "provider_mode": fetch_provider_mode,
        "selection": saved,
        "page": page,
        "result_index": result_index,
        "alternatives": videos,
        "judgment": judgment,
    }


def rescore_unscored_segments(
    selections_path: Path,
    script_path: Path,
    timestamps_path: Path,
    *,
    cache_dir: Path | None,
    use_ai: bool,
    ai_budget: AiBudget | None,
    judgment_cache: JudgmentCache | None,
) -> dict[str, Any]:
    rows = build_segment_rows(script_path, timestamps_path, selections_path)
    state = get_selection_state(selections_path)
    updated_ids: list[int] = []

    for row in rows:
        segment_id = int(row["segment_id"])
        key = str(segment_id)
        current = state.get("segments", {}).get(key)
        if not current or not current.get("url"):
            continue
        if current.get("confidence_source"):
            continue

        judgment = pick_best_candidate(
            row,
            [current],
            str(current.get("query_used") or row.get("search_query") or ""),
            segment_id=segment_id,
            cache_dir=cache_dir or script_path.parent / ".broll_cache",
            use_ai=use_ai,
            budget=ai_budget,
            judgment_cache=judgment_cache,
        )

        save_segment_selection(
            selections_path,
            script_path,
            segment_id,
            row.get("search_query", ""),
            current,
            int(current.get("page") or 1),
            int(current.get("result_index") or 0),
            query_used=str(current.get("query_used") or row.get("search_query") or ""),
            custom_query=current.get("custom_query"),
            judgment=judgment,
        )
        updated_ids.append(segment_id)

    return {
        "updated": len(updated_ids),
        "segment_ids": updated_ids,
    }


def parse_mix_adjustments(body: dict[str, Any]) -> tuple[float, float]:
    narration_adjust_db = clamp_mix_adjust_db(float(body.get("narration_adjust_db") or 0))
    background_adjust_db = clamp_mix_adjust_db(float(body.get("background_adjust_db") or 0))
    return narration_adjust_db, background_adjust_db


def preview_cache_name(
    background_audio_key: str | None,
    preview_seconds: float,
    narration_adjust_db: float,
    background_adjust_db: float,
) -> str:
    if background_audio_key:
        safe_stem = re.sub(r"[^\w.-]+", "_", Path(background_audio_key).stem)[:48]
        narr_tag = str(narration_adjust_db).replace(".", "p").replace("-", "m")
        bg_tag = str(background_adjust_db).replace(".", "p").replace("-", "m")
        return f"preview_{safe_stem}_{int(preview_seconds)}s_n{narr_tag}_b{bg_tag}.m4a"
    narr_tag = str(narration_adjust_db).replace(".", "p").replace("-", "m")
    return f"preview_narration_{int(preview_seconds)}s_n{narr_tag}.m4a"


class BrollViewerHandler(BaseHTTPRequestHandler):
    script_path = DEFAULT_SCRIPT
    timestamps_path = DEFAULT_TIMESTAMPS
    selections_path = DEFAULT_SELECTIONS
    audio_path = DEFAULT_AUDIO
    output_path = DEFAULT_OUTPUT
    project_dir = VIDEO_DIR
    export_status_file = VIDEO_DIR / ".broll_export_status.json"
    flagged_path = VIDEO_DIR / ".broll_flagged.json"
    cache_dir = VIDEO_DIR / ".broll_cache"
    use_ai_judge = True
    ai_budget: AiBudget | None = None
    judgment_cache: JudgmentCache | None = None
    workspace_mode = False

    def _active_workspace(self) -> Path | None:
        if not self.workspace_mode:
            return self.project_dir
        project = self.headers.get("X-Billions-Project", "").strip()
        if not project:
            return None
        try:
            return project_workspace(WORKSPACE_DIR, project)
        except ValueError:
            return None

    def _require_workspace(self) -> Path:
        workspace = self._active_workspace()
        if workspace is None:
            raise ValueError("Select a project first.")
        return workspace

    def _project_ready(self) -> bool:
        return (
            self.script_path.exists()
            and self.timestamps_path.exists()
            and self.audio_path.exists()
        )

    def _sync_from_workspace(self) -> None:
        if not self.workspace_mode:
            return
        workspace = self._active_workspace()
        if workspace is None:
            return
        paths = workspace_paths(workspace)
        self.script_path = paths["script"]
        self.timestamps_path = paths["timestamps"]
        self.selections_path = paths["selections"]
        self.audio_path = paths["audio"]
        self.output_path = paths["workspace"] / "final_video.mp4"
        self.project_dir = paths["workspace"]
        self.export_status_file = paths["export_status"]
        self.flagged_path = paths["flagged"]
        self.cache_dir = paths["cache"]

    def _save_export_state(self) -> None:
        save_export_state(self.export_status_file)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _allowed_cors_origin(self) -> str | None:
        origin = self.headers.get("Origin", "").strip()
        if not origin:
            return None
        allowed = os.environ.get(
            "BROLL_WEB_ORIGIN",
            "http://localhost:3001,http://127.0.0.1:3001",
        )
        allowed_origins = {item.strip() for item in allowed.split(",") if item.strip()}
        return origin if origin in allowed_origins else None

    def end_headers(self) -> None:
        origin = self._allowed_cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Billions-Project")
            self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, *, inline: bool = False) -> None:
        if not path.exists():
            self._send_json({"error": "File not found"}, HTTPStatus.NOT_FOUND)
            return
        mime, _ = mimetypes.guess_type(str(path))
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        disposition = "inline" if inline else "attachment"
        self.send_header("Content-Disposition", f'{disposition}; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def _export_snapshot(self) -> dict[str, Any]:
        with export_lock:
            return enrich_export_state(dict(export_state))

    def _set_export_state(self, **kwargs: Any) -> None:
        with export_lock:
            if kwargs.get("status") == "running" and export_state.get("status") != "running":
                kwargs.setdefault("started_at", time.time())
                kwargs.setdefault("progress_percent", 0)
                kwargs.setdefault("elapsed_seconds", 0)
                kwargs.setdefault("eta_seconds", None)
            kwargs["updated_at"] = time.time()
            export_state.update(kwargs)

            stage = str(export_state.get("stage", ""))
            current = int(export_state.get("current") or 0)
            total = int(export_state.get("total") or 0)
            status = str(export_state.get("status", "idle"))
            export_state["progress_percent"] = compute_progress_percent(
                stage, current, total, status
            )
            self._save_export_state()

    def _start_export_job(
        self,
        background_audio: str | None = None,
        *,
        narration_adjust_db: float = 0.0,
        background_adjust_db: float = 0.0,
        resolution: str = "4k",
        quality: str = "balanced",
    ) -> None:
        with export_lock:
            if export_state.get("status") == "running":
                raise RuntimeError("Export already in progress")

        export_cancel_event.clear()

        background_audio_path = None
        if background_audio:
            background_audio_path = resolve_r2_background_audio(
                background_audio,
                self.cache_dir,
            )

        title = read_json(self.timestamps_path, {}).get("title")
        output_path = self.output_path
        if title:
            output_path = output_path.parent / sanitize_output_name(title)

        self._set_export_state(
            status="running",
            stage="prepare",
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
        )

        def on_progress(stage: str, current: int, total: int, message: str) -> None:
            self._set_export_state(
                stage=stage,
                current=current,
                total=total,
                message=message,
            )

        def hardware_monitor_loop() -> None:
            from hardware_monitor import resolve_whisper_device, sample_hardware_stats

            device, device_info = resolve_whisper_device()
            while export_state.get("status") == "running":
                stats = sample_hardware_stats(device, device_info)
                self._set_export_state(hardware=stats)
                time.sleep(1.5)

        def worker() -> None:
            hw_thread = threading.Thread(target=hardware_monitor_loop, daemon=True)
            hw_thread.start()
            try:
                result = export_video(
                    audio_path=self.audio_path,
                    timestamps_path=self.timestamps_path,
                    selections_path=self.selections_path,
                    output_path=output_path,
                    on_progress=on_progress,
                    cache_dir=self.cache_dir,
                    fresh=True,
                    should_cancel=export_cancel_event.is_set,
                    background_audio_path=background_audio_path,
                    narration_adjust_db=narration_adjust_db,
                    background_adjust_db=background_adjust_db,
                    resolution=resolution,
                    quality=quality,
                )
                if export_cancel_event.is_set():
                    return
                self._set_export_state(
                    status="done",
                    stage="done",
                    current=1,
                    total=1,
                    message="Export complete",
                    output=result["output"],
                    encoder=result["encoder"],
                    error=None,
                    progress_percent=100,
                    eta_seconds=0,
                )
            except ExportCancelled:
                if not export_cancel_event.is_set():
                    self._set_export_state(
                        status="interrupted",
                        stage="cancelled",
                        message="Export cancelled",
                        error=None,
                    )
            except Exception as exc:
                if export_cancel_event.is_set():
                    return
                summary = summarize_export_error(exc)
                self._set_export_state(
                    status="error",
                    stage="error",
                    message=summary,
                    error=summary,
                )
            finally:
                export_cancel_event.clear()

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_export_job(self) -> None:
        with export_lock:
            if export_state.get("status") != "running":
                raise RuntimeError("No export in progress")

        export_cancel_event.set()
        request_export_cancel()
        self._set_export_state(
            status="interrupted",
            stage="cancelled",
            message="Export cancelled",
            error=None,
        )

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        self._sync_from_workspace()

        if parsed.path in ("/", "/index.html"):
            if HTML_FILE.exists():
                self._send_html(HTML_FILE.read_text(encoding="utf-8"))
            else:
                self._send_json({"ok": True, "message": "Use the Next.js viewer UI."})
            return

        if parsed.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        if parsed.path == "/api/project/list":
            try:
                projects = list_projects(WORKSPACE_DIR)
                running = next(
                    (p for p in projects if p.get("timestamps_job", {}).get("status") == "running"),
                    None,
                )
                self._send_json(
                    {
                        "projects": projects,
                        "has_running_job": running is not None,
                        "running_project": (
                            {"id": running["id"], "name": running["name"]}
                            if running
                            else None
                        ),
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/project/status":
            try:
                workspace = self._require_workspace() if self.workspace_mode else self.project_dir
                self._send_json(project_status(workspace))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/whisper/hardware":
            try:
                from hardware_monitor import resolve_whisper_device, sample_hardware_stats

                device, info = resolve_whisper_device()
                payload = sample_hardware_stats(device, info)
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/project/segment-timestamps/status":
            try:
                workspace = self._require_workspace() if self.workspace_mode else self.project_dir
                self._send_json(timestamps_job_snapshot(workspace))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/health":
            ai_snapshot = self.ai_budget.snapshot() if self.ai_budget else {}
            pool = get_pexels_pool()
            pixabay_enabled = bool(os.environ.get("PIXABAY_API_KEY"))
            self._send_json(
                {
                    "ok": True,
                    "version": 3,
                    "export_api_version": EXPORT_API_VERSION,
                    "export_mux_mode": "copy",
                    "features": [
                        "segments",
                        "fetch",
                        "select",
                        "export",
                        "ai_judge",
                        "pixabay",
                        "provider_modes",
                        "project_upload",
                        "segment_timestamps",
                    ],
                    "pexels_key_count": pool.size,
                    "pixabay_enabled": pixabay_enabled,
                    "provider_modes": ["mix", "pexels", "pixabay", "random"],
                    "fetch_concurrency": pool.size,
                    "ai_judge": {
                        "enabled": self.use_ai_judge and bool(os.environ.get("OPENAI_API_KEY")),
                        **ai_snapshot,
                    },
                    "project_folder": str(self.project_dir),
                    "script": str(self.script_path),
                    "workspace_mode": self.workspace_mode,
                    "viewer_ready": self._project_ready(),
                    "segment_count": (
                        len(
                            build_segment_rows(
                                self.script_path,
                                self.timestamps_path,
                                self.selections_path,
                            )
                        )
                        if self._project_ready()
                        else 0
                    ),
                }
            )
            return

        if parsed.path == "/api/segments":
            if not self._project_ready():
                project_payload: dict[str, Any] | None = None
                try:
                    workspace = self._require_workspace() if self.workspace_mode else self.project_dir
                    project_payload = project_status(workspace)
                except ValueError as exc:
                    project_payload = {"error": str(exc)}
                self._send_json(
                    {
                        "error": "Project not ready. Import script.json, script.mp3, and run segment timestamps.",
                        "project": project_payload,
                    },
                    HTTPStatus.BAD_REQUEST,
                )
                return
            rows = build_segment_rows(
                self.script_path,
                self.timestamps_path,
                self.selections_path,
            )
            script_data = read_json(self.script_path, {})
            from script_format import detect_script_format
            from folder_fetch import enrich_segments_folder_status

            script_format = detect_script_format(script_data)
            enrich_segments_folder_status(rows, script_format)
            timestamps_meta = read_json(self.timestamps_path, {})
            ai_snapshot = self.ai_budget.snapshot() if self.ai_budget else {}

            self._send_json(
                {
                    "title": script_data.get("title"),
                    "project_folder": str(self.project_dir),
                    "script": str(self.script_path),
                    "script_format": script_format,
                    "video_duration_s": timestamps_meta.get("video_duration_s"),
                    "segments": rows,
                    "judgment_summary": summarize_judgments(rows),
                    "ai_judge": {
                        "enabled": self.use_ai_judge and bool(os.environ.get("OPENAI_API_KEY")),
                        **ai_snapshot,
                    },
                }
            )
            return

        if parsed.path == "/api/folder-fetch/preview":
            if not self._project_ready():
                self._send_json(
                    {"error": "Project not ready."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            try:
                script_data = read_json(self.script_path, {})
                from script_format import detect_script_format
                from folder_fetch import build_folder_fetch_plan

                script_format = detect_script_format(script_data)
                if script_format != "folder":
                    self._send_json(
                        {
                            "error": "Folder fetch requires a folder-format script.json "
                            "(string type per segment).",
                            "script_format": script_format,
                        },
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                rows = build_segment_rows(
                    self.script_path,
                    self.timestamps_path,
                    self.selections_path,
                )
                strategy_param = (params.get("shortage_strategy") or [""])[0].strip()
                shortage_strategy = strategy_param or None
                if shortage_strategy and shortage_strategy not in {
                    "leave_empty",
                    "reuse_spaced",
                    "random_api",
                }:
                    self._send_json(
                        {"error": f"Invalid shortage_strategy: {shortage_strategy}"},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                plan = build_folder_fetch_plan(
                    rows,
                    shortage_strategy=shortage_strategy,  # type: ignore[arg-type]
                )
                plan["script_format"] = script_format
                self._send_json(plan)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/fetch":
            try:
                segment_id = int(params.get("segment_id", ["0"])[0])
                refetch = params.get("refetch", ["false"])[0].lower() in {
                    "1",
                    "true",
                    "yes",
                }
                rows = build_segment_rows(
                    self.script_path,
                    self.timestamps_path,
                    self.selections_path,
                )
                segment = next(
                    (row for row in rows if row["segment_id"] == segment_id),
                    None,
                )
                if segment is None:
                    self._send_json({"error": "Segment not found"}, HTTPStatus.NOT_FOUND)
                    return

                query_override = params.get("query", [""])[0].strip() or None
                provider = params.get("provider", ["mix"])[0].strip().lower()
                use_ai = params.get("ai", ["true"])[0].lower() not in {"0", "false", "no"}
                payload = fetch_segment_video(
                    self.selections_path,
                    self.script_path,
                    segment_id,
                    segment["search_query"],
                    refetch=refetch,
                    query_override=query_override,
                    provider_override=provider,
                    segment=segment,
                    cache_dir=self.cache_dir,
                    use_ai=self.use_ai_judge and use_ai,
                    ai_budget=self.ai_budget,
                    judgment_cache=self.judgment_cache,
                    flagged_path=self.flagged_path,
                )
                self._send_json(payload)
            except Exception as exc:
                print(f"Fetch failed segment {segment_id}: {exc}")
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/search":
            try:
                query = params.get("query", [""])[0]
                page = int(params.get("page", ["1"])[0])
                provider = params.get("provider", ["mix"])[0].strip().lower()
                if not query:
                    self._send_json(
                        {"error": "query is required"},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                if provider == "pexels":
                    payload = pexels_search(query, page=page)
                elif provider == "pixabay":
                    payload = pixabay_search(query, page=page)
                else:
                    payload = mixed_search(query, page=page)
                payload = {
                    **payload,
                    "videos": filter_flagged_videos(payload.get("videos", []), self.flagged_path),
                }
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/status":
            self._send_json(self._export_snapshot())
            return

        if parsed.path == "/api/audio/background":
            try:
                from project_r2 import _r2_configured

                files = list_r2_background_audio()
                self._send_json(
                    {
                        "files": files,
                        "configured": _r2_configured(),
                        "storage_prefix": "Audio/",
                        "narration": {
                            "name": self.audio_path.name,
                            "duration_seconds": round(probe_duration(self.audio_path), 3)
                            if self.audio_path.exists()
                            else None,
                        },
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/audio/narration":
            if not self.audio_path.exists():
                self._send_json({"error": "Narration audio not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_file(self.audio_path, inline=True)
            return

        if parsed.path == "/api/audio/background-file":
            try:
                storage_key = (params.get("key") or params.get("file") or [""])[0]
                if not storage_key:
                    self._send_json({"error": "Background audio key required"}, HTTPStatus.BAD_REQUEST)
                    return
                path = resolve_r2_background_audio(storage_key, self.cache_dir)
                self._send_file(path, inline=True)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/audio/balance":
            try:
                storage_key = (params.get("background") or [""])[0]
                if not self.audio_path.exists():
                    self._send_json({"error": "Narration audio not found"}, HTTPStatus.NOT_FOUND)
                    return
                if storage_key:
                    validate_audio_storage_key(storage_key)
                    background_path = resolve_r2_background_audio(storage_key, self.cache_dir)
                    gains = compute_mix_gains(self.audio_path, background_path)
                    payload = {
                        "background": storage_key,
                        "narration": self.audio_path.name,
                        **gains,
                    }
                else:
                    gains = compute_solo_narration_gains(self.audio_path)
                    payload = {
                        "background": None,
                        "narration": self.audio_path.name,
                        **gains,
                    }
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/audio/preview-file":
            try:
                filename = (params.get("file") or [""])[0]
                preview_path = self.cache_dir / "audio_previews" / filename
                if not preview_path.exists():
                    self._send_json({"error": "Preview not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_file(preview_path, inline=True)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/download":
            snapshot = self._export_snapshot()
            output = snapshot.get("output")
            if snapshot.get("status") != "done" or not output:
                self._send_json({"error": "No completed export available"}, HTTPStatus.BAD_REQUEST)
                return
            self._send_file(Path(output))
            return

        if parsed.path == "/api/duplicates":
            try:
                rows = build_segment_rows(
                    self.script_path,
                    self.timestamps_path,
                    self.selections_path,
                )
                duplicates = find_duplicate_clips(rows)
                affected_segments = {
                    segment_id
                    for group in duplicates
                    for segment_id in group["segment_ids"]
                }
                self._send_json(
                    {
                        "duplicates": duplicates,
                        "total_groups": len(duplicates),
                        "total_segments_affected": len(affected_segments),
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/flagged":
            try:
                rows = build_segment_rows(
                    self.script_path,
                    self.timestamps_path,
                    self.selections_path,
                )
                clips = []
                for clip in list_flagged_clips(self.flagged_path):
                    clip_row = dict(clip)
                    clip_row["segment_ids"] = find_segments_with_clip(
                        rows,
                        {
                            "provider": clip.get("provider"),
                            "video_id": clip.get("video_id"),
                            "url": clip.get("url"),
                        },
                    )
                    clips.append(clip_row)
                self._send_json({"clips": clips})
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        self._sync_from_workspace()

        if parsed.path == "/api/project/create":
            try:
                body = self._read_json_body() if self.headers.get("Content-Length") else {}
                name = str(body.get("name", "")).strip() or None
                project = create_project(WORKSPACE_DIR, name=name)
                workspace = project_workspace(WORKSPACE_DIR, project["id"])
                load_timestamps_job_state(workspace)
                self._send_json(project)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/project/upload/script":
            try:
                workspace = self._require_workspace() if self.workspace_mode else self.project_dir
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" in content_type:
                    parts = parse_multipart_form(self._read_body(), content_type)
                    file_part = parts.get("file") or parts.get("script")
                    if not file_part:
                        self._send_json({"error": "Missing script file"}, HTTPStatus.BAD_REQUEST)
                        return
                    script_data = json.loads(file_part[1].decode("utf-8"))
                else:
                    script_data = self._read_json_body()
                if not script_data:
                    self._send_json({"error": "Empty script payload"}, HTTPStatus.BAD_REQUEST)
                    return
                status = save_script(workspace, script_data)
                self._sync_from_workspace()
                self._send_json(status)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/project/upload/audio":
            try:
                workspace = self._require_workspace() if self.workspace_mode else self.project_dir
                content_type = self.headers.get("Content-Type", "")
                audio_bytes: bytes
                if "multipart/form-data" in content_type:
                    parts = parse_multipart_form(self._read_body(), content_type)
                    file_part = parts.get("file") or parts.get("audio")
                    if not file_part:
                        self._send_json({"error": "Missing audio file"}, HTTPStatus.BAD_REQUEST)
                        return
                    audio_bytes = file_part[1]
                else:
                    audio_bytes = self._read_body()
                if not audio_bytes:
                    self._send_json({"error": "Empty audio payload"}, HTTPStatus.BAD_REQUEST)
                    return
                status = save_audio(workspace, audio_bytes)
                self._sync_from_workspace()
                self._send_json(status)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/project/upload/timestamps":
            try:
                workspace = self._require_workspace() if self.workspace_mode else self.project_dir
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" in content_type:
                    parts = parse_multipart_form(self._read_body(), content_type)
                    file_part = parts.get("file") or parts.get("timestamps")
                    if not file_part:
                        self._send_json({"error": "Missing timestamps file"}, HTTPStatus.BAD_REQUEST)
                        return
                    timestamps_data = json.loads(file_part[1].decode("utf-8"))
                else:
                    timestamps_data = self._read_json_body()
                if not timestamps_data:
                    self._send_json({"error": "Empty timestamps payload"}, HTTPStatus.BAD_REQUEST)
                    return
                status = save_timestamps(workspace, timestamps_data)
                self._sync_from_workspace()
                self._send_json(status)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/project/segment-timestamps":
            try:
                workspace = self._require_workspace() if self.workspace_mode else self.project_dir
                body = self._read_json_body() if self.headers.get("Content-Length") else {}
                model = str(body.get("model", "small"))

                def on_complete() -> None:
                    configure_handler_paths(
                        workspace / "script.json",
                        workspace / "segment_timestamps.json",
                        workspace / "broll_selections.json",
                        workspace / "script.mp3",
                        workspace / "final_video.mp4",
                        use_ai_judge=self.use_ai_judge,
                        ai_max_calls=self.ai_budget.max_calls if self.ai_budget else 100,
                    )

                snapshot = start_segment_timestamps(
                    workspace,
                    model=model,
                    on_complete=on_complete if self.workspace_mode else None,
                )
                self._send_json(snapshot)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/select":
            try:
                body = self._read_json_body()
                segment_id = int(body["segment_id"])
                search_query = body["search_query"]
                video = body["video"]
                if is_clip_flagged(video, self.flagged_path):
                    self._send_json(
                        {"error": "This clip is flagged and cannot be selected"},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                page = int(body.get("page", 1))
                result_index = int(body.get("result_index", 0))
                saved = save_segment_selection(
                    self.selections_path,
                    self.script_path,
                    segment_id,
                    search_query,
                    video,
                    page,
                    result_index,
                    judgment={
                        "confidence": 1.0,
                        "confidence_source": "manual",
                        "needs_review": False,
                        "ai_skipped": None,
                    },
                )
                self._send_json({"segment_id": segment_id, "selection": saved})
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/folder-fetch/apply":
            if not self._project_ready():
                self._send_json(
                    {"error": "Project not ready."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            try:
                script_data = read_json(self.script_path, {})
                from script_format import detect_script_format
                from folder_fetch import apply_folder_fetch_plan, build_folder_fetch_plan

                if detect_script_format(script_data) != "folder":
                    self._send_json(
                        {"error": "Folder fetch requires a folder-format script.json."},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                rows = build_segment_rows(
                    self.script_path,
                    self.timestamps_path,
                    self.selections_path,
                )
                body = self._read_json_body() if self.headers.get("Content-Length") else {}
                shortage_strategy = str(body.get("shortage_strategy") or "").strip() or None
                if shortage_strategy and shortage_strategy not in {
                    "leave_empty",
                    "reuse_spaced",
                    "random_api",
                }:
                    self._send_json(
                        {"error": f"Invalid shortage_strategy: {shortage_strategy}"},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                plan = build_folder_fetch_plan(
                    rows,
                    shortage_strategy=shortage_strategy,  # type: ignore[arg-type]
                )
                if plan.get("needs_shortage_choice"):
                    self._send_json(
                        {
                            "error": "Choose how to handle folder shortages before applying.",
                            "shortages": plan.get("shortages", []),
                        },
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                segments_by_id = {row["segment_id"]: row for row in rows}
                result = apply_folder_fetch_plan(
                    self.selections_path,
                    self.script_path,
                    segments_by_id,
                    plan["assignments"],
                    cache_dir=self.cache_dir,
                    use_ai=self.use_ai_judge,
                    ai_budget=self.ai_budget,
                    judgment_cache=self.judgment_cache,
                    flagged_path=self.flagged_path,
                )
                result["summary"] = plan["summary"]
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/select/storage":
            try:
                body = self._read_json_body()
                segment_id = int(body["segment_id"])
                search_query = body["search_query"]
                storage_key = str(body.get("storage_key") or "").strip()
                clip_duration = body.get("duration")
                loop = bool(body.get("loop", False))
                duration_value = None
                if clip_duration is not None:
                    try:
                        duration_value = float(clip_duration)
                    except (TypeError, ValueError):
                        duration_value = None

                video = build_storage_selection(
                    storage_key,
                    duration=duration_value,
                    loop=loop,
                )
                if is_clip_flagged(video, self.flagged_path):
                    self._send_json(
                        {"error": "This clip is flagged and cannot be selected"},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                saved = save_segment_selection(
                    self.selections_path,
                    self.script_path,
                    segment_id,
                    search_query,
                    video,
                    1,
                    0,
                    query_used=f"storage:{storage_key}",
                    fetch_provider="storage",
                    judgment={
                        "confidence": 1.0,
                        "confidence_source": "manual",
                        "needs_review": False,
                        "ai_skipped": None,
                    },
                )
                self._send_json({"segment_id": segment_id, "selection": saved})
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/start":
            try:
                body = self._read_json_body() if self.headers.get("Content-Length") else {}
                background_audio = body.get("background_audio")
                if background_audio is not None and not isinstance(background_audio, str):
                    raise ValueError("background_audio must be an R2 storage key string or null")
                narration_adjust_db, background_adjust_db = parse_mix_adjustments(body)
                resolution = str(body.get("resolution") or "4k").strip().lower()
                quality = str(body.get("quality") or "balanced").strip().lower()
                self._start_export_job(
                    background_audio=background_audio or None,
                    narration_adjust_db=narration_adjust_db,
                    background_adjust_db=background_adjust_db,
                    resolution=resolution,
                    quality=quality,
                )
                self._send_json(self._export_snapshot())
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/audio/preview":
            try:
                body = self._read_json_body()
                background_audio = body.get("background_audio")
                narration_adjust_db, background_adjust_db = parse_mix_adjustments(body)
                if not self.audio_path.exists():
                    raise FileNotFoundError("Narration audio not found")
                preview_seconds = float(body.get("preview_seconds") or 45)
                preview_dir = self.cache_dir / "audio_previews"
                preview_dir.mkdir(parents=True, exist_ok=True)
                preview_name = preview_cache_name(
                    str(background_audio) if background_audio else None,
                    preview_seconds,
                    narration_adjust_db,
                    background_adjust_db,
                )
                preview_path = preview_dir / preview_name

                if background_audio:
                    storage_key = str(background_audio)
                    validate_audio_storage_key(storage_key)
                    background_path = resolve_r2_background_audio(storage_key, self.cache_dir)
                    base_gains = compute_mix_gains(self.audio_path, background_path)
                    gains = apply_mix_adjustments(
                        base_gains,
                        narration_adjust_db=narration_adjust_db,
                        background_adjust_db=background_adjust_db,
                    )
                    build_mixed_audio(
                        narration_path=self.audio_path,
                        background_path=background_path,
                        output_path=preview_path,
                        gains=gains,
                        preview_seconds=preview_seconds,
                    )
                    background_name = storage_key
                else:
                    base_gains = compute_solo_narration_gains(self.audio_path)
                    gains = apply_mix_adjustments(
                        base_gains,
                        narration_adjust_db=narration_adjust_db,
                        background_adjust_db=0.0,
                    )
                    render_narration_audio(
                        self.audio_path,
                        preview_path,
                        gains["narration_gain_db"],
                        preview_seconds=preview_seconds,
                    )
                    background_name = None

                self._send_json(
                    {
                        "preview_url": f"/api/audio/preview-file?file={urllib.parse.quote(preview_name)}",
                        "preview_seconds": preview_seconds,
                        "background_audio": background_name,
                        "narration": self.audio_path.name,
                        **gains,
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/cancel":
            try:
                self._cancel_export_job()
                self._send_json(self._export_snapshot())
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/rescore/unscored":
            try:
                body = self._read_json_body() if self.headers.get("Content-Length") else {}
                use_ai = str(body.get("ai", "true")).lower() not in {"0", "false", "no"}
                payload = rescore_unscored_segments(
                    self.selections_path,
                    self.script_path,
                    self.timestamps_path,
                    cache_dir=self.cache_dir,
                    use_ai=self.use_ai_judge and use_ai,
                    ai_budget=self.ai_budget,
                    judgment_cache=self.judgment_cache,
                )
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/flagged":
            try:
                body = self._read_json_body()
                segment_id = int(body["segment_id"])
                rows = build_segment_rows(
                    self.script_path,
                    self.timestamps_path,
                    self.selections_path,
                )
                segment = next(
                    (row for row in rows if row["segment_id"] == segment_id),
                    None,
                )
                if segment is None:
                    self._send_json({"error": "Segment not found"}, HTTPStatus.NOT_FOUND)
                    return
                selection = segment.get("selection")
                if not selection or not selection.get("url"):
                    self._send_json(
                        {"error": "Segment has no selected clip to flag"},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                clip = flag_clip(self.flagged_path, selection)
                affected_segment_ids = find_segments_with_clip(rows, selection)
                self._send_json(
                    {
                        "clip": clip,
                        "affected_segment_ids": affected_segment_ids,
                        "affected_count": len(affected_segment_ids),
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/flagged/unflag":
            try:
                body = self._read_json_body()
                key = str(body.get("key") or "").strip()
                if not key:
                    self._send_json({"error": "key is required"}, HTTPStatus.BAD_REQUEST)
                    return
                removed = unflag_clip(self.flagged_path, key)
                if not removed:
                    self._send_json({"error": "Flagged clip not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json({"ok": True, "key": key})
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Billions b-roll viewer.",
        epilog=(
            "Examples:\n"
            "  python broll_viewer.py video\n"
            "  python broll_viewer.py video2\n"
            "  python broll_viewer.py video --port 8766"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=None,
        help="Folder containing script.json, script.mp3, and segment_timestamps.json. "
             "Overrides all --script/--timestamps/--audio/--selections/--output defaults.",
    )
    parser.add_argument(
        "--workspace",
        action="store_true",
        help="Use backend/workspace for uploads (no pre-existing project required).",
    )
    parser.add_argument("--script", default=None)
    parser.add_argument("--timestamps", default=None)
    parser.add_argument("--selections", default=None)
    parser.add_argument("--audio", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--no-ai-judge",
        action="store_true",
        help="Disable OpenAI thumbnail judging (heuristics only).",
    )
    parser.add_argument(
        "--ai-max-calls",
        type=int,
        default=100,
        help="Max OpenAI judge calls per day (default: 100).",
    )
    return parser.parse_args()


def resolve_paths(
    args: argparse.Namespace,
) -> tuple[Path, Path, Path, Path, Path, bool]:
    if getattr(args, "workspace", False):
        base = WORKSPACE_DIR
        script_path = base / "script.json"
        timestamps_path = base / "segment_timestamps.json"
        selections_path = base / "broll_selections.json"
        audio_path = base / "script.mp3"
        output_path = base / "final_video.mp4"
        return script_path, timestamps_path, selections_path, audio_path, output_path, True

    if args.folder:
        folder = Path(args.folder)
        if not folder.is_dir():
            raise SystemExit(f"Folder not found: {folder}")
        base = folder
    else:
        base = VIDEO_DIR

    script_path = Path(args.script) if args.script else base / "script.json"
    timestamps_path = Path(args.timestamps) if args.timestamps else base / "segment_timestamps.json"
    selections_path = Path(args.selections) if args.selections else base / "broll_selections.json"
    audio_path = Path(args.audio) if args.audio else base / "script.mp3"
    output_path = Path(args.output) if args.output else base / "final_video.mp4"

    for label, path in (
        ("Script", script_path),
        ("Timestamps", timestamps_path),
        ("Audio", audio_path),
    ):
        if not path.exists():
            raise SystemExit(f"{label} not found: {path}")

    return script_path, timestamps_path, selections_path, audio_path, output_path, False


def configure_handler_paths(
    script_path: Path,
    timestamps_path: Path,
    selections_path: Path,
    audio_path: Path,
    output_path: Path,
    *,
    use_ai_judge: bool,
    ai_max_calls: int,
) -> Path:
    project_dir = script_path.parent
    export_status_file = project_dir / ".broll_export_status.json"
    cache_dir = project_dir / ".broll_cache"

    BrollViewerHandler.script_path = script_path
    BrollViewerHandler.timestamps_path = timestamps_path
    BrollViewerHandler.selections_path = selections_path
    BrollViewerHandler.audio_path = audio_path
    BrollViewerHandler.output_path = output_path
    BrollViewerHandler.project_dir = project_dir
    BrollViewerHandler.export_status_file = export_status_file
    BrollViewerHandler.flagged_path = project_dir / ".broll_flagged.json"
    BrollViewerHandler.cache_dir = cache_dir
    BrollViewerHandler.use_ai_judge = use_ai_judge
    BrollViewerHandler.ai_budget = AiBudget(cache_dir, max_calls=ai_max_calls)
    BrollViewerHandler.judgment_cache = JudgmentCache(cache_dir)
    return project_dir


def ensure_port_available(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError as exc:
            raise SystemExit(
                f"Port {port} is already in use — another broll_viewer.py is probably still running.\n"
                f"Stop it with Ctrl+C in that terminal, or run:\n"
                f"  python broll_viewer.py <folder> --port {port + 1}"
            ) from exc


def main() -> None:
    args = parse_args()
    load_env_file()

    pool = get_pexels_pool()

    script_path, timestamps_path, selections_path, audio_path, output_path, workspace_mode = (
        resolve_paths(args)
    )
    project_dir = configure_handler_paths(
        script_path,
        timestamps_path,
        selections_path,
        audio_path,
        output_path,
        use_ai_judge=not args.no_ai_judge,
        ai_max_calls=args.ai_max_calls,
    )
    BrollViewerHandler.workspace_mode = workspace_mode

    if workspace_mode:
        from project_r2 import restore_workspace_from_r2

        migrate_legacy_workspace(WORKSPACE_DIR)
        migrate_user_scoped_projects(WORKSPACE_DIR)
        load_all_timestamps_job_states(WORKSPACE_DIR)
        for project in list_projects(WORKSPACE_DIR):
            try:
                restore_workspace_from_r2(project_workspace(WORKSPACE_DIR, project["id"]))
            except Exception as exc:
                print(f"[project-r2] Restore skipped for {project['id']}: {exc}")

    export_status_file = project_dir / ".broll_export_status.json"
    load_persisted_export_state(export_status_file)
    ensure_port_available(args.host, args.port)

    server = ThreadingHTTPServer((args.host, args.port), BrollViewerHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"B-roll viewer API running at {url}")
    print(f"Project folder: {project_dir}")
    if workspace_mode:
        print("Workspace mode: import script.json and script.mp3 via the web UI.")
    else:
        print(f"Script: {BrollViewerHandler.script_path}")
        print(f"Timestamps: {BrollViewerHandler.timestamps_path}")
        print(f"Selections: {BrollViewerHandler.selections_path}")
        print(f"Audio: {BrollViewerHandler.audio_path}")
        print(f"Export output: {BrollViewerHandler.output_path}")
    print(f"Export API v{EXPORT_API_VERSION} (mux: video copy, fresh on each export)")
    print(f"Pexels API keys: {pool.size} — parallel fetch concurrency: {pool.size}")
    print(
        "Pixabay API: "
        + ("enabled" if os.environ.get("PIXABAY_API_KEY") else "disabled (set PIXABAY_API_KEY)")
    )
    if BrollViewerHandler.use_ai_judge and os.environ.get("OPENAI_API_KEY"):
        budget = BrollViewerHandler.ai_budget.snapshot()
        print(
            "AI judge: enabled "
            f"({budget['remaining']}/{budget['max_calls']} calls remaining today)"
        )
    elif BrollViewerHandler.use_ai_judge:
        print("AI judge: enabled but OPENAI_API_KEY missing — heuristics only")
    else:
        print("AI judge: disabled")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
