"""Download YouTube audio as MP3 (adapted from RestfulLibrary/mp.py)."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path


def extract_video_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()

    if re.fullmatch(r"[\w-]{11}", url_or_id):
        return url_or_id

    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/|youtube\.com/shorts/)([\w-]{11})",
        r"youtube\.com/watch\?.*[&?]v=([\w-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def sanitize_audio_filename(title: str) -> str:
    safe = "".join(c if (c.isalnum() or c in " _-().") else "_" for c in title).strip()
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("._ ")
    return (safe[:120] or "youtube_audio").strip()


def download_mp3(
    url: str,
    output_dir: Path,
    *,
    bitrate: str = "192",
    cookies_browser: str | None = None,
) -> tuple[Path, str]:
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is required. Install it with: pip install -U yt-dlp"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(title)s.%(ext)s")

    options: dict = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "ios"],
            }
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }
        ],
    }

    if cookies_browser:
        options["cookiesfrombrowser"] = (cookies_browser,)

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
    except Exception as exc:
        message = str(exc)
        if "403" in message or "Forbidden" in message:
            raise RuntimeError(
                "YouTube blocked the download (HTTP 403). Update yt-dlp or try again later."
            ) from exc
        raise RuntimeError(f"YouTube download failed: {message}") from exc

    if info is None:
        raise RuntimeError("Download failed.")

    title = str(info.get("title") or extract_video_id(url)).strip()
    output_path = output_dir / f"{title}.mp3"
    if not output_path.exists():
        matches = sorted(output_dir.glob("*.mp3"), key=lambda path: path.stat().st_mtime)
        if not matches:
            raise RuntimeError("Download finished but MP3 file was not found.")
        output_path = matches[-1]

    return output_path, title


def download_youtube_audio_to_temp(
    url: str,
    *,
    bitrate: str = "192",
    cookies_browser: str | None = None,
) -> tuple[Path, str]:
    video_id = extract_video_id(url)
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    temp_dir = Path(tempfile.mkdtemp(prefix="yt_audio_"))
    try:
        local_path, title = download_mp3(
            watch_url,
            temp_dir,
            bitrate=bitrate,
            cookies_browser=cookies_browser,
        )
        return local_path, title
    except Exception:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
