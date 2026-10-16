"""Lua escape hatch (script.py)."""
from conftest import fails, ok, run

from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import script


def test_run_lua_script_returns_printed_output(sprite):
    out = ok(run(script.run_lua_script(
        'local spr = app.activeSprite print("size=" .. spr.width .. "x" .. spr.height)',
        sprite)))
    assert "size=32x32" in out


def test_run_lua_script_rejects_empty():
    fails(script.run_lua_script("  "), InputError, "Script cannot be empty")


def test_lua_syntax_error_has_a_message():
    # Aseprite prints Lua syntax errors on stdout, not stderr; the error used
    # to come back as "Failed ...: " with nothing after the colon.
    message = fails(script.run_lua_script("this is not lua"), AsepriteError)
    assert message.strip(), "error message is empty"
