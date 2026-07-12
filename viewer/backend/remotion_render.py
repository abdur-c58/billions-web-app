#!/usr/bin/env python3
"""Render Remotion compositions to MP4 for export segments."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REMOTION_DIR = ROOT / "remotion"
ENTRY = "src/index.ts"
FPS = 30


def remotion_available() -> bool:
    pkg = REMOTION_DIR / "package.json"
    entry = REMOTION_DIR / ENTRY
    modules = REMOTION_DIR / "node_modules"
    return pkg.exists() and entry.exists() and modules.exists()


def _props_cache_key(
    composition: str,
    props: dict[str, Any],
    *,
    width: int,
    height: int,
    duration_seconds: float,
) -> str:
    payload = {
        "composition": composition,
        "props": props,
        "width": width,
        "height": height,
        "duration_seconds": round(duration_seconds, 3),
        "fps": FPS,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def render_remotion_clip(
    *,
    composition: str,
    props: dict[str, Any],
    duration_seconds: float,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    cache_dir: Path | None = None,
    force: bool = False,
) -> Path:
    if not remotion_available():
        raise RuntimeError(
            "Remotion package is not installed. Run `npm install` in the remotion/ folder."
        )

    if duration_seconds <= 0:
        raise ValueError("Remotion segment duration must be positive.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_key = _props_cache_key(
        composition,
        props,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
    )
    if cache_dir is not None:
        cached = cache_dir / f"remotion_{composition}_{cache_key}_{width}x{height}.mp4"
        if not force and cached.exists() and cached.stat().st_size > 0:
            if cached.resolve() != output_path.resolve():
                from export_video import safe_replace

                temp_copy = output_path.with_suffix(f".copy-{cache_key}.mp4")
                shutil.copy2(cached, temp_copy)
                safe_replace(temp_copy, output_path)
            return output_path

    duration_frames = max(30, int(round(duration_seconds * FPS)))
    render_props = dict(props)
    render_props["durationInFrames"] = duration_frames

    props_file = output_path.parent / f".remotion_props_{cache_key}.json"
    props_file.write_text(json.dumps(render_props, ensure_ascii=False), encoding="utf-8")

    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    props_arg = props_file.resolve().as_posix()
    output_arg = output_path.resolve().as_posix()
    command = [
        npm_cmd,
        "exec",
        "--yes",
        "--",
        "remotion",
        "render",
        ENTRY,
        composition,
        output_arg,
        f"--props={props_arg}",
        f"--width={width}",
        f"--height={height}",
        f"--fps={FPS}",
        "--codec=h264",
        "--hardware-acceleration=if-possible",
        "--video-bitrate=8M",
        "--gl=angle",
        "--log=error",
    ]

    env = os.environ.copy()
    env.setdefault("REMOTION_DISABLE_TELEMETRY", "1")

    try:
        result = subprocess.run(
            command,
            cwd=REMOTION_DIR,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        if props_file.exists():
            props_file.unlink()

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Remotion render failed for {composition}: {detail or 'unknown error'}"
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        alt_output = Path(output_arg)
        if alt_output.exists() and alt_output.stat().st_size > 0 and alt_output != output_path:
            if output_path.parent.exists():
                from export_video import safe_replace

                temp_copy = output_path.with_suffix(".remotion-alt.mp4")
                shutil.copy2(alt_output, temp_copy)
                safe_replace(temp_copy, output_path)
        elif not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Remotion did not produce output: {output_path}")

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"remotion_{composition}_{cache_key}_{width}x{height}.mp4"
        from export_video import safe_replace

        temp_cache = cache_path.with_suffix(f".staging-{cache_key}.mp4")
        shutil.copy2(output_path, temp_cache)
        safe_replace(temp_cache, cache_path)

    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage: python remotion_render.py <Composition> <output.mp4> [--props props.json]"
        )
    composition = sys.argv[1]
    out = Path(sys.argv[2])
    props: dict[str, Any] = {}
    duration = 5.0
    if "--props" in sys.argv:
        idx = sys.argv.index("--props")
        props_path = Path(sys.argv[idx + 1])
        payload = json.loads(props_path.read_text(encoding="utf-8"))
        props = payload.get("props", payload)
        duration = float(payload.get("duration_seconds", duration))
    render_remotion_clip(
        composition=composition,
        props=props,
        duration_seconds=duration,
        output_path=out,
    )
    print(out.resolve())
