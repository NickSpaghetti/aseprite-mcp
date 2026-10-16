"""Behaviour of the slice and tilemap tools, read back from the saved file."""
import json

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.commands import run_script
from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import canvas, slices, tilemap

_counter = 0


@pytest.fixture
def blank(base_dir):
    """A fresh 16x16 sprite."""
    global _counter
    _counter += 1
    path = f"{BASE}/tile_{_counter}.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    return path


@pytest.fixture
def tiled(blank):
    """blank with an 8x8 tilemap layer 'map' (a 2x2 grid) holding one tile."""
    ok(run(tilemap.create_tilemap_layer(blank, "map", 8, 8)))
    ok(run(tilemap.draw_on_tile(blank, "map", 1, [{"x": 0, "y": 0, "color": "#FF0000"}])))
    return blank


TILE_PIXEL = """
local layer
for _, l in ipairs(app.activeSprite.layers) do if l.name == "map" then layer = l end end
local v = layer.tileset:tile(%d).image:getPixel(%d, %d)
local pc = app.pixelColor
print(string.format("#%%02x%%02x%%02x%%02x", pc.rgbaR(v), pc.rgbaG(v), pc.rgbaB(v), pc.rgbaA(v)))
"""


def tile_pixel(path, index, x, y):
    return run(run_script(TILE_PIXEL % (index, x, y), path)).strip()


def slice_list(path):
    return {s["name"]: s for s in json.loads(run(slices.list_slices(path)))}


# ── slices ────────────────────────────────────────────────────────────

def test_slice_lifecycle(blank):
    ok(run(slices.create_slice(blank, "btn", 1, 2, 10, 12)))
    assert slice_list(blank)["btn"] == {"name": "btn", "x": 1, "y": 2, "width": 10, "height": 12}
    ok(run(slices.set_slice_center(blank, "btn", 2, 2, 6, 8)))
    ok(run(slices.set_slice_pivot(blank, "btn", 5, 6)))
    s = slice_list(blank)["btn"]
    assert s["center"] == {"x": 2, "y": 2, "width": 6, "height": 8} and s["pivot"] == {"x": 5, "y": 6}
    ok(run(slices.delete_slice(blank, "btn")))
    assert slice_list(blank) == {}


def test_slice_errors(blank):
    ok(run(slices.create_slice(blank, "btn", 0, 0, 4, 4)))
    fails(slices.create_slice(blank, "btn", 0, 0, 4, 4), AsepriteError, "already exists")
    for call in (slices.set_slice_center(blank, "nope", 0, 0, 1, 1), slices.set_slice_pivot(blank, "nope", 0, 0),
                 slices.delete_slice(blank, "nope")):
        fails(call, AsepriteError, "Slice not found")
    fails(slices.create_slice(blank, "", 0, 0, 4, 4), InputError, "cannot be empty")
    fails(slices.create_slice(blank, "x", 0, 0, 0, 4), InputError, "must be > 0")


# ── tilemaps ──────────────────────────────────────────────────────────

def test_tilemap_info(tiled):
    assert json.loads(run(tilemap.get_tilemap_info(tiled, "map"))) == {
        "tile_width": 8, "tile_height": 8, "tile_count": 1, "map_cols": 2, "map_rows": 2}


def test_create_tilemap_layer_rejects_a_taken_top_level_name(tiled):
    fails(tilemap.create_tilemap_layer(tiled, "map", 8, 8), AsepriteError, "already exists")


def test_draw_on_tile_and_append(tiled):
    assert tile_pixel(tiled, 1, 0, 0) == "#ff0000ff"
    ok(run(tilemap.draw_on_tile(tiled, "map", 2, [{"x": 7, "y": 7, "color": "#00FF00"}])))
    assert tile_pixel(tiled, 2, 7, 7) == "#00ff00ff"
    assert json.loads(run(tilemap.get_tilemap_info(tiled, "map")))["tile_count"] == 2


def test_draw_on_tile_errors(tiled):
    fails(tilemap.draw_on_tile(tiled, "map", 5, [{"x": 0, "y": 0, "color": "#FF0000"}]), AsepriteError, "out of range")
    fails(tilemap.draw_on_tile(tiled, "map", 0, [{"x": 0, "y": 0, "color": "#FF0000"}]), InputError, "reserved")
    fails(tilemap.draw_on_tile(tiled, "Layer 1", 1, [{"x": 0, "y": 0, "color": "#FF0000"}]), AsepriteError,
          "not a tilemap")


def test_set_get_and_clear_tiles(tiled):
    ok(run(tilemap.set_tiles(tiled, "map", 1, [{"col": 1, "row": 0, "tile_index": 1}])))
    get = lambda c, r: json.loads(run(tilemap.get_tile_at(tiled, "map", 1, c, r)))["tile_index"]
    assert (get(1, 0), get(0, 0)) == (1, 0)
    ok(run(tilemap.set_tiles(tiled, "map", 1, [{"col": 1, "row": 0, "tile_index": 0}])))
    assert get(1, 0) == 0


def test_set_tiles_validates_everything_before_writing(tiled):
    fails(tilemap.set_tiles(tiled, "map", 1, [{"col": 0, "row": 0, "tile_index": 1},
                                              {"col": 5, "row": 0, "tile_index": 1}]),
          AsepriteError, "outside the 2x2 map")
    assert json.loads(run(tilemap.get_tile_at(tiled, "map", 1, 0, 0)))["tile_index"] == 0
    fails(tilemap.set_tiles(tiled, "map", 1, [{"col": 0, "row": 0, "tile_index": 7}]), AsepriteError, "out of range")


# ── behaviour changed by the move to ops (failed before) ──────────────

def test_list_slices_is_valid_json_for_any_name(blank):
    name = 'two\nlines "quoted" \\'
    ok(run(slices.create_slice(blank, name, 0, 0, 4, 4)))
    assert name in slice_list(blank)


@pytest.mark.parametrize("color,expected", [("#0F0", "#00ff00ff"), ("#00FF0080", "#00ff0080")])
def test_tile_colours_parse_like_every_other_tool(tiled, color, expected):
    ok(run(tilemap.draw_on_tile(tiled, "map", 1, [{"x": 1, "y": 1, "color": color}])))
    assert tile_pixel(tiled, 1, 1, 1) == expected


@pytest.mark.parametrize("bad", ["3", 1.5])
def test_tile_coordinates_must_be_integers(tiled, bad):
    fails(tilemap.draw_on_tile(tiled, "map", 1, [{"x": bad, "y": 0, "color": "#FF0000"}]), InputError, "integer")
    fails(tilemap.set_tiles(tiled, "map", 1, [{"col": bad, "row": 0, "tile_index": 1}]), InputError, "integer")
