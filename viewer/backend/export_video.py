#!/usr/bin/env python3
"""Assemble narration MP3 + selected b-roll clips into a final video.

Uses ffmpeg with GPU encoding when available (NVENC > AMF > QSV > CPU).

Usage:
    python export_video.py script.mp3 segment_timestamps.json broll_selections.json
    python export_video.py script.mp3 segment_timestamps.json broll_selections.json -o final.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
EXPORT_API_VERSION = 6  # bump when export pipeline changes (6 = resolution + quality params)
DEFAULT_OUTPUT = ROOT / "final_video.mp4"
CLIP_CACHE_DIR = ROOT / ".broll_cache"
SEGMENT_CACHE_DIR = ROOT / ".export_cache" / "segments"
FPS = 30

RESOLUTION_MAP: dict[str, tuple[int, int]] = {
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
}
DEFAULT_RESOLUTION = "4k"

# Quality presets: CRF sets the quality floor; maxrate caps the bitrate ceiling
# so file sizes are predictable even for very long videos.
# Approximate file sizes for a 2-hour video at each preset:
#   high       ~8M  maxrate  →  ~7.2 GB
#   balanced   ~4M  maxrate  →  ~3.6 GB
#   compressed ~2.5M maxrate →  ~2.2 GB  (matches CapCut 2500kbps VBR)
QUALITY_PRESETS: dict[str, dict[str, str | int]] = {
    "high":       {"crf": 18, "maxrate": "8M",    "bufsize": "16M"},
    "balanced":   {"crf": 22, "maxrate": "4M",    "bufsize": "8M"},
    "compressed": {"crf": 26, "maxrate": "2500k", "bufsize": "5M"},
}
DEFAULT_QUALITY = "balanced"

# Legacy constants kept for any direct callers.
WIDTH, HEIGHT = RESOLUTION_MAP[DEFAULT_RESOLUTION]
NARRATION_TARGET_DB = -16.0
BACKGROUND_UNDER_NARRATION_DB = 22.0
MAX_MIX_ADJUST_DB = 12.0

ProgressCallback = Callable[[str, int, int, str], None]
CancelCheck = Callable[[], bool]

_active_ffmpeg_lock = threading.Lock()
_active_ffmpeg_procs: dict[str, subprocess.Popen[str]] = {}
_export_context = threading.local()


def set_export_context(project_id: str | None) -> None:
    _export_context.project_id = project_id


def _current_export_project_id() -> str | None:
    return getattr(_export_context, "project_id", None)


class ExportCancelled(Exception):
    """Raised when an export is cancelled by the user."""


def request_export_cancel(project_id: str | None = None) -> None:
    pid = project_id or _current_export_project_id()
    if not pid:
        return
    with _active_ffmpeg_lock:
        proc = _active_ffmpeg_procs.get(pid)
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def _check_cancel(should_cancel: CancelCheck | None) -> None:
    if should_cancel and should_cancel():
        request_export_cancel()
        raise ExportCancelled("Export cancelled")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Billions final video.")
    parser.add_argument("audio", help="Narration MP3/WAV path.")
    parser.add_argument("timestamps", help="segment_timestamps.json path.")
    parser.add_argument("selections", help="broll_selections.json path.")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT), help="Output MP4 path.")
    parser.add_argument(
        "--encoder",
        default="auto",
        help="ffmpeg video encoder (auto, h264_nvenc, h264_amf, h264_qsv, libx264).",
    )
    return parser.parse_args()


def run_ffmpeg(args: list[str], quiet: bool = True, should_cancel: CancelCheck | None = None) -> None:
    project_id = _current_export_project_id()
    command = ["ffmpeg", "-hide_banner", "-y", *args]
    _check_cancel(should_cancel)
    proc = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
        text=quiet,
    )
    if project_id:
        with _active_ffmpeg_lock:
            _active_ffmpeg_procs[project_id] = proc
    try:
        stdout, stderr = proc.communicate()
        if should_cancel and should_cancel():
            raise ExportCancelled("Export cancelled")
        if proc.returncode != 0:
            err = (stderr or "").strip()
            raise RuntimeError(err or "ffmpeg failed")
        _ = stdout
    finally:
        if project_id:
            with _active_ffmpeg_lock:
                if _active_ffmpeg_procs.get(project_id) is proc:
                    _active_ffmpeg_procs.pop(project_id, None)


def detect_encoder(
    preferred: str = "auto",
    crf: int = 22,
    maxrate: str = "4M",
    bufsize: str = "8M",
) -> tuple[str, list[str]]:
    if preferred != "auto":
        return preferred, encoder_args(preferred, crf, maxrate, bufsize)

    encoders = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    for name in ("h264_nvenc", "h264_amf", "h264_qsv"):
        if name in encoders:
            print(f"Using GPU encoder: {name}")
            return name, encoder_args(name, crf, maxrate, bufsize)

    print("No GPU encoder found, falling back to libx264")
    return "libx264", encoder_args("libx264", crf, maxrate, bufsize)


def encoder_args(
    encoder: str,
    crf: int = 22,
    maxrate: str = "4M",
    bufsize: str = "8M",
) -> list[str]:
    if encoder == "h264_nvenc":
        return [
            "-c:v", "h264_nvenc", "-preset", "p4",
            "-rc", "vbr", "-cq", str(crf), "-b:v", "0",
            "-maxrate", maxrate, "-bufsize", bufsize,
        ]
    if encoder == "h264_amf":
        return [
            "-c:v", "h264_amf", "-quality", "balanced",
            "-rc", "vbr_peak", "-qp_i", str(crf), "-qp_p", str(crf),
            "-maxrate", maxrate,
        ]
    if encoder == "h264_qsv":
        return [
            "-c:v", "h264_qsv", "-preset", "medium",
            "-global_quality", str(crf), "-maxrate", maxrate,
        ]
    # libx264: use -crf for quality floor + -maxrate to cap ceiling
    return [
        "-c:v", "libx264", "-preset", "fast",
        "-crf", str(crf), "-maxrate", maxrate, "-bufsize", bufsize,
    ]


# Cached result of the one-time GPU-filter capability probe.
_gpu_scale_support: bool | None = None


def _ffmpeg_capability(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["ffmpeg", "-hide_banner", *args],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return ""


def gpu_scale_available(encoder_name: str) -> bool:
    """Detect whether the full NVDEC -> scale_cuda -> NVENC path is usable.

    Result is cached for the process. Falls back to False on any doubt so the
    CPU scaler is used instead (slower but always correct).
    """
    global _gpu_scale_support
    if _gpu_scale_support is not None:
        return _gpu_scale_support

    if encoder_name != "h264_nvenc":
        _gpu_scale_support = False
        return False

    hwaccels = _ffmpeg_capability(["-hwaccels"])
    filters = _ffmpeg_capability(["-filters"])
    if "cuda" not in hwaccels or "scale_cuda" not in filters:
        print("[export] GPU scaling unavailable (no cuda hwaccel / scale_cuda); using CPU scaler.")
        _gpu_scale_support = False
        return False

    # Functional probe: upload a tiny frame to CUDA, scale it, download, encode.
    # Mirrors the production filter graph so a build that lists but can't run
    # scale_cuda still falls back cleanly.
    probe = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y",
            "-init_hw_device", "cuda=cu:0", "-filter_hw_device", "cu",
            "-f", "lavfi", "-i", "color=c=black:s=640x360:r=5",
            "-t", "0.2",
            "-vf",
            "format=nv12,hwupload_cuda,"
            "scale_cuda=1280:720:force_original_aspect_ratio=increase,"
            "hwdownload,format=nv12,crop=1280:720",
            "-c:v", "h264_nvenc", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    _gpu_scale_support = probe.returncode == 0
    if _gpu_scale_support:
        print("[export] GPU scaling enabled (NVDEC + scale_cuda + NVENC).")
    else:
        print("[export] GPU scaling probe failed; using CPU scaler.")
    return _gpu_scale_support


def load_segments(timestamps_path: Path, selections_path: Path) -> list[dict[str, Any]]:
    timestamps = json.loads(timestamps_path.read_text(encoding="utf-8"))
    selections = json.loads(selections_path.read_text(encoding="utf-8")).get("segments", {})

    rows: list[dict[str, Any]] = []
    for entry in timestamps.get("segments", []):
        segment_id = entry.get("segment_id")
        timing = entry.get("timing", {})
        duration = timing.get("duration_seconds")
        if segment_id is None or duration is None or duration <= 0:
            continue

        selection = selections.get(str(segment_id))
        rows.append(
            {
                "segment_id": segment_id,
                "duration": float(duration),
                "selection": selection,
            }
        )

    rows.sort(key=lambda item: item["segment_id"])
    return rows


def download_clip(url: str, dest: Path, *, retries: int = 3) -> None:
    # Already cached from a previous run / prefetch pass.
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Stream to a .part temp file and only rename into place on success. This
    # keeps memory flat (no whole-file read) and guarantees a half-finished
    # download on a flaky/slow link can never be mistaken for a valid cache hit.
    request = urllib.request.Request(url, headers={"User-Agent": "Billions-Export/1.0"})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                with open(tmp, "wb") as handle:
                    shutil.copyfileobj(response, handle, length=1024 * 1024)
            if tmp.stat().st_size == 0:
                raise RuntimeError("downloaded file was empty")
            tmp.replace(dest)
            return
        except Exception as exc:  # noqa: BLE001 - retried below, re-raised if final
            last_error = exc
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Failed to download clip after {retries} attempts: {last_error}")


def prefetch_clips(
    segments: list[dict[str, Any]],
    cache_dir: Path | None,
    *,
    should_cancel: CancelCheck | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Download all source clips concurrently before encoding starts.

    Network transfers overlap with each other (and are off the GPU critical
    path) so the encoder never stalls waiting on a download mid-render.
    """
    clip_cache_dir = (cache_dir / "clips") if cache_dir else CLIP_CACHE_DIR
    clip_cache_dir.mkdir(parents=True, exist_ok=True)

    jobs: dict[str | int, tuple[str, Path]] = {}
    for segment in segments:
        selection = segment.get("selection")
        if not selection or not selection.get("url"):
            continue
        video_id = selection_cache_id(selection)
        dest = clip_cache_dir / f"{video_id}.mp4"
        if dest.exists() and dest.stat().st_size > 0:
            continue
        jobs.setdefault(video_id, (clip_source_url(selection), dest))

    if not jobs:
        return

    total = len(jobs)
    done = 0
    if on_progress:
        on_progress("download", 0, total, f"Downloading {total} clip(s)…")

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(download_clip, url, dest): video_id
            for video_id, (url, dest) in jobs.items()
        }
        try:
            for future in as_completed(futures):
                if should_cancel and should_cancel():
                    raise ExportCancelled("Export cancelled")
                future.result()
                done += 1
                if on_progress:
                    on_progress("download", done, total, f"Downloaded {done}/{total} clip(s)")
        finally:
            if should_cancel and should_cancel():
                for future in futures:
                    future.cancel()


def clip_source_url(selection: dict[str, Any]) -> str:
    provider = str(selection.get("provider") or "").strip().lower()
    storage_key = str(selection.get("storage_key") or "").strip()
    if provider == "storage" and storage_key:
        base = os.environ.get("BROLL_MEDIA_BASE_URL", "http://127.0.0.1:3001").rstrip("/")
        return f"{base}/api/storage/media?key={urllib.parse.quote(storage_key, safe='')}"

    url = str(selection.get("url") or "").strip()
    if url.startswith("/"):
        base = os.environ.get("BROLL_MEDIA_BASE_URL", "http://127.0.0.1:3001").rstrip("/")
        return f"{base}{url}"
    return url


def selection_cache_id(selection: dict[str, Any] | None) -> str | int:
    if not selection:
        return "black"
    video_id = selection.get("video_id")
    if video_id is not None:
        return video_id
    storage_key = selection.get("storage_key")
    if storage_key:
        return f"storage_{storage_key}"
    return "black"


def scale_filter(width: int = WIDTH, height: int = HEIGHT, fps: int = FPS) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps}"
    )


def gpu_scale_filter(width: int = WIDTH, height: int = HEIGHT, fps: int = FPS) -> str:
    # Heavy resample runs on the GPU (scale_cuda); only the cheap crop/fps
    # happens on the CPU after a single hwdownload. NVENC re-uploads to encode.
    return (
        f"scale_cuda={width}:{height}:force_original_aspect_ratio=increase,"
        f"hwdownload,format=nv12,crop={width}:{height},fps={fps}"
    )


def _escape_drawtext_value(text: str) -> str:
    # Escape drawtext special chars so credit labels render reliably.
    return (
        text.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("%", r"\%")
    )


def build_credit_filter(selection: dict[str, Any] | None) -> str | None:
    if not selection:
        return None

    provider = str(selection.get("provider") or "").strip().lower()
    photographer = str(selection.get("photographer") or "").strip()
    if provider not in {"pexels", "pixabay"}:
        return None
    if not photographer:
        return None

    credit = f"Via {photographer}"

    escaped = _escape_drawtext_value(credit)
    return (
        "drawtext="
        f"text='{escaped}':"
        "x=w-tw-18:y=h-th-12:"
        "fontsize=16:"
        "fontcolor=white@0.50:"
        "box=0"
    )


def clear_export_work_cache(cache_dir: Path, output_path: Path | None = None) -> None:
    """Remove encoded segment cache and intermediate export artifacts."""
    segments_dir = cache_dir / "segments"
    if segments_dir.exists():
        shutil.rmtree(segments_dir)
    for name in ("video_only.mp4", "concat_list.txt"):
        path = cache_dir / name
        if path.exists():
            path.unlink()
    if output_path and output_path.exists():
        output_path.unlink()


def render_segment_clip(
    segment_id: int,
    duration: float,
    selection: dict[str, Any] | None,
    encoder: str,
    enc_args: list[str],
    cache_dir: Path | None = None,
    *,
    out_width: int = WIDTH,
    out_height: int = HEIGHT,
    force: bool = False,
    should_cancel: CancelCheck | None = None,
) -> Path:
    clip_cache_dir = (cache_dir / "clips") if cache_dir else CLIP_CACHE_DIR
    segment_cache_dir = (cache_dir / "segments") if cache_dir else SEGMENT_CACHE_DIR
    segment_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_id = selection_cache_id(selection)
    res_tag = f"{out_width}x{out_height}"
    out_path = segment_cache_dir / f"segment_{segment_id:03d}_{cache_id}_{res_tag}.mp4"
    if not force and out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    duration_str = f"{duration:.3f}"

    if selection and selection.get("url"):
        video_id = selection_cache_id(selection)
        source_path = clip_cache_dir / f"{video_id}.mp4"
        download_clip(clip_source_url(selection), source_path)

        use_gpu = gpu_scale_available(encoder)
        credit_filter = build_credit_filter(selection)

        if use_gpu:
            vf_parts = [gpu_scale_filter(out_width, out_height)]
            if credit_filter:
                # drawtext needs planar frames in system memory.
                vf_parts.append("format=yuv420p")
                vf_parts.append(credit_filter)
            input_args = [
                "-hwaccel", "cuda",
                "-hwaccel_output_format", "cuda",
                "-stream_loop", "-1",
                "-i", str(source_path),
            ]
        else:
            vf_parts = [scale_filter(out_width, out_height)]
            if credit_filter:
                vf_parts.append(credit_filter)
            input_args = [
                "-stream_loop", "-1",
                "-i", str(source_path),
            ]

        try:
            run_ffmpeg(
                [
                    *input_args,
                    "-t",
                    duration_str,
                    "-vf",
                    ",".join(vf_parts),
                    "-an",
                    *enc_args,
                    "-pix_fmt",
                    "yuv420p",
                    str(out_path),
                ],
                should_cancel=should_cancel,
            )
        except RuntimeError:
            # GPU graph failed at runtime — disable it and retry on the CPU path
            # once so a single bad clip doesn't abort the whole export.
            if not use_gpu:
                raise
            global _gpu_scale_support
            _gpu_scale_support = False
            print("[export] GPU render failed for a clip; falling back to CPU scaler.")
            cpu_vf = [scale_filter(out_width, out_height)]
            if credit_filter:
                cpu_vf.append(credit_filter)
            run_ffmpeg(
                [
                    "-stream_loop", "-1",
                    "-i", str(source_path),
                    "-t", duration_str,
                    "-vf", ",".join(cpu_vf),
                    "-an",
                    *enc_args,
                    "-pix_fmt", "yuv420p",
                    str(out_path),
                ],
                should_cancel=should_cancel,
            )
        return out_path

    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={out_width}x{out_height}:r={FPS}",
            "-t",
            duration_str,
            *enc_args,
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ],
        should_cancel=should_cancel,
    )
    return out_path


def concat_segments(
    segment_files: list[Path],
    output_path: Path,
    *,
    should_cancel: CancelCheck | None = None,
) -> None:
    list_path = output_path.parent / "concat_list.txt"
    lines = [f"file '{path.resolve().as_posix()}'" for path in segment_files]
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output_path),
        ],
        should_cancel=should_cancel,
    )


def mux_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    enc_args: list[str],
    *,
    should_cancel: CancelCheck | None = None,
) -> None:
    # Segments are already GPU/CPU encoded — copy the video stream to avoid a second
    # full-length re-encode (very slow and can OOM on long exports).
    _ = enc_args
    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ],
        should_cancel=should_cancel,
    )


def _format_srt_timestamp(total_seconds: float) -> str:
    millis = max(0, int(round(total_seconds * 1000)))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def _sentence_chunks(text: str) -> list[str]:
    cleaned = " ".join(str(text or "").strip().split())
    if not cleaned:
        return []
    chunks = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    if not chunks:
        return [cleaned]
    split_chunks: list[str] = []
    for chunk in chunks:
        words = chunk.split()
        if len(words) <= 12:
            split_chunks.append(chunk)
            continue
        for index in range(0, len(words), 12):
            split_chunks.append(" ".join(words[index : index + 12]))
    return split_chunks


def write_refined_subtitles_srt(timestamps_path: Path, output_path: Path) -> int:
    timestamps = json.loads(timestamps_path.read_text(encoding="utf-8"))
    segments = timestamps.get("segments", [])
    cues: list[tuple[float, float, str]] = []

    for segment in segments:
        timing = segment.get("timing") or {}
        start = timing.get("start_seconds")
        end = timing.get("end_seconds")
        if start is None or end is None:
            duration = timing.get("duration_seconds")
            if start is not None and duration:
                end = float(start) + float(duration)
            else:
                continue
        start_f = float(start)
        end_f = float(end)
        if end_f <= start_f:
            continue

        text = str(segment.get("content") or "").strip()
        chunks = _sentence_chunks(text)
        if not chunks:
            continue
        total_words = max(1, sum(max(1, len(chunk.split())) for chunk in chunks))
        seg_duration = end_f - start_f
        cursor = start_f

        for idx, chunk in enumerate(chunks):
            words = max(1, len(chunk.split()))
            if idx == len(chunks) - 1:
                cue_end = end_f
            else:
                portion = seg_duration * (words / total_words)
                cue_end = min(end_f, cursor + max(0.7, portion))
            cues.append((cursor, cue_end, chunk))
            cursor = cue_end

    if not cues:
        output_path.write_text("", encoding="utf-8")
        return 0

    normalized: list[tuple[float, float, str]] = []
    last_end = 0.0
    for start, end, text in cues:
        start = max(last_end, start)
        min_end = start + 0.6
        end = max(min_end, end)
        normalized.append((start, end, text))
        last_end = end

    lines: list[str] = []
    for idx, (start, end, text) in enumerate(normalized, start=1):
        lines.extend(
            [
                str(idx),
                f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}",
                text,
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return len(normalized)


def _escape_subtitles_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def mux_audio_with_subtitles(
    video_path: Path,
    audio_path: Path,
    subtitles_path: Path,
    output_path: Path,
    enc_args: list[str],
    *,
    should_cancel: CancelCheck | None = None,
) -> None:
    subtitle_filter = (
        f"subtitles=filename='{_escape_subtitles_path(subtitles_path)}':"
        "force_style='FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,MarginV=36'"
    )
    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-vf",
            subtitle_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            *enc_args,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ],
        should_cancel=should_cancel,
    )


def add_faststart(input_path: Path, *, should_cancel: CancelCheck | None = None) -> None:
    """Move moov atom to file start for web playback (optional second pass)."""
    if not input_path.exists() or input_path.stat().st_size < 500 * 1024 * 1024:
        run_ffmpeg(
            [
                "-i",
                str(input_path),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(input_path.with_suffix(".faststart.mp4")),
            ],
            should_cancel=should_cancel,
        )
        temp = input_path.with_suffix(".faststart.mp4")
        temp.replace(input_path)


def probe_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def probe_decoded_duration(audio_path: Path) -> float:
    """How much audio ffmpeg can actually decode (handles lying MP3 headers)."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(audio_path),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stderr or "") + (result.stdout or "")
    matches = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    if not matches:
        raise RuntimeError(f"Could not decode audio duration for {audio_path.name}")
    hours, minutes, seconds = matches[-1]
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def validate_narration_audio(
    audio_path: Path,
    *,
    min_expected_seconds: float | None = None,
) -> float:
    """Ensure narration is fully decodable; raise if metadata oversells the file."""
    tagged = probe_duration(audio_path)
    decoded = probe_decoded_duration(audio_path)
    if decoded < 5:
        raise RuntimeError(
            f"Narration audio {audio_path.name} has no usable audio. Re-upload the MP3."
        )
    if tagged - decoded > 30:
        raise RuntimeError(
            f"Narration audio {audio_path.name} looks incomplete: the file reports "
            f"{tagged / 60:.1f} min but ffmpeg only decodes {decoded / 60:.1f} min. "
            "Re-upload the full narration MP3, then re-run segment timestamps and export."
        )
    if min_expected_seconds is not None and decoded + 30 < min_expected_seconds:
        raise RuntimeError(
            f"Narration audio is only {decoded / 60:.1f} min long, but the timeline needs "
            f"about {min_expected_seconds / 60:.1f} min. Re-upload the full MP3 and re-run "
            "segment timestamps before exporting."
        )
    return decoded


def probe_mean_volume(audio_path: Path, max_probe_seconds: float | None = 120.0) -> float:
    command = ["ffmpeg", "-hide_banner"]
    if max_probe_seconds:
        command.extend(["-t", f"{max_probe_seconds:.3f}"])
    command.extend(["-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = (result.stderr or "") + (result.stdout or "")
    match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", output)
    if not match:
        raise RuntimeError(f"Could not measure loudness for {audio_path.name}")
    return float(match.group(1))


def clamp_mix_adjust_db(value: float) -> float:
    return max(-MAX_MIX_ADJUST_DB, min(MAX_MIX_ADJUST_DB, float(value)))


def compute_solo_narration_gains(narration_path: Path) -> dict[str, float]:
    narration_mean_db = probe_mean_volume(narration_path)
    narration_gain_db = NARRATION_TARGET_DB - narration_mean_db
    return {
        "narration_mean_db": round(narration_mean_db, 2),
        "background_mean_db": 0.0,
        "narration_gain_db": round(narration_gain_db, 2),
        "background_gain_db": 0.0,
        "background_under_narration_db": BACKGROUND_UNDER_NARRATION_DB,
    }


def apply_mix_adjustments(
    gains: dict[str, float],
    *,
    narration_adjust_db: float = 0.0,
    background_adjust_db: float = 0.0,
) -> dict[str, float]:
    narr_adj = clamp_mix_adjust_db(narration_adjust_db)
    bg_adj = clamp_mix_adjust_db(background_adjust_db)
    adjusted = dict(gains)
    adjusted["narration_gain_db"] = round(gains["narration_gain_db"] + narr_adj, 2)
    adjusted["background_gain_db"] = round(gains["background_gain_db"] + bg_adj, 2)
    adjusted["narration_adjust_db"] = narr_adj
    adjusted["background_adjust_db"] = bg_adj
    return adjusted


def compute_mix_gains(
    narration_path: Path,
    background_path: Path,
) -> dict[str, float]:
    narration_mean_db = probe_mean_volume(narration_path)
    background_mean_db = probe_mean_volume(background_path)
    narration_gain_db = NARRATION_TARGET_DB - narration_mean_db
    background_gain_db = (
        NARRATION_TARGET_DB - BACKGROUND_UNDER_NARRATION_DB
    ) - background_mean_db
    return {
        "narration_mean_db": round(narration_mean_db, 2),
        "background_mean_db": round(background_mean_db, 2),
        "narration_gain_db": round(narration_gain_db, 2),
        "background_gain_db": round(background_gain_db, 2),
        "background_under_narration_db": BACKGROUND_UNDER_NARRATION_DB,
    }


def build_mixed_audio(
    narration_path: Path,
    background_path: Path,
    output_path: Path,
    *,
    gains: dict[str, float] | None = None,
    preview_seconds: float | None = None,
    should_cancel: CancelCheck | None = None,
) -> dict[str, float]:
    if gains is None:
        gains = compute_mix_gains(narration_path, background_path)

    duration = validate_narration_audio(narration_path)
    if preview_seconds is not None:
        duration = min(duration, preview_seconds)
    duration_str = f"{duration:.3f}"
    narration_gain_db = gains["narration_gain_db"]
    background_gain_db = gains["background_gain_db"]

    # Loop the background track at the demuxer level (-stream_loop) instead of
    # buffering it in memory with aloop. aloop=size=2e9 tries to hold billions
    # of samples in RAM and fails ("Error while filtering: Invalid argument")
    # on long exports; -stream_loop streams the loop with flat memory use.
    filter_complex = (
        f"[0:a]volume={narration_gain_db}dB,atrim=0:{duration_str}[narr];"
        f"[1:a]volume={background_gain_db}dB[bg];"
        f"[narr][bg]amix=inputs=2:duration=first:dropout_transition=0[a]"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(narration_path),
            "-stream_loop",
            "-1",
            "-i",
            str(background_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[a]",
            "-t",
            duration_str,
            "-f",
            "ipod",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ],
        should_cancel=should_cancel,
    )
    return gains


def render_narration_audio(
    narration_path: Path,
    output_path: Path,
    gain_db: float,
    *,
    preview_seconds: float | None = None,
    should_cancel: CancelCheck | None = None,
) -> None:
    duration = probe_decoded_duration(narration_path)
    if preview_seconds is not None:
        duration = min(duration, preview_seconds)
    duration_str = f"{duration:.3f}"
    filter_complex = f"[0:a]volume={gain_db}dB,atrim=0:{duration_str}[a]"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(narration_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[a]",
            "-f",
            "ipod",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ],
        should_cancel=should_cancel,
    )


def summarize_export_error(exc: Exception, max_len: int = 200) -> str:
    text = str(exc).strip()
    if not text:
        return "Export failed"
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # "Conversion failed!" / "ffmpeg failed" are generic trailers — the useful
    # cause is usually a line above them. Prefer a specific error line and only
    # fall back to the generic trailer when nothing better is found.
    generic = {"conversion failed!", "conversion failed", "ffmpeg failed"}
    tokens = (
        "error", "failed", "cannot", "not found", "invalid argument",
        "no space", "out of memory", "permission denied", "killed",
    )
    candidates = [
        line for line in reversed(lines)
        if any(token in line.lower() for token in tokens)
    ]
    for line in candidates:
        if line.lower().rstrip(".!") not in generic:
            return line[:max_len]
    if candidates:
        return candidates[0][:max_len]
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def sanitize_output_name(title: str | None) -> str:
    if not title:
        return "final_video.mp4"
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return f"{slug[:80] or 'final_video'}.mp4"


def export_video(
    audio_path: Path,
    timestamps_path: Path,
    selections_path: Path,
    output_path: Path,
    encoder: str = "auto",
    on_progress: ProgressCallback | None = None,
    cache_dir: Path | None = None,
    *,
    fresh: bool = False,
    should_cancel: CancelCheck | None = None,
    background_audio_path: Path | None = None,
    narration_adjust_db: float = 0.0,
    background_adjust_db: float = 0.0,
    resolution: str = DEFAULT_RESOLUTION,
    quality: str = DEFAULT_QUALITY,
    include_subtitles: bool = False,
) -> dict[str, Any]:
    def progress(stage: str, current: int, total: int, message: str) -> None:
        if on_progress:
            on_progress(stage, current, total, message)
        else:
            print(f"[{stage}] {current}/{total} {message}")

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not on PATH")

    _check_cancel(should_cancel)

    segments = load_segments(timestamps_path, selections_path)
    if not segments:
        raise RuntimeError("No timed segments found in timestamps file")

    timeline_seconds = sum(segment["duration"] for segment in segments)
    validate_narration_audio(
        audio_path,
        min_expected_seconds=timeline_seconds,
    )

    res_key = resolution.lower().replace(" ", "")
    out_width, out_height = RESOLUTION_MAP.get(res_key, RESOLUTION_MAP[DEFAULT_RESOLUTION])
    preset = QUALITY_PRESETS.get(quality.lower(), QUALITY_PRESETS[DEFAULT_QUALITY])
    crf = int(preset["crf"])
    maxrate = str(preset["maxrate"])
    bufsize = str(preset["bufsize"])
    print(f"Export settings: {out_width}x{out_height} @ CRF {crf}, maxrate {maxrate} ({quality})")

    encoder_name, enc_args = detect_encoder(encoder, crf=crf, maxrate=maxrate, bufsize=bufsize)
    work_dir = cache_dir if cache_dir else ROOT / ".export_cache"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Pull every source clip down up front, concurrently, so GPU encoding
    # never blocks on a network download between segments. Done before the
    # cache clear so the download phase is timed on its own (stage "download").
    prefetch_clips(segments, cache_dir, should_cancel=should_cancel, on_progress=on_progress)
    _check_cancel(should_cancel)

    if fresh:
        progress("prepare", 0, 1, "Clearing export cache…")
        clear_export_work_cache(work_dir, output_path)
        _check_cancel(should_cancel)

    progress("prepare", 0, len(segments), "Starting segment render…")
    segment_files: list[Path] = []
    missing = 0

    for index, segment in enumerate(segments, start=1):
        _check_cancel(should_cancel)
        selection = segment["selection"]
        if not selection:
            missing += 1
        progress(
            "prepare",
            index,
            len(segments),
            f"Segment {segment['segment_id']} ({segment['duration']:.1f}s)",
        )
        segment_files.append(
            render_segment_clip(
                segment_id=segment["segment_id"],
                duration=segment["duration"],
                selection=selection,
                encoder=encoder_name,
                enc_args=enc_args,
                cache_dir=cache_dir,
                out_width=out_width,
                out_height=out_height,
                force=fresh,
                should_cancel=should_cancel,
            )
        )

    video_only = work_dir / "video_only.mp4"
    _check_cancel(should_cancel)
    progress("concat", 0, 1, "Concatenating segments…")
    concat_segments(segment_files, video_only, should_cancel=should_cancel)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _check_cancel(should_cancel)

    mux_audio_path = audio_path
    mix_gains: dict[str, float] | None = None
    narr_adj = clamp_mix_adjust_db(narration_adjust_db)
    bg_adj = clamp_mix_adjust_db(background_adjust_db)

    if background_audio_path:
        if not background_audio_path.exists():
            raise FileNotFoundError(f"Background audio not found: {background_audio_path}")
        progress("audio", 0, 1, "Balancing narration and background audio…")
        mixed_audio_path = work_dir / "mixed_audio.m4a"
        base_gains = compute_mix_gains(audio_path, background_audio_path)
        mix_gains = apply_mix_adjustments(
            base_gains,
            narration_adjust_db=narr_adj,
            background_adjust_db=bg_adj,
        )
        build_mixed_audio(
            narration_path=audio_path,
            background_path=background_audio_path,
            output_path=mixed_audio_path,
            gains=mix_gains,
            should_cancel=should_cancel,
        )
        mux_audio_path = mixed_audio_path
        progress("audio", 1, 1, "Background audio mixed")
    elif abs(narr_adj) > 0.01:
        progress("audio", 0, 1, "Adjusting narration level…")
        base_gains = compute_solo_narration_gains(audio_path)
        mix_gains = apply_mix_adjustments(
            base_gains,
            narration_adjust_db=narr_adj,
            background_adjust_db=0.0,
        )
        adjusted_narration_path = work_dir / "narration_adjusted.m4a"
        render_narration_audio(
            audio_path,
            adjusted_narration_path,
            mix_gains["narration_gain_db"],
            should_cancel=should_cancel,
        )
        mux_audio_path = adjusted_narration_path
        progress("audio", 1, 1, "Narration level adjusted")
    else:
        base_gains = compute_solo_narration_gains(audio_path)
        mix_gains = apply_mix_adjustments(
            base_gains,
            narration_adjust_db=0.0,
            background_adjust_db=0.0,
        )
        if abs(mix_gains["narration_gain_db"]) > 0.01:
            progress("audio", 0, 1, "Normalizing narration level…")
            adjusted_narration_path = work_dir / "narration_adjusted.m4a"
            render_narration_audio(
                audio_path,
                adjusted_narration_path,
                mix_gains["narration_gain_db"],
                should_cancel=should_cancel,
            )
        mux_audio_path = adjusted_narration_path
        progress("audio", 1, 1, "Narration normalized")

    video_duration = probe_duration(video_only)
    audio_duration = probe_decoded_duration(mux_audio_path)
    if audio_duration + 5 < video_duration:
        raise RuntimeError(
            f"Final audio is only {audio_duration / 60:.1f} min but rendered video is "
            f"{video_duration / 60:.1f} min. The narration MP3 is likely incomplete — "
            "re-upload the full file, re-run segment timestamps, and export again."
        )

    subtitles_count = 0
    subtitles_path = work_dir / "captions.srt"
    if include_subtitles:
        progress("encode", 0, 2, "Generating subtitles from Whisper timing…")
        subtitles_count = write_refined_subtitles_srt(timestamps_path, subtitles_path)

    if include_subtitles and subtitles_count > 0:
        progress("encode", 1, 2, f"Burning {subtitles_count} subtitle cues…")
        mux_audio_with_subtitles(
            video_only,
            mux_audio_path,
            subtitles_path,
            output_path,
            enc_args,
            should_cancel=should_cancel,
        )
    else:
        progress("encode", 0, 1, f"Muxing audio with {encoder_name}…")
        mux_audio(video_only, mux_audio_path, output_path, enc_args, should_cancel=should_cancel)
    if output_path.exists() and output_path.stat().st_size < 500 * 1024 * 1024:
        progress("encode", 1, 1, "Optimizing for download…")
        add_faststart(output_path, should_cancel=should_cancel)

    return {
        "output": str(output_path.resolve()),
        "encoder": encoder_name,
        "segments": len(segments),
        "missing_broll": missing,
        "background_audio": str(background_audio_path.resolve()) if background_audio_path else None,
        "audio_mix": mix_gains,
        "subtitles_burned": bool(include_subtitles and subtitles_count > 0),
        "subtitles_count": subtitles_count,
    }


def main() -> None:
    args = parse_args()
    timestamps_path = Path(args.timestamps)
    title = None
    if timestamps_path.exists():
        title = json.loads(timestamps_path.read_text(encoding="utf-8")).get("title")

    output_path = Path(args.output)
    if str(output_path) == str(DEFAULT_OUTPUT) and title:
        output_path = ROOT / sanitize_output_name(title)

    result = export_video(
        audio_path=Path(args.audio),
        timestamps_path=timestamps_path,
        selections_path=Path(args.selections),
        output_path=output_path,
        encoder=args.encoder,
    )
    print(
        f"Exported {result['output']} "
        f"({result['segments']} segments, {result['missing_broll']} missing b-roll, {result['encoder']})"
    )


if __name__ == "__main__":
    main()
