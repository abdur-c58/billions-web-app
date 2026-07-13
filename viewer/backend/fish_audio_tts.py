"""Fish Audio text-to-speech for project narration generation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

FISH_TTS_URL = "https://api.fish.audio/v1/tts"
DEFAULT_WPM = 145
DEFAULT_MODEL = "s2.1-pro-free"
DEFAULT_MAX_CHARS_PER_CHUNK = 2500


@dataclass(frozen=True)
class FishTtsConfig:
    api_key: str
    voice_id: str
    model: str
    temperature: float
    top_p: float
    speed: float
    volume: float
    mp3_bitrate: int
    latency: str
    chunk_length: int
    normalize_loudness: bool
    auto_delay_seconds: int


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def load_fish_config() -> FishTtsConfig:
    api_key = os.environ.get("FISH_API_KEY", "").strip()
    voice_id = os.environ.get("FISH_VOICE_ID", "").strip()
    return FishTtsConfig(
        api_key=api_key,
        voice_id=voice_id,
        model=os.environ.get("FISH_TTS_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        temperature=_env_float("FISH_TTS_TEMPERATURE", 0.7),
        top_p=_env_float("FISH_TTS_TOP_P", 0.7),
        speed=_env_float("FISH_TTS_SPEED", 1.0),
        volume=_env_float("FISH_TTS_VOLUME", 0.0),
        mp3_bitrate=_env_int("FISH_TTS_MP3_BITRATE", 128),
        latency=os.environ.get("FISH_TTS_LATENCY", "normal").strip() or "normal",
        chunk_length=_env_int("FISH_TTS_CHUNK_LENGTH", 300),
        normalize_loudness=os.environ.get("FISH_TTS_NORMALIZE_LOUDNESS", "1").strip().lower()
        not in {"0", "false", "no"},
        auto_delay_seconds=_env_int("FISH_TTS_AUTO_DELAY_SECONDS", 10),
    )


def validate_fish_config(config: FishTtsConfig | None = None) -> FishTtsConfig:
    config = config or load_fish_config()
    missing: list[str] = []
    if not config.api_key:
        missing.append("FISH_API_KEY")
    if not config.voice_id:
        missing.append("FISH_VOICE_ID")
    if missing:
        raise ValueError(
            f"Set {', '.join(missing)} in .env.local before generating narration."
        )
    return config


def estimate_duration_seconds(word_count: int, wpm: int = DEFAULT_WPM) -> float:
    if word_count <= 0:
        return 0.0
    return round((word_count / wpm) * 60.0, 1)


def format_duration_label(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"~{minutes} min" if secs < 30 else f"~{minutes}m {secs}s"
    return f"~{secs}s"


def build_transcript_preview(transcript: str, segment_count: int) -> dict[str, Any]:
    word_count = len(transcript.split())
    duration_seconds = estimate_duration_seconds(word_count)
    return {
        "transcript": transcript,
        "segment_count": segment_count,
        "word_count": word_count,
        "estimated_duration_seconds": duration_seconds,
        "estimated_duration_label": format_duration_label(duration_seconds),
        "wpm": DEFAULT_WPM,
    }


def split_transcript_for_tts(text: str, max_chars: int = DEFAULT_MAX_CHARS_PER_CHUNK) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            flush()
            for start in range(0, len(sentence), max_chars):
                part = sentence[start : start + max_chars].strip()
                if part:
                    chunks.append(part)
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            flush()
            current = sentence

    flush()
    return chunks or [text[:max_chars]]


def _build_tts_payload(text: str, config: FishTtsConfig) -> dict[str, Any]:
    return {
        "text": text,
        "reference_id": config.voice_id,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "prosody": {
            "speed": config.speed,
            "volume": config.volume,
            "normalize_loudness": config.normalize_loudness,
        },
        "chunk_length": config.chunk_length,
        "normalize": True,
        "format": "mp3",
        "mp3_bitrate": config.mp3_bitrate,
        "latency": config.latency,
        "condition_on_previous_chunks": True,
    }


def synthesize_chunk(text: str, config: FishTtsConfig) -> bytes:
    body = json.dumps(_build_tts_payload(text, config)).encode("utf-8")
    request = urllib.request.Request(
        FISH_TTS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "model": config.model,
            "User-Agent": "Billions-BrollViewer/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("message"):
                raise RuntimeError(f"Fish Audio API error {exc.code}: {payload['message']}") from exc
            if isinstance(payload, list) and payload:
                first = payload[0]
                if isinstance(first, dict) and first.get("msg"):
                    raise RuntimeError(
                        f"Fish Audio API error {exc.code}: {first['msg']}"
                    ) from exc
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"Fish Audio API error {exc.code}: {raw[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Fish Audio request failed: {exc.reason}") from exc


def concat_mp3_chunks(chunk_paths: list[Path], output_path: Path) -> None:
    if not chunk_paths:
        raise RuntimeError("No audio chunks to concatenate.")
    if len(chunk_paths) == 1:
        output_path.write_bytes(chunk_paths[0].read_bytes())
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
        dir=output_path.parent,
    ) as list_file:
        for chunk_path in chunk_paths:
            escaped = str(chunk_path.resolve()).replace("'", "'\\''")
            list_file.write(f"file '{escaped}'\n")
        list_path = Path(list_file.name)

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
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
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(stderr or "ffmpeg concat failed")
    finally:
        list_path.unlink(missing_ok=True)


def synthesize_transcript_to_file(
    transcript: str,
    output_path: Path,
    config: FishTtsConfig,
    *,
    on_progress: Callable[[int, str, str, int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> None:
    chunks = split_transcript_for_tts(transcript)
    if not chunks:
        raise RuntimeError("Transcript is empty.")

    total = len(chunks)
    temp_dir = output_path.parent / ".tts_chunks"
    temp_dir.mkdir(parents=True, exist_ok=True)

    chunk_paths: list[Path] = []
    try:
        for index, chunk_text in enumerate(chunks):
            if should_cancel and should_cancel():
                raise RuntimeError("Narration generation cancelled.")
            if on_progress:
                percent = 5 + int(((index) / total) * 80)
                on_progress(
                    percent,
                    f"Synthesizing chunk {index + 1}/{total}…",
                    "synthesize",
                    index,
                    total,
                )
            audio_bytes = synthesize_chunk(chunk_text, config)
            chunk_path = temp_dir / f"chunk_{index:04d}.mp3"
            chunk_path.write_bytes(audio_bytes)
            chunk_paths.append(chunk_path)
            if on_progress:
                percent = 5 + int(((index + 1) / total) * 80)
                on_progress(
                    percent,
                    f"Finished chunk {index + 1}/{total}",
                    "synthesize",
                    index + 1,
                    total,
                )

        if should_cancel and should_cancel():
            raise RuntimeError("Narration generation cancelled.")

        if on_progress:
            on_progress(88, "Merging audio chunks…", "concat", total, total)

        concat_mp3_chunks(chunk_paths, output_path)

        if on_progress:
            on_progress(95, "Saving narration audio…", "save", total, total)
    finally:
        if temp_dir.exists():
            for path in temp_dir.glob("*.mp3"):
                path.unlink(missing_ok=True)
            try:
                temp_dir.rmdir()
            except OSError:
                pass