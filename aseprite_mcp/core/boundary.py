"""Checks and parsers for raw tool arguments. Each raises InputError or returns
the parsed value, so code past the tool entry point can trust what it was given."""

import os
from typing import Any

from .colors import parse_hex_color
from .errors import InputError


def require_file(path: str) -> None:
    if not os.path.exists(path):
        raise InputError(f"File {path} not found")


def require_safe_path(path: str) -> None:
    """Reject parent-directory traversal in a user-supplied path.

    Works on normalized path components, so it does not false-positive on
    filenames like `foo..bar.aseprite`. Absolute paths and tilde expansion are
    allowed: this targets traversal only, not access scoping.
    """
    parts = os.path.normpath(path).replace("\\", "/").split("/")
    if ".." in parts:
        raise InputError("Invalid filename: parent directory traversal not allowed")


def require_color(value: str, field: str = "color") -> list[int]:
    """Parse a hex colour (#RGB, #RGBA, #RRGGBB, #RRGGBBAA) into [r, g, b, a]."""
    rgba = parse_hex_color(value) if isinstance(value, str) else None
    if rgba is None:
        raise InputError(f"Invalid {field} value: {value}")
    return list(rgba)


def require_point(item: Any, what: str = "point") -> list[int]:
    """Parse {"x": int, "y": int} into [x, y]. Bools, floats and strings are rejected."""
    if not isinstance(item, dict):
        raise InputError(f"Each {what} must be an object with integer x and y, got {item!r}")
    coords = [item.get("x"), item.get("y")]
    if not all(type(c) is int for c in coords):
        raise InputError(f"Each {what} needs integer x and y, got {item!r}")
    return coords
