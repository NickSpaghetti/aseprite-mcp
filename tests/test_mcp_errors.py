"""Failures must reach the MCP client as isError results.

These talk to the real server over stdio, so they check the protocol boundary
rather than the Python functions behind it.
"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from conftest import BASE

REPO = os.path.join(os.path.dirname(__file__), "..")


async def _call(tool, args):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "aseprite_mcp"],
        env={**os.environ, "PYTHONPATH": REPO}, cwd=BASE)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, args)


def call(tool, args):
    return asyncio.run(_call(tool, args))


def test_input_error_is_flagged():
    result = call("add_frame", {"filename": f"{BASE}/does-not-exist.aseprite"})
    assert result.isError is True
    assert "not found" in result.content[0].text


def test_aseprite_error_is_flagged(sprite):
    result = call("delete_tag", {"filename": sprite, "name": "NO_SUCH_TAG"})
    assert result.isError is True
    assert "Tag not found" in result.content[0].text


def test_success_is_not_flagged(sprite):
    result = call("get_sprite_info", {"filename": sprite})
    assert result.isError is False
