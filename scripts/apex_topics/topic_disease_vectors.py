"""Apex Archives — disease vector ranking (from temp.py / script.json)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMP_PY = ROOT / "temp.py"
SCRIPT_JSON = ROOT / "script.json"


def build() -> dict:
    if not SCRIPT_JSON.exists() or SCRIPT_JSON.stat().st_mtime < TEMP_PY.stat().st_mtime:
        subprocess.run([sys.executable, str(TEMP_PY)], check=True, cwd=str(ROOT))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from apex_enrich import finalize_script

    return finalize_script(json.loads(SCRIPT_JSON.read_text(encoding="utf-8")))
