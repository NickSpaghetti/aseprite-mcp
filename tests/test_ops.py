"""The op layer: lua/lib.lua, lua/ops/*.lua, and commands.call."""
import json
import os

import pytest
from conftest import fails, ok, run

from aseprite_mcp.core import commands
from aseprite_mcp.core.errors import AsepriteError
from aseprite_mcp.tools import canvas, layers

# Modules whose tools only call ops. They must not build Lua in Python again.
MIGRATED = ["animation", "canvas", "drawing", "fx", "layers", "native_fx", "palette"]

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "aseprite_mcp", "tools")


def _layer_names(path):
    # JSON, not one name per line: names may contain newlines.
    out = run(commands.run_script(
        "local names = {} for _, l in ipairs(app.activeSprite.layers) do names[#names + 1] = l.name end "
        "print(json.encode(names))", path))
    return json.loads(out)


def _load_test_op(source):
    """Register an extra op in the running worker, for tests only."""
    run(commands.run_script('print("warm")'))
    with commands.worker._lock:
        commands.worker._send({"load": [{"name": "test_op.lua", "code": source}]})


@pytest.mark.parametrize("module", MIGRATED)
def test_migrated_module_builds_no_lua(module):
    source = open(os.path.join(TOOLS_DIR, f"{module}.py")).read()
    for needle in ("run_script", "lua_escape", "FIND_LAYER", 'print("ERROR'):
        assert needle not in source, f"{module}.py still contains {needle}"


def test_hostile_names_are_stored_as_data(base_dir):
    path = f"{base_dir}/ops_hostile.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    hostile = 'Arm "L" ]] end) os.exit(1) --\n\\0 [[x]]'
    ok(run(canvas.add_layer(path, hostile)))
    ok(run(layers.rename_layer(path, hostile, hostile + " v2")))
    assert _layer_names(path) == ["Layer 1", hostile + " v2"]


def test_op_failure_carries_its_code(sprite):
    with pytest.raises(AsepriteError) as info:
        run(layers.rename_layer(sprite, "NO_SUCH_LAYER", "x"))
    assert info.value.code == "LayerNotFound"
    assert str(info.value) == "Layer not found"


def test_unknown_op_is_reported():
    with pytest.raises(AsepriteError) as info:
        run(commands.call("nope.nothing"))
    assert info.value.code == "UnknownOp"


def test_failed_edit_leaves_the_file_untouched(base_dir):
    path = f"{base_dir}/ops_atomic.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    _load_test_op('''
        local lib = ...
        lib.edit("test.half_edit", function(sprite)
          sprite:newLayer().name = "half"
          lib.fail("Boom", "failed after changing the sprite")
        end)
    ''')
    with pytest.raises(AsepriteError, match="failed after changing"):
        run(commands.call("test.half_edit", path))
    assert _layer_names(path) == ["Layer 1"]


def test_whole_numbers_arrive_as_integers():
    _load_test_op('''
        local lib = ...
        lib.free("test.types", function(a)
          return { n = math.type(a.n), f = math.type(a.f), list = math.type(a.list[2]) }
        end)
    ''')
    assert run(commands.call("test.types", n=3, f=1.5, list=[1, 2])) == {
        "n": "integer", "f": "float", "list": "integer"}
