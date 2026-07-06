#!/usr/bin/env python3
"""Local server for the Billions b-roll viewer."""

from __future__ import annotations

import argparse
import base64
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

from export_job_state import (
    clear_cancel_event,
    compute_export_inputs_hash,
    export_snapshot,
    get_cancel_event,
    list_running_exports,
    load_all_export_states,
    project_export_running,
    set_cancel_event,
    update_export_state,
)
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
    set_export_context,
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
from youtube_description import build_youtube_description
from youtube_thumbnail_prompts import build_thumbnail_prompts
from project_manager import (
    _alignment_summary_from_timestamps_file,
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
    purge_stale_exported_videos,
    resolve_r2_background_audio,
    touch_exported_video_access,
    upload_exported_video,
    upload_storage_audio,
    validate_audio_storage_key,
    validate_audio_storage_prefix,
)
from user_sessions import (
    create_project,
    delete_project,
    list_projects,
    migrate_legacy_workspace,
    migrate_user_scoped_projects,
    project_workspace,
    prune_stale_projects,
    read_manifest,
)
from youtube_audio_job import (
    get_youtube_audio_job,
    list_running_youtube_audio_jobs,
    start_youtube_audio_job,
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


def project_is_protected(project_id: str) -> bool:
    """True if a project has a running job and must not be deleted/pruned."""
    if project_export_running(project_id):
        return True
    try:
        workspace = project_workspace(WORKSPACE_DIR, project_id)
        if timestamps_job_snapshot(workspace).get("status") == "running":
            return True
    except Exception:
        pass
    return False


def prune_inactive_projects() -> list[str]:
    """Remove projects past their inactivity TTL, skipping any with active jobs."""
    try:
        return prune_stale_projects(WORKSPACE_DIR, is_protected=project_is_protected)
    except Exception as exc:  # noqa: BLE001
        print(f"[projects] Prune sweep failed: {exc}")
        return []


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



ROOT_STORAGE_FOLDERS = ("Audio", "B-Roll", "Other", "Exported Videos")
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
        if origin in allowed_origins:
            return origin
        # Vercel deployments upload audio directly to the tunnel (bypasses body limits).
        if origin.endswith(".vercel.app") and os.environ.get("BROLL_ALLOW_VERCEL_CORS", "1") == "1":
            return origin
        return None

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

    def _export_snapshot_for(self, project_id: str | None = None) -> dict[str, Any]:
        pid = (project_id or self.headers.get("X-Billions-Project", "")).strip()
        if not pid:
            raise ValueError("Select a project first.")
        workspace = project_workspace(WORKSPACE_DIR, pid)
        status_file = workspace_paths(workspace)["export_status"]
        return export_snapshot(pid, status_file)

    def _regenerate_youtube_description(
        self,
        *,
        include_emojis: bool = True,
        include_chapters: bool = False,
    ) -> dict[str, Any]:
        project_id = self.headers.get("X-Billions-Project", "").strip()
        if not project_id:
            raise ValueError("Select a project first.")
        workspace = self._require_workspace()
        if not self.script_path.exists():
            raise ValueError("Script not found for this project.")

        project_name = None
        try:
            project_name = read_manifest(workspace).get("name")
        except Exception:
            project_name = None
        if not project_name:
            title = read_json(self.timestamps_path, {}).get("title")
            project_name = title or project_id[:8]

        youtube_description = build_youtube_description(
            script_path=self.script_path,
            timestamps_path=self.timestamps_path,
            selections_path=self.selections_path,
            project_name=project_name,
            include_emojis=include_emojis,
            include_chapters=include_chapters,
        )
        status_file = workspace_paths(workspace)["export_status"]
        update_export_state(project_id, status_file, youtube_description=youtube_description)
        return self._export_snapshot_for(project_id)

    def _regenerate_thumbnail_prompts(self) -> dict[str, Any]:
        project_id = self.headers.get("X-Billions-Project", "").strip()
        if not project_id:
            raise ValueError("Select a project first.")
        workspace = self._require_workspace()
        if not self.script_path.exists():
            raise ValueError("Script not found for this project.")

        project_name = None
        try:
            project_name = read_manifest(workspace).get("name")
        except Exception:
            project_name = None
        if not project_name:
            title = read_json(self.timestamps_path, {}).get("title")
            project_name = title or project_id[:8]

        thumbnail_prompts = build_thumbnail_prompts(
            script_path=self.script_path,
            project_name=project_name,
        )
        status_file = workspace_paths(workspace)["export_status"]
        update_export_state(project_id, status_file, thumbnail_prompts=thumbnail_prompts)
        return self._export_snapshot_for(project_id)

    def _download_youtube_audio(self) -> None:
        body = self._read_json_body()
        url = str(body.get("url") or "").strip()
        prefix = str(body.get("prefix") or "").strip()
        if not url:
            raise ValueError("YouTube URL is required.")

        job_id = start_youtube_audio_job(url, prefix)
        self._send_json({"job_id": job_id, "status": "running"})

    def _youtube_audio_job_snapshot(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        job_id = str((params.get("job_id") or [""])[0]).strip()
        if not job_id:
            self._send_json({"error": "job_id is required"}, HTTPStatus.BAD_REQUEST)
            return
        job = get_youtube_audio_job(job_id)
        if not job:
            self._send_json({"error": "Download job not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json(job)

    def _activity_snapshot(self) -> dict[str, Any]:
        """Global view of all running jobs across projects (navbar indicator)."""
        jobs: list[dict[str, Any]] = []

        try:
            for project in list_projects(WORKSPACE_DIR):
                job = project.get("timestamps_job") or {}
                if job.get("status") == "running":
                    jobs.append(
                        {
                            "type": "whisper",
                            "label": "Transcribing",
                            "project_id": project.get("id"),
                            "project_name": project.get("name"),
                            "progress_percent": int(job.get("progress_percent") or 0),
                            "message": job.get("message") or "Generating timestamps…",
                            "stage": job.get("stage"),
                        }
                    )
        except Exception:
            pass

        for export in list_running_exports():
            jobs.append(
                {
                    "type": "export",
                    "label": "Rendering",
                    "project_id": export.get("project_id"),
                    "project_name": export.get("project_name"),
                    "progress_percent": int(export.get("progress_percent") or 0),
                    "message": export.get("message") or "Exporting video…",
                    "stage": export.get("stage"),
                    "eta_seconds": export.get("eta_seconds"),
                }
            )

        for yt_job in list_running_youtube_audio_jobs():
            jobs.append(
                {
                    "type": "youtube_audio",
                    "label": "YT audio",
                    "job_id": yt_job.get("job_id"),
                    "project_id": None,
                    "project_name": yt_job.get("title") or "YouTube",
                    "progress_percent": int(yt_job.get("progress_percent") or 0),
                    "message": yt_job.get("message") or "Downloading audio…",
                    "stage": yt_job.get("stage"),
                }
            )

        gpu = None
        if jobs:
            try:
                from hardware_monitor import gpu_snapshot

                gpu = gpu_snapshot()
            except Exception:
                gpu = None

        return {"jobs": jobs, "gpu": gpu, "busy": bool(jobs)}

    def _start_export_job(
        self,
        background_audio: str | None = None,
        *,
        narration_adjust_db: float = 0.0,
        background_adjust_db: float = 0.0,
        resolution: str = "4k",
        quality: str = "balanced",
        include_subtitles: bool = False,
    ) -> None:
        project_id = self.headers.get("X-Billions-Project", "").strip()
        if not project_id:
            raise RuntimeError("Select a project first.")

        workspace = self._require_workspace()
        status_file = workspace_paths(workspace)["export_status"]

        if project_export_running(project_id):
            raise RuntimeError("Export already in progress for this project")

        clear_cancel_event(project_id)
        cancel_event = get_cancel_event(project_id)

        title = read_json(self.timestamps_path, {}).get("title")
        output_path = self.output_path
        if title:
            output_path = output_path.parent / sanitize_output_name(title)

        project_name = None
        try:
            project_name = read_manifest(workspace).get("name")
        except Exception:
            project_name = None
        if not project_name:
            project_name = title or project_id[:8]

        def set_state(**kwargs: Any) -> None:
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

        def hardware_monitor_loop() -> None:
            from hardware_monitor import resolve_whisper_device, sample_hardware_stats

            device, device_info = resolve_whisper_device()
            while project_export_running(project_id):
                stats = sample_hardware_stats(device, device_info)
                set_state(hardware=stats)
                time.sleep(1.5)

        def worker() -> None:
            set_export_context(project_id)
            hw_thread = threading.Thread(target=hardware_monitor_loop, daemon=True)
            hw_thread.start()
            try:
                background_audio_path = None
                if background_audio:
                    on_progress("download", 0, 0, "Downloading background audio…")
                    background_audio_path = resolve_r2_background_audio(
                        background_audio,
                        self.cache_dir,
                    )

                result = export_video(
                    audio_path=self.audio_path,
                    timestamps_path=self.timestamps_path,
                    selections_path=self.selections_path,
                    script_path=self.script_path,
                    output_path=output_path,
                    on_progress=on_progress,
                    cache_dir=self.cache_dir,
                    fresh=True,
                    should_cancel=cancel_event.is_set,
                    background_audio_path=background_audio_path,
                    narration_adjust_db=narration_adjust_db,
                    background_adjust_db=background_adjust_db,
                    resolution=resolution,
                    quality=quality,
                    include_subtitles=include_subtitles,
                )
                if cancel_event.is_set():
                    return
                inputs_hash = compute_export_inputs_hash(
                    timestamps_path=self.timestamps_path,
                    selections_path=self.selections_path,
                    audio_path=self.audio_path,
                )
                # Upload to R2 "Exported Videos/" folder asynchronously.
                r2_key: str | None = None
                try:
                    r2_key = upload_exported_video(
                        Path(result["output"]),
                        project_name or project_id[:8],
                    )
                except Exception as r2_exc:
                    print(f"[export-r2] Upload skipped: {r2_exc}")
                youtube_description: str | None = None
                try:
                    youtube_description = build_youtube_description(
                        script_path=self.script_path,
                        timestamps_path=self.timestamps_path,
                        selections_path=self.selections_path,
                        project_name=project_name or project_id[:8],
                    )
                except Exception as desc_exc:
                    print(f"[export] Description generation skipped: {desc_exc}")
                set_state(
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
                    inputs_hash=inputs_hash,
                    r2_key=r2_key,
                    youtube_description=youtube_description,
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

    def _cancel_export_job(self) -> None:
        project_id = self.headers.get("X-Billions-Project", "").strip()
        if not project_id:
            raise RuntimeError("Select a project first.")
        if not project_export_running(project_id):
            raise RuntimeError("No export in progress for this project")

        workspace = self._require_workspace()
        status_file = workspace_paths(workspace)["export_status"]

        set_cancel_event(project_id)
        request_export_cancel(project_id)
        update_export_state(
            project_id,
            status_file,
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
                from project_r2 import sync_local_projects_with_r2

                sync_local_projects_with_r2(WORKSPACE_DIR)
                prune_inactive_projects()
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

        if parsed.path == "/api/project/script/transcript":
            try:
                from script_format import build_narration_transcript, iter_content_segments

                if not self.script_path.exists():
                    raise ValueError("Upload script.json first.")
                script_data = read_json(self.script_path, {})
                transcript = build_narration_transcript(script_data)
                segment_count = len(iter_content_segments(script_data))
                word_count = len(transcript.split())
                self._send_json(
                    {
                        "transcript": transcript,
                        "segment_count": segment_count,
                        "word_count": word_count,
                    }
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
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
            timestamp_alignment = _alignment_summary_from_timestamps_file(timestamps_meta)

            self._send_json(
                {
                    "title": script_data.get("title"),
                    "project_folder": str(self.project_dir),
                    "script": str(self.script_path),
                    "script_format": script_format,
                    "video_duration_s": timestamps_meta.get("video_duration_s"),
                    "timestamp_alignment": timestamp_alignment,
                    "segments": rows,
                    "judgment_summary": summarize_judgments(rows),
                    "export_inputs_hash": compute_export_inputs_hash(
                        timestamps_path=self.timestamps_path,
                        selections_path=self.selections_path,
                        audio_path=self.audio_path,
                    ),
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
                if segment.get("render_mode") == "remotion":
                    remotion = segment.get("remotion") or {}
                    layout = str(remotion.get("layout") or "").strip().lower()
                    if layout != "split-right":
                        self._send_json(
                            {
                                "error": (
                                    "Remotion segments are rendered automatically and do not use b-roll fetch."
                                )
                            },
                            HTTPStatus.BAD_REQUEST,
                        )
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

        if parsed.path == "/api/export/inputs-hash":
            try:
                if not self._project_ready():
                    raise ValueError("Project not ready.")
                self._send_json(
                    {
                        "export_inputs_hash": compute_export_inputs_hash(
                            timestamps_path=self.timestamps_path,
                            selections_path=self.selections_path,
                            audio_path=self.audio_path,
                        ),
                    }
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/status":
            try:
                self._send_json(self._export_snapshot_for())
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/storage/youtube-audio/status":
            try:
                self._youtube_audio_job_snapshot()
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/activity":
            self._send_json(self._activity_snapshot())
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
                filename = Path((params.get("file") or [""])[0]).name
                if not filename:
                    self._send_json({"error": "Preview filename required"}, HTTPStatus.BAD_REQUEST)
                    return
                if self.workspace_mode and self._active_workspace() is None:
                    self._send_json({"error": "Select a project first."}, HTTPStatus.BAD_REQUEST)
                    return
                preview_path = self.cache_dir / "audio_previews" / filename
                if not preview_path.exists():
                    self._send_json({"error": "Preview not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_file(preview_path, inline=True)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/remotion/preview-file":
            try:
                filename = Path((params.get("file") or [""])[0]).name
                if not filename or ".." in filename or "/" in filename or "\\" in filename:
                    self._send_json({"error": "Preview filename required"}, HTTPStatus.BAD_REQUEST)
                    return
                if self.workspace_mode and self._active_workspace() is None:
                    self._send_json({"error": "Select a project first."}, HTTPStatus.BAD_REQUEST)
                    return
                preview_path = self.cache_dir / "remotion_previews" / filename
                if not preview_path.exists():
                    self._send_json({"error": "Preview not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_file(preview_path, inline=True)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/download":
            try:
                qp = urllib.parse.parse_qs(parsed.query)
                pid_from_qs = (qp.get("project") or [""])[0].strip()
                snapshot = self._export_snapshot_for(project_id=pid_from_qs or None)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            output = snapshot.get("output")
            if snapshot.get("status") != "done" or not output:
                self._send_json({"error": "No completed export available"}, HTTPStatus.BAD_REQUEST)
                return
            # Touch R2 last-downloaded timestamp (non-blocking).
            r2_key = snapshot.get("r2_key")
            if r2_key:
                threading.Thread(
                    target=touch_exported_video_access,
                    args=(r2_key,),
                    daemon=True,
                ).start()
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

        if parsed.path == "/api/project/delete":
            try:
                body = self._read_json_body() if self.headers.get("Content-Length") else {}
                project_id = str(
                    body.get("project_id")
                    or self.headers.get("X-Billions-Project", "")
                ).strip()
                if not project_id:
                    self._send_json({"error": "project_id required"}, HTTPStatus.BAD_REQUEST)
                    return
                if project_is_protected(project_id):
                    self._send_json(
                        {"error": "Project has a running job and can't be deleted."},
                        HTTPStatus.CONFLICT,
                    )
                    return
                delete_project(WORKSPACE_DIR, project_id)
                self._send_json({"ok": True, "deleted": project_id})
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
                from segment_timestamps import normalize_whisper_model

                model = normalize_whisper_model(str(body.get("model", "medium")))
                retranscribe = bool(body.get("retranscribe", False))

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
                    retranscribe=retranscribe,
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

        if parsed.path == "/api/remotion/props":
            try:
                if not self._project_ready():
                    self._send_json({"error": "Project not ready."}, HTTPStatus.BAD_REQUEST)
                    return
                body = self._read_json_body()
                segment_id = int(body["segment_id"])
                props = body.get("props")
                if not isinstance(props, dict):
                    raise ValueError("props object is required.")
                from remotion_editor import update_remotion_segment_props

                workspace = self._active_workspace()
                if workspace is None:
                    raise ValueError("Select a project first.")
                remotion = update_remotion_segment_props(workspace, segment_id, props)
                self._send_json(
                    {
                        "segment_id": segment_id,
                        "remotion": remotion,
                        "export_inputs_hash": compute_export_inputs_hash(
                            timestamps_path=self.timestamps_path,
                            selections_path=self.selections_path,
                            audio_path=self.audio_path,
                        ),
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/remotion/suggest":
            try:
                if not self._project_ready():
                    self._send_json({"error": "Project not ready."}, HTTPStatus.BAD_REQUEST)
                    return
                body = self._read_json_body()
                segment_id = int(body["segment_id"])
                user_prompt = str(body.get("prompt") or "").strip()
                current_props = body.get("current_props")
                if not isinstance(current_props, dict):
                    current_props = {}

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
                if segment.get("render_mode") != "remotion" or not segment.get("remotion"):
                    self._send_json(
                        {"error": "Segment is not a Remotion segment."},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                remotion = segment["remotion"]
                composition = str(remotion["composition"])
                base_props = dict(remotion.get("props") or {})
                base_props.update(current_props)

                script_prompt = str(remotion.get("prompt") or "")

                from remotion_ai import suggest_remotion_props

                result = suggest_remotion_props(
                    composition=composition,
                    segment_content=str(segment.get("content") or ""),
                    segment_description=str(segment.get("description") or ""),
                    script_prompt=script_prompt,
                    current_props=base_props,
                    user_prompt=user_prompt,
                    ai_budget=self.ai_budget if self.use_ai_judge else None,
                )
                self._send_json(
                    {
                        "segment_id": segment_id,
                        "composition": composition,
                        "props": result["props"],
                        "updates": result.get("updates") or {},
                        "summary": result.get("summary") or "",
                        "ai_used": bool(result.get("ai_used")),
                        "ai_judge": {
                            "enabled": self.use_ai_judge and bool(os.environ.get("OPENAI_API_KEY")),
                            **(self.ai_budget.snapshot() if self.ai_budget else {}),
                        },
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/remotion/preview":
            try:
                if not self._project_ready():
                    self._send_json({"error": "Project not ready."}, HTTPStatus.BAD_REQUEST)
                    return
                body = self._read_json_body()
                segment_id = int(body["segment_id"])
                props_override = body.get("props")
                save_first = body.get("save", False)
                if isinstance(save_first, str):
                    save_first = save_first.lower() in {"1", "true", "yes"}

                workspace = self._active_workspace()
                if workspace is None:
                    raise ValueError("Select a project first.")

                if save_first and isinstance(props_override, dict):
                    from remotion_editor import update_remotion_segment_props

                    update_remotion_segment_props(workspace, segment_id, props_override)

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
                if segment.get("render_mode") != "remotion" or not segment.get("remotion"):
                    self._send_json(
                        {"error": "Segment is not a Remotion segment."},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return

                remotion = segment["remotion"]
                composition = str(remotion["composition"])
                props = dict(remotion.get("props") or {})
                if isinstance(props_override, dict):
                    from remotion_editor import find_script_segment, merge_remotion_props

                    script_data = read_json(self.script_path, {})
                    script_segment = find_script_segment(script_data, segment_id)
                    if script_segment is not None:
                        merged = merge_remotion_props(script_segment, props_override)
                        props = merged["props"]

                from remotion_editor import (
                    preview_cache_name,
                    render_remotion_segment_preview,
                    segment_preview_duration_seconds,
                )

                duration_seconds = segment_preview_duration_seconds(
                    segment_id=segment_id,
                    timestamps_path=self.timestamps_path,
                )
                preview_path = render_remotion_segment_preview(
                    workspace=workspace,
                    cache_dir=self.cache_dir,
                    segment_id=segment_id,
                    composition=composition,
                    props=props,
                    duration_seconds=duration_seconds,
                    force=bool(props_override),
                )
                preview_name = preview_cache_name(
                    segment_id, composition, props, duration_seconds
                )
                preview_url = f"/api/remotion/preview-file?file={urllib.parse.quote(preview_name)}"
                self._send_json(
                    {
                        "segment_id": segment_id,
                        "composition": composition,
                        "props": props,
                        "preview_url": preview_url,
                        "duration_seconds": duration_seconds,
                    }
                )
            except Exception as exc:
                print(f"Remotion preview failed: {exc}")
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
                include_subtitles = body.get("include_subtitles", False)
                if isinstance(include_subtitles, str):
                    include_subtitles = include_subtitles.lower() not in {"0", "false", "no"}
                else:
                    include_subtitles = bool(include_subtitles)
                self._start_export_job(
                    background_audio=background_audio or None,
                    narration_adjust_db=narration_adjust_db,
                    background_adjust_db=background_adjust_db,
                    resolution=resolution,
                    quality=quality,
                    include_subtitles=include_subtitles,
                )
                self._send_json(self._export_snapshot_for())
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/audio/preview":
            try:
                if self.workspace_mode:
                    self._require_workspace()
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

                if not preview_path.exists() or preview_path.stat().st_size <= 0:
                    raise RuntimeError("Preview render produced an empty file")

                preview_bytes = preview_path.read_bytes()
                preview_b64 = base64.b64encode(preview_bytes).decode("ascii")
                preview_url = f"/api/audio/preview-file?file={urllib.parse.quote(preview_name)}"

                self._send_json(
                    {
                        "preview_url": preview_url,
                        "preview_data_url": f"data:audio/mp4;base64,{preview_b64}",
                        "preview_seconds": preview_seconds,
                        "background_audio": background_name,
                        "narration": self.audio_path.name,
                        **gains,
                    }
                )
            except Exception as exc:
                summary = summarize_export_error(exc)
                self._send_json({"error": summary}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/cancel":
            try:
                self._cancel_export_job()
                self._send_json(self._export_snapshot_for())
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/youtube-description":
            try:
                body = self._read_json_body() if self.headers.get("Content-Length") else {}
                include_emojis = body.get("include_emojis", True)
                if isinstance(include_emojis, str):
                    include_emojis = include_emojis.lower() not in {"0", "false", "no"}
                else:
                    include_emojis = bool(include_emojis)
                include_chapters = body.get("include_chapters", False)
                if isinstance(include_chapters, str):
                    include_chapters = include_chapters.lower() not in {"0", "false", "no"}
                else:
                    include_chapters = bool(include_chapters)
                snapshot = self._regenerate_youtube_description(
                    include_emojis=include_emojis,
                    include_chapters=include_chapters,
                )
                self._send_json(snapshot)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/export/thumbnail-prompts":
            try:
                snapshot = self._regenerate_thumbnail_prompts()
                self._send_json(snapshot)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/storage/youtube-audio":
            try:
                self._download_youtube_audio()
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
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
        from project_r2 import restore_workspace_from_r2, sync_local_projects_with_r2

        migrate_legacy_workspace(WORKSPACE_DIR)
        migrate_user_scoped_projects(WORKSPACE_DIR)
        sync_local_projects_with_r2(WORKSPACE_DIR)
        load_all_timestamps_job_states(WORKSPACE_DIR)
        prune_inactive_projects()
        for project in list_projects(WORKSPACE_DIR):
            try:
                restore_workspace_from_r2(project_workspace(WORKSPACE_DIR, project["id"]))
            except Exception as exc:
                print(f"[project-r2] Restore skipped for {project['id']}: {exc}")

        def _prune_loop() -> None:
            while True:
                time.sleep(3600)
                prune_inactive_projects()
                try:
                    purge_stale_exported_videos()
                except Exception as exc:
                    print(f"[export-r2] Purge error: {exc}")

        threading.Thread(target=_prune_loop, daemon=True).start()

    load_all_export_states(WORKSPACE_DIR)
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
