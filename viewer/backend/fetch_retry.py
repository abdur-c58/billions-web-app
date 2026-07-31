"""Retry helpers for b-roll fetch (rate limits / transient errors)."""

from __future__ import annotations

import re
import time
from typing import Any, Callable

MAX_FETCH_ATTEMPTS = 8


def is_retryable_fetch_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    # Permanent client mistakes — never burn rate-limit budget retrying these.
    if re.search(
        r"no query param|empty query|search query is required|missing search query",
        message,
    ):
        return False
    status = getattr(exc, "status", None)
    # Bare 400s are often permanent (bad query); only retry if the body looks transient.
    if status == 400:
        return bool(re.search(r"rate|timeout|throttl|temporar|try again", message))
    if status in (0, 429, 502, 503, 504):
        return True
    if status is not None and isinstance(status, int) and status >= 500:
        return True
    return bool(
        re.search(
            r"rate|timeout|timed out|network|offline|429|503|502|504|cannot reach|connection|fish audio|throttl",
            message,
        )
    )


def retry_delay_seconds(attempt: int, exc: BaseException) -> float:
    status = getattr(exc, "status", None)
    base = 3.0 if status == 429 else 1.5
    return min(45.0, base * (1.6 ** max(0, attempt - 1)))


def run_with_retry(
    operation: Callable[[], Any],
    *,
    max_attempts: int = MAX_FETCH_ATTEMPTS,
    label: str = "fetch",
) -> Any:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except BaseException as exc:
            last_exc = exc
            if attempt >= max_attempts or not is_retryable_fetch_error(exc):
                raise
            delay = retry_delay_seconds(attempt, exc)
            print(f"[{label}] retry {attempt}/{max_attempts} in {delay:.1f}s: {exc}")
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{label} failed")
