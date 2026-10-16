"""Checks on raw tool arguments. Each raises InputError or returns nothing, so
code past the tool entry point can trust what it was given."""

import os

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
