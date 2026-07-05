#!/usr/bin/env python3
"""Generate per-segment timestamps for Billions b-roll placement.

Aligns each script.json segment to real start/end times in a narration MP3
using Whisper word timestamps (same pipeline as Gem Insider — see instructions.md).

Usage:
    python segment_timestamps.py video
    python segment_timestamps.py video --model medium
    python segment_timestamps.py video --retry-failed
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

ProgressCallback = Callable[[int, str, str], None] | None
HardwareCallback = Callable[[dict[str, Any]], None] | None

DEFAULT_WPM = 145.0
DEFAULT_MIN_DURATION = 2.0
DEFAULT_GAP = 0.0
DEFAULT_WHISPER_MODEL = "medium"
WHISPER_MODELS = frozenset(
    {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "turbo"}
)


def normalize_whisper_model(model: str | None) -> str:
    name = str(model or DEFAULT_WHISPER_MODEL).strip().lower()
    if name not in WHISPER_MODELS:
        allowed = ", ".join(sorted(WHISPER_MODELS))
        raise ValueError(f"Unsupported Whisper model '{model}'. Choose from: {allowed}.")
    return name
DEFAULT_LOOKAHEAD = 8
DEFAULT_MATCH_WINDOW = 5
DEFAULT_MIN_WINDOW_MATCH_RATIO = 0.6
DEFAULT_MAX_CURSOR_JUMP = 80
CACHE_DIR = Path(".whisper_cache")
IGNORED_SUBDIRS = {".broll_cache", ".whisper_cache"}
ALLOWED_EXTRA_FILES = {
    "segment_timestamps.json",
    "broll_selections.json",
    ".broll_flagged.json",
    ".broll_export_status.json",
    ".timestamps_job.json",
    "project.json",
    "final_video.mp4",
}

CONTRACTIONS: dict[str, list[str]] = {
    "theres": ["there", "is"],
    "theyre": ["they", "are"],
    "youre": ["you", "are"],
    "were": ["we", "are"],
    "its": ["it", "is"],
    "thats": ["that", "is"],
    "whats": ["what", "is"],
    "heres": ["here", "is"],
    "dont": ["do", "not"],
    "doesnt": ["does", "not"],
    "didnt": ["did", "not"],
    "wont": ["will", "not"],
    "cant": ["can", "not"],
    "isnt": ["is", "not"],
    "arent": ["are", "not"],
    "wasnt": ["was", "not"],
    "werent": ["were", "not"],
    "hasnt": ["has", "not"],
    "havent": ["have", "not"],
    "hadnt": ["had", "not"],
    "wouldnt": ["would", "not"],
    "couldnt": ["could", "not"],
    "shouldnt": ["should", "not"],
    "im": ["i", "am"],
    "ive": ["i", "have"],
    "ill": ["i", "will"],
    "youll": ["you", "will"],
    "theyll": ["they", "will"],
    "well": ["we", "will"],
    "hed": ["he", "would"],
    "shed": ["she", "would"],
    "wed": ["we", "would"],
    "youd": ["you", "would"],
}

# Whisper often keeps apostrophe contractions as one token (e.g. "There's" -> theres).
WHISPER_COMBINED: dict[str, list[str]] = {
    key: value for key, value in CONTRACTIONS.items()
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Align Billions script segments to narration audio via Whisper."
        ),
        epilog=(
            "Examples:\n"
            "  python segment_timestamps.py video\n"
            "  python segment_timestamps.py video --model medium\n"
            "  python segment_timestamps.py video --retry-failed"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "folder",
        help="Folder containing exactly one .json file, one .mp3 file, and nothing else.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: <folder>/segment_timestamps.json).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_WHISPER_MODEL,
        help=f"Whisper model size. Default: {DEFAULT_WHISPER_MODEL}.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Fuzzy re-match only segments that failed in the existing output.",
    )
    parser.add_argument(
        "--retranscribe",
        action="store_true",
        help="Ignore cached Whisper output and transcribe again.",
    )
    parser.add_argument(
        "--lookahead",
        type=int,
        default=DEFAULT_LOOKAHEAD,
        help=f"Words to scan ahead during fuzzy retry. Default: {DEFAULT_LOOKAHEAD}.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent level for output files. Default: 2.",
    )
    return parser.parse_args()


def resolve_video_folder(folder: Path) -> tuple[Path, Path]:
    """Return the single JSON and MP3 in a folder, or exit if invalid."""
    if not folder.exists():
        raise SystemExit(f"Folder not found: {folder}")
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")

    subdirs = [
        path
        for path in folder.iterdir()
        if path.is_dir() and path.name not in IGNORED_SUBDIRS
    ]
    if subdirs:
        names = ", ".join(path.name for path in subdirs)
        raise SystemExit(
            f"Folder must contain only files, not subfolders. Found: {names}"
        )

    files = [path for path in folder.iterdir() if path.is_file()]
    json_files = [
        path
        for path in files
        if path.suffix.lower() == ".json" and path.name != "segment_timestamps.json"
    ]
    mp3_files = [path for path in files if path.suffix.lower() == ".mp3"]
    other_files = [
        path
        for path in files
        if path.name not in {*(p.name for p in json_files), *(p.name for p in mp3_files)}
        and path.name not in ALLOWED_EXTRA_FILES
    ]

    errors: list[str] = []
    if len(json_files) != 1:
        count = len(json_files)
        errors.append(f"expected exactly 1 .json file, found {count}")
    if len(mp3_files) != 1:
        count = len(mp3_files)
        errors.append(f"expected exactly 1 .mp3 file, found {count}")
    if other_files:
        names = ", ".join(path.name for path in other_files)
        errors.append(f"unexpected files: {names}")

    if errors:
        found = ", ".join(path.name for path in files) if files else "(empty)"
        detail = "; ".join(errors)
        raise SystemExit(
            f"Cannot run: folder '{folder}' is invalid ({detail}). "
            f"Found: {found}"
        )

    return json_files[0], mp3_files[0]


def count_words(text: str) -> int:
    return len(re.sub(r"[^a-z0-9 ]", "", text.lower()).split())


def normalize(text: str) -> list[str]:
    return [token for token in re.sub(r"[^a-z0-9 ]", "", text.lower()).split() if token]


def expand_tokens(tokens: list[str]) -> list[str]:
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(CONTRACTIONS.get(token, [token]))
    return expanded


def whisper_token(word_entry: dict[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]", "", word_entry["word"].lower())


SMALL_NUMBERS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

TENS_NUMBERS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

SCALE_NUMBERS: dict[str, int] = {
    "hundred": 100,
    "thousand": 1000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}


def parse_glued_number_token(token: str) -> int | None:
    if token.isdigit():
        return int(token)

    if token in SMALL_NUMBERS:
        return SMALL_NUMBERS[token]
    if token in TENS_NUMBERS:
        return TENS_NUMBERS[token]

    for tens_word, tens_value in TENS_NUMBERS.items():
        if token.startswith(tens_word) and len(token) > len(tens_word):
            suffix = token[len(tens_word) :]
            if suffix in SMALL_NUMBERS and SMALL_NUMBERS[suffix] < 10:
                return tens_value + SMALL_NUMBERS[suffix]

    return None


def parse_script_number_phrase(
    tokens: list[str], start_idx: int, max_tokens: int = 10
) -> tuple[int, int] | None:
    idx = start_idx
    total = 0
    current = 0
    consumed = 0

    while idx < len(tokens) and consumed < max_tokens:
        token = tokens[idx]
        if token == "and":
            idx += 1
            consumed += 1
            continue

        if token in SMALL_NUMBERS:
            current += SMALL_NUMBERS[token]
            idx += 1
            consumed += 1
            continue

        if token in TENS_NUMBERS:
            current += TENS_NUMBERS[token]
            idx += 1
            consumed += 1
            continue

        glued = parse_glued_number_token(token)
        if glued is not None and token not in SMALL_NUMBERS and token not in TENS_NUMBERS:
            current += glued
            idx += 1
            consumed += 1
            if idx >= len(tokens) or tokens[idx] not in SCALE_NUMBERS:
                break
            continue

        if token in SCALE_NUMBERS:
            scale = SCALE_NUMBERS[token]
            if scale == 100:
                current = (current or 1) * 100
            else:
                current = (current or 1) * scale
                total += current
                current = 0
            idx += 1
            consumed += 1
            continue

        break

    if consumed == 0:
        return None

    return total + current, consumed


def parse_whisper_number_phrase(
    whisper_words: list[dict[str, Any]], start_idx: int
) -> tuple[int, int] | None:
    if start_idx >= len(whisper_words):
        return None

    token = whisper_token(whisper_words[start_idx])
    if not token or not token.isdigit():
        return None

    value = int(token)
    consumed = 1

    if start_idx + 1 < len(whisper_words):
        next_token = whisper_token(whisper_words[start_idx + 1])
        if next_token == "000":
            value *= 1000
            consumed = 2

    if (
        value % 10 == 0
        and value >= 10
        and start_idx + consumed < len(whisper_words)
    ):
        trailing = whisper_token(whisper_words[start_idx + consumed])
        trailing_value = parse_glued_number_token(trailing)
        if trailing_value is not None and 0 < trailing_value < 10:
            value += trailing_value
            consumed += 1

    return value, consumed


def whisper_tokens_joined(
    whisper_words: list[dict[str, Any]], start_idx: int, max_parts: int = 4
) -> tuple[str, int] | None:
    parts: list[str] = []
    consumed = 0
    idx = start_idx

    while idx < len(whisper_words) and len(parts) < max_parts:
        token = whisper_token(whisper_words[idx])
        idx += 1
        consumed += 1
        if not token or token == "-":
            continue
        parts.append(token)

    if not parts:
        return None

    return "".join(parts), consumed


def try_match_joined_whisper_word(
    script_token: str,
    whisper_words: list[dict[str, Any]],
    whisper_idx: int,
) -> tuple[int, int] | None:
    for part_count in range(2, 5):
        joined = whisper_tokens_joined(whisper_words, whisper_idx, max_parts=part_count)
        if joined is None:
            continue
        combined, consumed = joined
        if script_token == combined:
            return 1, consumed
    return None


def try_match_number_phrase(
    script_tokens: list[str],
    script_idx: int,
    whisper_words: list[dict[str, Any]],
    whisper_idx: int,
) -> tuple[int, int] | None:
    script_number = parse_script_number_phrase(script_tokens, script_idx)
    whisper_number = parse_whisper_number_phrase(whisper_words, whisper_idx)
    if script_number is None or whisper_number is None:
        return None
    if script_number[0] != whisper_number[0]:
        return None
    return script_number[1], whisper_number[1]


def format_timestamp(total_seconds: float) -> str:
    rounded_ms = int(round(total_seconds * 1000))
    hours, remainder = divmod(rounded_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def make_timing_block(start_seconds: float, end_seconds: float) -> dict[str, Any]:
    duration_seconds = max(0.0, end_seconds - start_seconds)
    return {
        "start_seconds": round(start_seconds, 3),
        "end_seconds": round(end_seconds, 3),
        "duration_seconds": round(duration_seconds, 3),
        "start_timecode": format_timestamp(start_seconds),
        "end_timecode": format_timestamp(end_seconds),
    }


def get_audio_duration(audio_path: Path) -> float | None:
    try:
        from export_video import probe_decoded_duration

        return round(probe_decoded_duration(audio_path), 3)
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError, RuntimeError):
        return None


def iter_script_segments(script_data: dict[str, Any]) -> list[dict[str, Any]]:
    from script_format import parse_segment_broll_fields

    segments: list[dict[str, Any]] = []
    for beat_block in script_data.get("script", []):
        beat = beat_block.get("beat")
        label = beat_block.get("label")
        for segment in beat_block.get("segments", []):
            content = str(segment.get("content", "")).strip()
            description = segment.get("description", "")
            search_query, category = parse_segment_broll_fields(segment)
            segments.append(
                {
                    "segment_id": segment.get("segment_id"),
                    "beat": beat,
                    "label": label,
                    "content": content,
                    "word_count": count_words(content),
                    "script_tokens": expand_tokens(normalize(content)),
                    "description": description,
                    "broll": {
                        "search_query": search_query,
                        "category": category,
                    },
                }
            )
    segments.sort(key=lambda item: item["segment_id"] or 0)
    return segments


def cache_path_for_audio(audio_path: Path) -> Path:
    project = audio_path.parent.name or "project"
    return CACHE_DIR / f"{project}_{audio_path.stem}.json"


def load_whisper_words(cache_file: Path) -> list[dict[str, Any]] | None:
    if not cache_file.exists():
        return None
    with cache_file.open("r", encoding="utf-8") as infile:
        payload = json.load(infile)
    return payload.get("words")


def save_whisper_cache(cache_file: Path, words: list[dict[str, Any]]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps({"words": words}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def transcribe_audio(
    audio_path: Path,
    model_name: str,
    on_progress: Callable[[int, str], None] | None = None,
    on_hardware: HardwareCallback = None,
) -> list[dict[str, Any]]:
    from hardware_monitor import resolve_whisper_device, sample_hardware_stats

    try:
        import whisper
    except ImportError as exc:
        raise SystemExit(
            "Failed to import Whisper for audio alignment.\n"
            f"  {exc}\n"
            "If Whisper is not installed: pip install openai-whisper\n"
            "If a local file shadows stdlib (e.g. copy.py), rename it."
        ) from exc

    device, device_info = resolve_whisper_device()
    gpu_label = device_info.get("gpu_name") or "CPU"
    print(f"Whisper device: {device} ({gpu_label})")

    if on_hardware:
        on_hardware(sample_hardware_stats(device, device_info))

    print(f"Loading Whisper model '{model_name}' on {device}...")
    if on_progress:
        label = "GPU" if device == "cuda" else "CPU"
        on_progress(9, f"Loading Whisper model on {label}…")
    model = whisper.load_model(model_name, device=device)
    print(f"Transcribing {audio_path}...")
    if on_progress:
        on_progress(10, "Starting transcription…")

    transcribe_kwargs: dict[str, Any] = {
        "word_timestamps": True,
        "language": "en",
        # Whisper disables its tqdm bar when verbose=True — keep False so we can hook progress.
        "verbose": False,
    }

    if on_progress:
        import importlib
        import time as time_module

        whisper_transcribe_mod = importlib.import_module("whisper.transcribe")
        original_tqdm_cls = whisper_transcribe_mod.tqdm.tqdm
        last_percent = 10
        last_fraction = 0.0
        last_report_ts = 0.0

        class WhisperProgressTqdm(original_tqdm_cls):  # type: ignore[misc, valid-type]
            def update(self, n: float = 1) -> bool | None:
                nonlocal last_percent, last_fraction, last_report_ts
                result = super().update(n)
                total = self.total or 0
                if total > 0:
                    fraction = min(1.0, self.n / total)
                    percent = min(37, 10 + int(27 * fraction))
                    now = time_module.time()
                    if (
                        percent > last_percent
                        or fraction >= last_fraction + 0.004
                        or now - last_report_ts >= 2.0
                    ):
                        last_percent = max(last_percent, percent)
                        last_fraction = fraction
                        last_report_ts = now
                        on_progress(
                            percent,
                            f"Transcribing audio… {int(fraction * 100)}%",
                        )
                        if on_hardware:
                            on_hardware(sample_hardware_stats(device, device_info))
                return result

        whisper_transcribe_mod.tqdm.tqdm = WhisperProgressTqdm
        try:
            result = model.transcribe(str(audio_path), **transcribe_kwargs)
        finally:
            whisper_transcribe_mod.tqdm.tqdm = original_tqdm_cls
    else:
        result = model.transcribe(str(audio_path), verbose=False, **transcribe_kwargs)

    words: list[dict[str, Any]] = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            words.append(
                {
                    "word": word["word"].strip(),
                    "start": round(float(word["start"]), 3),
                    "end": round(float(word["end"]), 3),
                }
            )
    return words


def get_whisper_words(
    audio_path: Path,
    model_name: str,
    retranscribe: bool,
) -> list[dict[str, Any]]:
    cache_file = cache_path_for_audio(audio_path)
    if not retranscribe:
        cached = load_whisper_words(cache_file)
        if cached:
            print(f"Using cached Whisper words from {cache_file}")
            return cached

    words = transcribe_audio(audio_path, model_name)
    save_whisper_cache(cache_file, words)
    print(f"Saved Whisper cache to {cache_file}")
    return words


SPELLING_ALIASES: dict[str, str] = {
    "centimetres": "centimeters",
    "metres": "meters",
    "kilometres": "kilometers",
    "amphorae": "amphore",
    "guyots": "goyots",
    "pteropods": "terrapods",
    "polynyas": "polinjas",
    "shale": "shell",
    "coral": "coal",
    "carry": "carried",
    "ontongjava": "ontonguejava",
    "bicarbonate": "carbonate",
}


def tokens_equivalent(script_token: str, whisper_token_value: str) -> bool:
    if script_token == whisper_token_value:
        return True
    if SPELLING_ALIASES.get(script_token) == whisper_token_value:
        return True
    if SPELLING_ALIASES.get(whisper_token_value) == script_token:
        return True
    return False


def consume_token_match(
    script_tokens: list[str],
    script_idx: int,
    whisper_words: list[dict[str, Any]],
    whisper_idx: int,
) -> tuple[int, int] | None:
    """Return (script_tokens_consumed, whisper_words_consumed) when tokens align."""
    if script_idx >= len(script_tokens) or whisper_idx >= len(whisper_words):
        return None

    whisper_tok = whisper_token(whisper_words[whisper_idx])
    script_tok = script_tokens[script_idx]

    if tokens_equivalent(script_tok, whisper_tok):
        return 1, 1

    combined = WHISPER_COMBINED.get(whisper_tok)
    if combined and script_tokens[script_idx : script_idx + len(combined)] == combined:
        return len(combined), 1

    number_match = try_match_number_phrase(
        script_tokens, script_idx, whisper_words, whisper_idx
    )
    if number_match is not None:
        return number_match

    joined_match = try_match_joined_whisper_word(
        script_tok, whisper_words, whisper_idx
    )
    if joined_match is not None:
        return joined_match

    if script_idx + 1 < len(script_tokens):
        script_pair = script_tokens[script_idx] + script_tokens[script_idx + 1]
        pair_match = try_match_joined_whisper_word(
            script_pair, whisper_words, whisper_idx
        )
        if pair_match is not None:
            return 2, pair_match[1]

    if script_tok == "percent" and not whisper_tok:
        return 1, 1

    return None


def min_window_matches(window_len: int) -> int:
    return max(2, math.ceil(window_len * DEFAULT_MIN_WINDOW_MATCH_RATIO))


def find_window_start(
    script_tokens: list[str],
    whisper_words: list[dict[str, Any]],
    cursor: int,
    window_size: int = DEFAULT_MATCH_WINDOW,
    max_skip: int = 0,
    max_cursor_jump: int = DEFAULT_MAX_CURSOR_JUMP,
) -> tuple[int, int] | None:
    if not script_tokens:
        return None

    window = script_tokens[: min(window_size, len(script_tokens))]
    min_matches = min_window_matches(len(window))
    search_end = len(whisper_words)
    best_hit: tuple[int, int] | None = None

    for start_idx in range(cursor, search_end):
        if start_idx - cursor > max_cursor_jump:
            break

        for skip in range(max_skip + 1):
            script_idx = skip
            whisper_idx = start_idx
            matched = 0

            while script_idx < len(window) and whisper_idx < len(whisper_words):
                consumed = consume_token_match(
                    window, script_idx, whisper_words, whisper_idx
                )
                if consumed is None:
                    break
                script_consumed, whisper_consumed = consumed
                matched += 1
                script_idx += script_consumed
                whisper_idx += whisper_consumed

            if matched >= min_matches:
                return start_idx, whisper_idx

            if matched >= min_matches - 1 and best_hit is None:
                best_hit = (start_idx, whisper_idx)

    return best_hit


def extend_match(
    script_tokens: list[str],
    whisper_words: list[dict[str, Any]],
    start_idx: int,
    whisper_idx: int,
    lookahead: int,
) -> list[int]:
    matched_indices: list[int] = []
    script_idx = 0
    cursor = start_idx

    while script_idx < len(script_tokens) and cursor < len(whisper_words):
        found_at: int | None = None
        script_advance = 0
        whisper_advance = 0

        for offset in range(lookahead + 1):
            check_idx = cursor + offset
            if check_idx >= len(whisper_words):
                break
            consumed = consume_token_match(
                script_tokens, script_idx, whisper_words, check_idx
            )
            if consumed is not None:
                found_at = check_idx
                script_advance, whisper_advance = consumed
                break

        if found_at is None:
            script_idx += 1
            continue

        matched_indices.append(found_at)
        cursor = found_at + whisper_advance
        script_idx += script_advance

    return matched_indices


def fact_number_token_length(script_tokens: list[str]) -> int:
    if not script_tokens or script_tokens[0] != "fact":
        return 0
    parsed = parse_script_number_phrase(script_tokens, 1)
    if parsed is None:
        return 1
    return 1 + parsed[1]


def align_segment(
    script_tokens: list[str],
    whisper_words: list[dict[str, Any]],
    cursor: int,
    fuzzy: bool = False,
    lookahead: int = DEFAULT_LOOKAHEAD,
) -> tuple[list[int], int]:
    if not script_tokens:
        return [], cursor

    body_tokens = script_tokens
    window_hit = find_window_start(
        script_tokens,
        whisper_words,
        cursor,
        max_skip=DEFAULT_LOOKAHEAD if fuzzy else 0,
    )
    if window_hit is None:
        skip = fact_number_token_length(script_tokens)
        if skip > 1:
            body_tokens = script_tokens[skip:]
            window_hit = find_window_start(
                body_tokens,
                whisper_words,
                cursor,
                max_skip=DEFAULT_LOOKAHEAD if fuzzy else 0,
            )
    if window_hit is None:
        return [], cursor

    start_idx, whisper_idx = window_hit
    matched_indices = extend_match(
        body_tokens,
        whisper_words,
        start_idx,
        whisper_idx,
        lookahead=lookahead if fuzzy else DEFAULT_LOOKAHEAD,
    )

    if not matched_indices:
        matched_indices = [start_idx]

    return matched_indices, matched_indices[-1] + 1


def interpolate_failed_segments(timeline_segments: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    run_start = 0
    total = len(timeline_segments)

    while run_start < total:
        if timeline_segments[run_start]["timing"]["start_seconds"] is not None:
            run_start += 1
            continue

        run_end = run_start
        while (
            run_end < total
            and timeline_segments[run_end]["timing"]["start_seconds"] is None
        ):
            run_end += 1

        prev_end = None
        for earlier in reversed(timeline_segments[:run_start]):
            if earlier["timing"]["end_seconds"] is not None:
                prev_end = earlier["timing"]["end_seconds"]
                break

        next_start = None
        if run_end < total:
            for later in timeline_segments[run_end:]:
                if later["timing"]["start_seconds"] is not None:
                    next_start = later["timing"]["start_seconds"]
                    break

        failed = timeline_segments[run_start:run_end]
        run_len = len(failed)

        if prev_end is not None and next_start is not None and next_start > prev_end:
            gap = next_start - prev_end
            step = gap / run_len
            for offset, entry in enumerate(failed):
                start_seconds = prev_end + offset * step
                end_seconds = prev_end + (offset + 1) * step
                entry["alignment"]["status"] = "interpolated"
                entry["timing"] = make_timing_block(start_seconds, end_seconds)
                warnings.append(
                    f"Segment {entry['segment_id']}: interpolated between neighbors."
                )
        elif prev_end is not None:
            for entry in failed:
                fallback_duration = max(
                    DEFAULT_MIN_DURATION, entry["word_count"] / DEFAULT_WPM * 60.0
                )
                entry["alignment"]["status"] = "estimated_fallback"
                entry["timing"] = make_timing_block(prev_end, prev_end + fallback_duration)
                prev_end += fallback_duration
                warnings.append(
                    f"Segment {entry['segment_id']}: estimated after previous segment."
                )
        else:
            for entry in failed:
                warnings.append(
                    f"Segment {entry['segment_id']}: could not align to audio."
                )

        run_start = run_end

    return warnings


def apply_aligned_spans(
    timeline_segments: list[dict[str, Any]],
    raw_starts: dict[int, float],
    raw_ends: dict[int, float],
) -> None:
    for index, entry in enumerate(timeline_segments):
        segment_id = entry["segment_id"]
        if segment_id not in raw_starts:
            continue

        start_seconds = raw_starts[segment_id]
        end_seconds = raw_ends[segment_id]

        for future in timeline_segments[index + 1 :]:
            future_id = future["segment_id"]
            if future_id in raw_starts:
                end_seconds = raw_starts[future_id]
                break

        entry["timing"] = make_timing_block(start_seconds, end_seconds)


def build_whisper_timeline(
    script_data: dict[str, Any],
    whisper_words: list[dict[str, Any]],
    fuzzy: bool = False,
    lookahead: int = DEFAULT_LOOKAHEAD,
    only_segment_ids: set[int] | None = None,
    existing_timeline: list[dict[str, Any]] | None = None,
    on_segment_progress: Callable[[int, int, int], None] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    script_segments = iter_script_segments(script_data)
    segment_list = list(script_segments)
    total_segments = len(segment_list)
    warnings: list[str] = []
    whisper_cursor = 0
    raw_starts: dict[int, float] = {}
    raw_ends: dict[int, float] = {}

    if existing_timeline is not None and only_segment_ids:
        timeline_segments = existing_timeline
        existing_by_id = {entry["segment_id"]: entry for entry in timeline_segments}
    else:
        timeline_segments = []
        existing_by_id = {}

    for index, segment in enumerate(segment_list):
        segment_id = segment["segment_id"]
        retry_only = only_segment_ids is not None

        if retry_only and segment_id not in only_segment_ids:
            continue

        if retry_only and segment_id in existing_by_id:
            prior = existing_by_id[segment_id]
            for earlier in timeline_segments:
                if earlier["segment_id"] == segment_id:
                    break
                if earlier["timing"]["start_seconds"] is not None:
                    whisper_cursor = max(
                        whisper_cursor,
                        earlier["alignment"].get("whisper_word_indices", [-1])[-1] + 1
                        if earlier["alignment"].get("whisper_word_indices")
                        else 0,
                    )

        script_tokens = segment["script_tokens"]
        matched_indices, next_cursor = align_segment(
            script_tokens,
            whisper_words,
            whisper_cursor,
            fuzzy=fuzzy,
            lookahead=lookahead,
        )

        alignment_ratio = (
            len(matched_indices) / len(script_tokens) if script_tokens else 1.0
        )
        aligned = bool(matched_indices) and alignment_ratio >= 0.5

        if aligned:
            whisper_cursor = next_cursor
            raw_starts[segment_id] = float(whisper_words[matched_indices[0]]["start"])
            raw_ends[segment_id] = float(whisper_words[matched_indices[-1]]["end"])
            alignment_status = "aligned"
            if alignment_ratio < 1.0:
                warnings.append(
                    f"Segment {segment_id}: partial match "
                    f"({len(matched_indices)}/{len(script_tokens)} words)."
                )
        else:
            alignment_status = "unmatched"
            warnings.append(
                f"Segment {segment_id}: could not align to audio."
            )

        entry = {
            "segment_id": segment_id,
            "beat": segment["beat"],
            "label": segment["label"],
            "content": segment["content"],
            "word_count": segment["word_count"],
            "description": segment["description"],
            "broll": segment["broll"],
            "alignment": {
                "status": alignment_status,
                "matched_words": len(matched_indices),
                "script_words": len(script_tokens),
                "whisper_word_indices": matched_indices,
            },
            "timing": {
                "start_seconds": None,
                "end_seconds": None,
                "duration_seconds": None,
                "start_timecode": None,
                "end_timecode": None,
            },
        }

        if retry_only and segment_id in existing_by_id:
            existing_by_id[segment_id].update(entry)
        elif not retry_only:
            timeline_segments.append(entry)

        if on_segment_progress and (not retry_only or segment_id in (only_segment_ids or set())):
            on_segment_progress(index + 1, total_segments, segment_id)

    if retry_only and existing_timeline is not None:
        timeline_segments = existing_timeline
        for entry in timeline_segments:
            segment_id = entry["segment_id"]
            if segment_id in raw_starts:
                entry["timing"] = make_timing_block(
                    raw_starts[segment_id], raw_ends[segment_id]
                )

    apply_aligned_spans(timeline_segments, raw_starts, raw_ends)
    warnings.extend(interpolate_failed_segments(timeline_segments))
    return timeline_segments, warnings


def build_estimate_timeline(script_data: dict[str, Any], wpm: float, min_duration: float, gap: float) -> list[dict[str, Any]]:
    cursor = 0.0
    timeline_segments: list[dict[str, Any]] = []

    for segment in iter_script_segments(script_data):
        duration_seconds = max(min_duration, (segment["word_count"] / wpm) * 60.0)
        start_seconds = cursor
        end_seconds = start_seconds + duration_seconds

        timeline_segments.append(
            {
                "segment_id": segment["segment_id"],
                "beat": segment["beat"],
                "label": segment["label"],
                "content": segment["content"],
                "word_count": segment["word_count"],
                "description": segment["description"],
                "broll": segment["broll"],
                "alignment": {
                    "status": "estimated",
                    "matched_words": 0,
                    "script_words": segment["word_count"],
                    "whisper_word_indices": [],
                },
                "timing": make_timing_block(start_seconds, end_seconds),
            }
        )
        cursor = end_seconds + gap

    return timeline_segments


def summarize_timeline(
    script_data: dict[str, Any],
    timeline_segments: list[dict[str, Any]],
    timing_method: dict[str, Any],
    source_file: str,
    audio_file: str | None,
    warnings: list[str],
    video_duration_s: float | None,
) -> dict[str, Any]:
    total_words = sum(segment["word_count"] for segment in timeline_segments)
    end_times = [
        segment["timing"]["end_seconds"]
        for segment in timeline_segments
        if segment["timing"]["end_seconds"] is not None
    ]
    total_seconds = video_duration_s or (max(end_times) if end_times else 0.0)
    aligned_count = sum(
        1 for segment in timeline_segments if segment["alignment"]["status"] == "aligned"
    )
    timed_count = sum(
        1
        for segment in timeline_segments
        if segment.get("timing", {}).get("start_seconds") is not None
        and segment.get("timing", {}).get("end_seconds") is not None
    )
    interpolated_count = sum(
        1 for segment in timeline_segments if segment["alignment"]["status"] == "interpolated"
    )
    estimated_count = sum(
        1
        for segment in timeline_segments
        if segment["alignment"]["status"] in ("estimated_fallback", "estimated")
    )

    return {
        "title": script_data.get("title"),
        "channel": script_data.get("channel"),
        "source_file": source_file,
        "audio_file": audio_file,
        "video_duration_s": video_duration_s,
        "timing_method": timing_method,
        "summary": {
            "total_segments": len(timeline_segments),
            "aligned_segments": aligned_count,
            "timed_segments": timed_count,
            "interpolated_segments": interpolated_count,
            "estimated_segments": estimated_count,
            "total_words": total_words,
            "total_duration_seconds": round(total_seconds, 3),
            "total_duration_timecode": format_timestamp(total_seconds),
            "warnings": warnings,
        },
        "segments": timeline_segments,
    }


def load_existing_timeline(output_path: Path) -> list[dict[str, Any]] | None:
    if not output_path.exists():
        return None
    with output_path.open("r", encoding="utf-8") as infile:
        payload = json.load(infile)
    return payload.get("segments")


def failed_segment_ids(timeline_segments: list[dict[str, Any]]) -> set[int]:
    return {
        entry["segment_id"]
        for entry in timeline_segments
        if entry["timing"]["start_seconds"] is None
        or entry["alignment"]["status"] == "unmatched"
        or entry["alignment"].get("matched_words", 0) == 0
    }


def generate_segment_timestamps(
    folder: Path,
    *,
    script_path: Path | None = None,
    audio_path: Path | None = None,
    output: Path | None = None,
    model: str = DEFAULT_WHISPER_MODEL,
    retry_failed: bool = False,
    retranscribe: bool = False,
    lookahead: int = DEFAULT_LOOKAHEAD,
    indent: int = 2,
    on_progress: ProgressCallback = None,
    on_hardware: HardwareCallback = None,
) -> dict[str, Any]:
    """Align script segments to narration audio and write segment_timestamps.json."""

    def report(percent: int, message: str, stage: str) -> None:
        if on_progress:
            on_progress(min(100, max(0, percent)), message, stage)

    _last_report = {"percent": -1, "ts": 0.0}

    def report_throttled(percent: int, message: str, stage: str) -> None:
        import time as time_module

        now = time_module.time()
        if percent < _last_report["percent"]:
            return
        if percent == _last_report["percent"] and now - _last_report["ts"] < 1.0:
            return
        _last_report["percent"] = percent
        _last_report["ts"] = now
        report(percent, message, stage)

    report(2, "Preparing alignment…", "prepare")
    if script_path is not None and audio_path is not None:
        input_path = script_path
        if not input_path.exists():
            raise RuntimeError(f"Script not found: {input_path}")
        if not audio_path.exists():
            raise RuntimeError(f"Audio not found: {audio_path}")
    else:
        input_path, audio_path = resolve_video_folder(folder)
    output_path = output or folder / "segment_timestamps.json"

    with input_path.open("r", encoding="utf-8") as infile:
        script_data = json.load(infile)

    cache_file = cache_path_for_audio(audio_path)
    cached_words = None if retranscribe else load_whisper_words(cache_file)
    if cached_words:
        report(38, "Using cached Whisper transcription", "whisper")
        whisper_words = cached_words
    else:
        report(8, "Loading Whisper model…", "whisper")

        def whisper_progress(percent: int, message: str) -> None:
            report(percent, message, "whisper")

        whisper_words = transcribe_audio(
            audio_path,
            model,
            on_progress=whisper_progress,
            on_hardware=on_hardware,
        )
        save_whisper_cache(cache_file, whisper_words)
        report(38, "Transcription complete", "whisper")

    video_duration_s = get_audio_duration(audio_path)

    existing_timeline = None
    only_segment_ids = None
    fuzzy = False

    if retry_failed:
        existing_timeline = load_existing_timeline(output_path)
        if not existing_timeline:
            raise RuntimeError(
                f"--retry-failed requires an existing output file: {output_path}"
            )
        only_segment_ids = failed_segment_ids(existing_timeline)
        if not only_segment_ids:
            return read_json(output_path)
        fuzzy = True

    def on_align_progress(done: int, total: int, segment_id: int) -> None:
        span = 50
        base = 40
        percent = base + int(span * done / max(1, total))
        report_throttled(
            percent,
            f"Aligning segment {segment_id} ({done}/{total})…",
            "align",
        )

    timeline_segments, warnings = build_whisper_timeline(
        script_data=script_data,
        whisper_words=whisper_words,
        fuzzy=fuzzy,
        lookahead=lookahead,
        only_segment_ids=only_segment_ids,
        existing_timeline=existing_timeline,
        on_segment_progress=on_align_progress,
    )

    if not retry_failed:
        failed_ids = failed_segment_ids(timeline_segments)
        if failed_ids:
            report(90, f"Retrying {len(failed_ids)} failed segment(s)…", "retry")

            def on_retry_progress(done: int, total: int, segment_id: int) -> None:
                span = 8
                base = 90
                percent = base + int(span * done / max(1, total))
                report_throttled(
                    percent,
                    f"Fuzzy retry segment {segment_id} ({done}/{total})…",
                    "retry",
                )

            timeline_segments, retry_warnings = build_whisper_timeline(
                script_data=script_data,
                whisper_words=whisper_words,
                fuzzy=True,
                lookahead=lookahead,
                only_segment_ids=failed_ids,
                existing_timeline=timeline_segments,
                on_segment_progress=on_retry_progress,
            )
            warnings.extend(retry_warnings)

    report(98, "Writing segment_timestamps.json…", "finalize")
    timeline = summarize_timeline(
        script_data=script_data,
        timeline_segments=timeline_segments,
        timing_method={
            "type": "whisper_word_alignment",
            "whisper_model": model,
            "lookahead_words": lookahead,
            "retry_failed": retry_failed,
        },
        source_file=str(input_path),
        audio_file=str(audio_path),
        warnings=warnings,
        video_duration_s=video_duration_s,
    )

    output_path.write_text(
        json.dumps(timeline, indent=indent, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report(100, "Segment timestamps ready", "done")
    return timeline


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as infile:
        return json.load(infile)


def main() -> None:
    args = parse_args()
    folder = Path(args.folder)
    output_path = Path(args.output) if args.output else folder / "segment_timestamps.json"

    timeline = generate_segment_timestamps(
        folder,
        output=output_path,
        model=args.model,
        retry_failed=args.retry_failed,
        retranscribe=args.retranscribe,
        lookahead=args.lookahead,
        indent=args.indent,
    )

    if args.retry_failed and timeline.get("segments"):
        failed = failed_segment_ids(timeline["segments"])
        if not failed:
            print("No failed segments to retry.")
            return

    total_seconds = timeline["summary"]["total_duration_seconds"]
    aligned = timeline["summary"].get("aligned_segments", 0)
    print(
        f"Wrote {len(timeline['segments'])} segments to {output_path} "
        f"({math.floor(total_seconds / 60)}m {round(total_seconds % 60, 1)}s)."
    )
    print(f"Aligned {aligned}/{len(timeline['segments'])} segments from audio.")
    for warning in timeline["summary"]["warnings"]:
        print(f"  warning: {warning}")


if __name__ == "__main__":
    main()
