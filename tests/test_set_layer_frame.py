"""set_layer and set_frame check and report; they no longer pretend to set an
"active" layer or frame, which Aseprite can't keep between calls (P01, P02)."""
import json
import os

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.errors import AsepriteError
from aseprite_mcp.tools import animation, canvas

_counter = 0


@pytest.fixture
def sprite3(base_dir):
    """8x8, 3 frames, layers 'Layer 1' and group 'grp' holding 'arm'."""
    global _counter
    _counter += 1
    path = f"{BASE}/setlf_{_counter}.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    ok(run(animation.add_frames(path, 2)))
    ok(run(canvas.add_group(path, "grp")))
    ok(run(canvas.add_layer(path, "arm", group="grp")))
    return path


def layer_names(path):
    return [layer["name"] for layer in json.loads(run(animation.get_sprite_info(path)))["layers"]]


def test_set_layer_existing_says_so_and_leaves_the_file_alone(sprite3):
    before = os.stat(sprite3).st_mtime_ns
    out = ok(run(canvas.set_layer(sprite3, "grp/arm")))
    assert "exists" in out and "no active layer" in out
    assert os.stat(sprite3).st_mtime_ns == before


def test_set_layer_missing_fails(sprite3):
    fails(canvas.set_layer(sprite3, "nope"), AsepriteError, "Layer not found")
    assert "nope" not in layer_names(sprite3)


def test_set_layer_creates_when_asked(sprite3):
    out = ok(run(canvas.set_layer(sprite3, "new", create_if_missing=True)))
    assert "created" in out and "new" in layer_names(sprite3)


def test_set_frame_existing_says_so_and_leaves_the_file_alone(sprite3):
    before = os.stat(sprite3).st_mtime_ns
    out = ok(run(canvas.set_frame(sprite3, 3)))
    assert "exists" in out and "no active frame" in out
    assert os.stat(sprite3).st_mtime_ns == before


def test_set_frame_out_of_range(sprite3):
    fails(canvas.set_frame(sprite3, 4), AsepriteError, "Frame index out of range")
