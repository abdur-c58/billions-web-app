#!/usr/bin/env python3
"""Load Remotion composition prop schemas and sanitize values by type."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "lib" / "remotion-schemas.json"

SAFE_PROP_KEY = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
RESERVED_PROP_KEYS = frozenset({"durationInFrames"})

_COLOR_RE = re.compile(
    r"^(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\))$"
)


@lru_cache(maxsize=1)
def load_schemas() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def composition_schema(composition: str) -> dict[str, Any]:
    schemas = load_schemas()
    compositions = schemas.get("compositions") or {}
    if composition in compositions:
        return compositions[composition]
    return compositions.get("FactCard", {"allowExtra": True, "props": {}})


def prop_definitions(composition: str) -> dict[str, dict[str, Any]]:
    return dict(composition_schema(composition).get("props") or {})


def prop_docs_for_composition(composition: str) -> dict[str, str]:
    docs: dict[str, str] = {}
    for key, definition in prop_definitions(composition).items():
        if definition.get("hidden"):
            continue
        prop_type = definition.get("type", "string")
        label = definition.get("label") or key
        extra = ""
        if prop_type == "select":
            options = definition.get("options") or []
            extra = " | ".join(str(option) for option in options)
        elif prop_type == "number":
            min_value = definition.get("min")
            max_value = definition.get("max")
            if min_value is not None and max_value is not None:
                extra = f"{min_value}-{max_value}"
        elif prop_type == "boolean":
            extra = "true | false"
        elif prop_type == "color":
            extra = "hex or rgb()/rgba()"
        elif prop_type == "css":
            extra = "CSS background value"
        docs[key] = f"{label} ({prop_type}{': ' + extra if extra else ''})"
    return docs


def _sanitize_color(value: Any) -> str | None:
    color = str(value).strip()
    if _COLOR_RE.match(color):
        return color
    return None


def _sanitize_css(value: Any) -> str | None:
    css = str(value).strip()[:400]
    lowered = css.lower()
    if (
        not css
        or ";" in css
        or "url(" in lowered
        or not any(token in lowered for token in ("gradient", "rgb", "#", "hsl"))
    ):
        return None
    return css


def _sanitize_string(value: Any, *, max_length: int = 500) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


def _sanitize_number(value: Any, definition: dict[str, Any]) -> int | float | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower().endswith("px"):
            stripped = stripped[:-2].strip()
        try:
            number = float(stripped)
        except (TypeError, ValueError):
            return None
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
    if not (number == number):  # NaN
        return None
    min_value = definition.get("min")
    max_value = definition.get("max")
    if min_value is not None:
        number = max(float(min_value), number)
    if max_value is not None:
        number = min(float(max_value), number)
    if definition.get("integer"):
        return int(round(number))
    if definition.get("step") and float(definition["step"]) < 1:
        return round(number, 3)
    return number


def _sanitize_boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def _sanitize_select(value: Any, definition: dict[str, Any]) -> str | None:
    text = str(value).strip()
    options = [str(option) for option in (definition.get("options") or [])]
    if text in options:
        return text
    return None


def _sanitize_by_definition(value: Any, definition: dict[str, Any]) -> Any | None:
    prop_type = definition.get("type", "string")
    if prop_type in {"string"}:
        return _sanitize_string(value, max_length=int(definition.get("maxLength") or 200))
    if prop_type == "textarea":
        return _sanitize_string(value, max_length=int(definition.get("maxLength") or 500))
    if prop_type == "number":
        return _sanitize_number(value, definition)
    if prop_type == "boolean":
        return _sanitize_boolean(value)
    if prop_type == "color":
        return _sanitize_color(value)
    if prop_type == "css":
        return _sanitize_css(value)
    if prop_type == "select":
        return _sanitize_select(value, definition)
    return _sanitize_string(value)


def _infer_extra_value(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value != value:
            return None
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        lowered = stripped.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            if "." in stripped:
                return float(stripped)
            return int(stripped)
        except ValueError:
            return stripped[:500]
    if isinstance(value, (list, dict)):
        return value
    return _sanitize_string(value)


def sanitize_remotion_props(composition: str, props: dict[str, Any]) -> dict[str, Any]:
    definitions = prop_definitions(composition)
    allow_extra = bool(composition_schema(composition).get("allowExtra", True))
    cleaned: dict[str, Any] = {}

    for key, value in props.items():
        if value is None:
            continue
        if not SAFE_PROP_KEY.match(key):
            continue

        definition = definitions.get(key)
        if definition is not None:
            sanitized = _sanitize_by_definition(value, definition)
            if sanitized is not None:
                cleaned[key] = sanitized
            continue

        if not allow_extra:
            continue
        if key in RESERVED_PROP_KEYS and key not in definitions:
            continue

        sanitized = _infer_extra_value(value)
        if sanitized is not None and sanitized != "":
            cleaned[key] = sanitized

    return cleaned


def known_prop_keys(composition: str, *, include_hidden: bool = False) -> set[str]:
    keys: set[str] = set()
    for key, definition in prop_definitions(composition).items():
        if definition.get("hidden") and not include_hidden:
            continue
        keys.add(key)
    return keys
