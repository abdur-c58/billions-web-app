"""Global automation toggle persisted under workspace/."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

SETTINGS_NAME = "automation_settings.json"
_lock = threading.Lock()

_default_settings: dict[str, Any] = {
    "enabled": True,
}


def settings_path(workspace_root: Path) -> Path:
    return workspace_root / SETTINGS_NAME


def read_automation_settings(workspace_root: Path) -> dict[str, Any]:
    path = settings_path(workspace_root)
    if not path.exists():
        return dict(_default_settings)
    try:
        with path.open("r", encoding="utf-8") as infile:
            payload = json.load(infile)
        if isinstance(payload, dict):
            return {**_default_settings, **payload}
    except (json.JSONDecodeError, OSError):
        pass
    return dict(_default_settings)


def write_automation_settings(workspace_root: Path, **updates: Any) -> dict[str, Any]:
    with _lock:
        current = read_automation_settings(workspace_root)
        current.update(updates)
        path = settings_path(workspace_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return current


def automation_enabled(workspace_root: Path) -> bool:
    return bool(read_automation_settings(workspace_root).get("enabled", True))
