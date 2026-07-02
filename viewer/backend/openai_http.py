"""Shared OpenAI HTTP client with retries for transient network errors."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_USER_AGENT = "Billions-BrollViewer/1.0"

_RETRYABLE_HTTP = {429, 500, 502, 503, 504}
_RETRYABLE_WINERRORS = {10053, 10054, 10060}


def _root_cause(exc: BaseException) -> BaseException:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, BaseException):
        return reason
    return exc


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_HTTP
    if isinstance(exc, TimeoutError):
        return True
    root = _root_cause(exc)
    if isinstance(root, OSError):
        if getattr(root, "winerror", None) in _RETRYABLE_WINERRORS:
            return True
        if root.errno in {54, 104, 110}:
            return True
    return isinstance(exc, (urllib.error.URLError, ConnectionResetError, ConnectionAbortedError))


def openai_chat_completion(
    *,
    body: dict[str, Any],
    timeout: float = 120,
    max_attempts: int = 4,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    encoded = json.dumps(body).encode("utf-8")
    last_error: RuntimeError | None = None

    for attempt in range(max_attempts):
        request = urllib.request.Request(
            OPENAI_CHAT_URL,
            data=encoded,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": DEFAULT_USER_AGENT,
                "Connection": "close",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"OpenAI API error {exc.code}: {raw}")
            if _is_retryable(exc) and attempt < max_attempts - 1:
                backoff = min(12.0, 1.5 * (2**attempt))
                print(
                    f"[openai] retry {attempt + 1}/{max_attempts} after HTTP {exc.code} "
                    f"(sleep {backoff:.1f}s)"
                )
                time.sleep(backoff)
                continue
            raise last_error from exc
        except Exception as exc:
            last_error = RuntimeError(f"OpenAI request failed: {exc}")
            if _is_retryable(exc) and attempt < max_attempts - 1:
                backoff = min(12.0, 1.5 * (2**attempt))
                print(
                    f"[openai] retry {attempt + 1}/{max_attempts} after network error "
                    f"(sleep {backoff:.1f}s): {exc}"
                )
                time.sleep(backoff)
                continue
            if isinstance(exc, urllib.error.URLError):
                raise RuntimeError(
                    "OpenAI connection was interrupted. Please try again in a few seconds."
                ) from exc
            raise last_error from exc

    if last_error:
        raise last_error
    raise RuntimeError("OpenAI request failed")


def openai_json_message(
    *,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout: float = 120,
) -> dict[str, Any]:
    payload = openai_chat_completion(
        body={
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    message = payload["choices"][0]["message"]["content"]
    return json.loads(message)
