"""Daily OpenAI call budget (Remotion layout suggestions and similar)."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_AI_MAX_CALLS_PER_DAY = 100


class AiBudget:
    def __init__(self, cache_dir: Path, max_calls: int = DEFAULT_AI_MAX_CALLS_PER_DAY) -> None:
        self.cache_dir = cache_dir
        self.max_calls = max_calls
        self.path = cache_dir / "ai_usage.json"
        self._calls = 0
        self._load()

    def _load(self) -> None:
        today = date.today().isoformat()
        if not self.path.exists():
            self._calls = 0
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._calls = 0
            return
        if data.get("date") != today:
            self._calls = 0
        else:
            self._calls = int(data.get("calls") or 0)
            saved_max = int(data.get("max_calls") or 0)
            if saved_max > 0:
                self.max_calls = saved_max

    def _save(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "date": date.today().isoformat(),
                    "calls": self._calls,
                    "max_calls": self.max_calls,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self._calls)

    def can_use(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY")) and self.remaining > 0

    def consume(self) -> None:
        self._calls += 1
        self._save()

    def snapshot(self) -> dict[str, Any]:
        return {
            "calls_today": self._calls,
            "max_calls": self.max_calls,
            "remaining": self.remaining,
        }
