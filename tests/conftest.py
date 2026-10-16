"""Shared fixtures for the end-to-end tool tests.

These tests run each MCP tool against a real Aseprite (ASEPRITE_PATH),
so they are smoke/integration tests, not unit tests. Tests within a
file form a sequence on a module-scoped sprite; files are independent.

Scratch files live under a fixed /tmp path (not pytest's tmp_path) so
they resolve identically inside the Docker-wrapped Aseprite, which only
mounts /tmp and /var/folders.
"""
import asyncio
import os
import shutil
import sys

import pytest
from mcp.server.fastmcp.exceptions import ToolError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aseprite_mcp.tools  # noqa: F401  (registers all tools)
from aseprite_mcp.tools import canvas, drawing

BASE = "/tmp/ase-pytest"


def run(coro):
    """Execute an async tool call from a sync test."""
    return asyncio.run(coro)


def ok(result):
    """Pass a successful tool result through. Failures raise before reaching here."""
    assert isinstance(result, str), result
    return result


def fails(coro, error=ToolError, match=None):
    """Assert a tool call raises `error` (optionally matching `match`); return the message."""
    with pytest.raises(error, match=match) as info:
        run(coro)
    return str(info.value)


@pytest.fixture(scope="session", autouse=True)
def base_dir():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
    return BASE


@pytest.fixture(scope="module")
def sprite(request, base_dir):
    """A fresh 32x32 sprite per test module with a painted 'body' layer."""
    name = request.module.__name__.removeprefix("tests.").removeprefix("test_")
    path = f"{BASE}/{name}.aseprite"
    ok(run(canvas.create_canvas(32, 32, path)))
    ok(run(canvas.add_layer(path, "body")))
    ok(run(drawing.draw_rectangle_at(path, "body", 1, 8, 8, 16, 16, "#D04648", True)))
    return path
