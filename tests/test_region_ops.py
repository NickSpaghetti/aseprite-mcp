"""Behaviour of the region (selection.py) and transform (transform.py) tools,
read back pixel by pixel from the saved file."""
import json

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import animation, canvas, drawing, selection, transform

from test_drawing_ops import coords, pixels

RED, GREEN, BLUE = "#FF0000", "#00FF00", "#0000FF"

_counter = 0


@pytest.fixture
def blank(base_dir):
    """A fresh 16x16 sprite, 2 frames, with an empty top layer 'paint'."""
    global _counter
    _counter += 1
    path = f"{BASE}/region_{_counter}.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    ok(run(canvas.add_layer(path, "paint")))
    ok(run(animation.add_frames(path, 1)))
    ok(run(animation.clear_cel(path, "paint", 2)))
    return path


def dots(path, points, layer="paint", frame=1):
    ok(run(drawing.draw_pixels_at(path, layer, frame, [{"x": x, "y": y, "color": c} for x, y, c in points])))


def info(path):
    return json.loads(run(animation.get_sprite_info(path)))


# ── move / copy / erase ───────────────────────────────────────────────

def test_move_region_cuts_and_pastes(blank):
    dots(blank, [(1, 1, RED), (2, 1, GREEN)])
    ok(run(selection.move_region(blank, "paint", 1, 1, 1, 2, 1, 5, 6)))
    assert pixels(blank) == {(5, 6): "#ff0000ff", (6, 6): "#00ff00ff"}


def test_move_transparent_source_keeps_destination(blank):
    dots(blank, [(1, 1, RED), (6, 6, BLUE)])
    ok(run(selection.move_region(blank, "paint", 1, 0, 0, 2, 2, 5, 5)))     # (0,0) transparent -> lands on (5,5); (1,1) -> (6,6)
    assert pixels(blank) == {(6, 6): "#ff0000ff"}


def test_move_off_canvas_is_discarded(blank):
    dots(blank, [(1, 1, RED), (2, 1, GREEN)])
    ok(run(selection.move_region(blank, "paint", 1, 1, 1, 2, 1, 15, 0)))
    assert pixels(blank) == {(15, 0): "#ff0000ff"}


def test_copy_region_to_other_layer_and_frame(blank):
    dots(blank, [(1, 1, RED)])
    ok(run(canvas.add_layer(blank, "other")))
    ok(run(selection.copy_region(blank, "paint", 1, 0, 0, 3, 3, 10, 10, "other", 2)))
    assert pixels(blank, "other", 2) == {(11, 11): "#ff0000ff"}
    assert pixels(blank) == {(1, 1): "#ff0000ff"}


def test_copy_region_errors(blank):
    fails(selection.copy_region(blank, "NOPE", 1, 0, 0, 1, 1, 0, 0), AsepriteError, "Source layer not found")
    fails(selection.copy_region(blank, "paint", 1, 0, 0, 1, 1, 0, 0, "NOPE"), AsepriteError, "Target layer not found")
    fails(selection.copy_region(blank, "paint", 9, 0, 0, 1, 1, 0, 0), AsepriteError, "Source frame index out of range")
    fails(selection.copy_region(blank, "paint", 1, 0, 0, 1, 1, 0, 0, "", 9), AsepriteError, "Target frame index out of range")
    fails(selection.copy_region(blank, "paint", 2, 0, 0, 1, 1, 0, 0), AsepriteError, "No cel at source layer/frame")


def test_erase_region(blank):
    dots(blank, [(1, 1, RED), (2, 2, RED), (5, 5, RED)])
    ok(run(selection.erase_region(blank, "paint", 1, 0, 0, 3, 3)))
    assert coords(blank) == {(5, 5)}


def test_erase_color_counts_and_tolerance(blank):
    dots(blank, [(1, 1, RED), (2, 2, "#FE0000"), (3, 3, GREEN)])
    out = ok(run(selection.erase_color(blank, "paint", 1, RED, 0)))
    assert "Erased 1 pixels" in out and coords(blank) == {(2, 2), (3, 3)}
    ok(run(selection.erase_color(blank, "paint", 1, RED, 1)))
    assert coords(blank) == {(3, 3)}


def test_region_tools_need_a_cel(blank):
    for call in (selection.move_region(blank, "paint", 2, 0, 0, 1, 1, 2, 2),
                 selection.erase_region(blank, "paint", 2, 0, 0, 1, 1),
                 selection.erase_color(blank, "paint", 2, RED)):
        fails(call, AsepriteError, "No cel")


def test_region_inputs(blank):
    fails(selection.erase_region(blank, "paint", 1, 0, 0, 0, 1), InputError, "must be > 0")
    fails(selection.erase_color(blank, "paint", 1, "red"), InputError, "Invalid color")


# ── flip / rotate (on a canvas-sized cel at 0,0) ──────────────────────

@pytest.fixture
def marked(blank):
    dots(blank, [(1, 2, RED), (3, 0, GREEN)])
    return blank


@pytest.mark.parametrize("direction,expected", [
    ("horizontal", {(14, 2), (12, 0)}),     # x -> 15 - x
    ("vertical", {(1, 13), (3, 15)}),       # y -> 15 - y
])
def test_flip(marked, direction, expected):
    ok(run(transform.flip_layer(marked, "paint", 1, direction)))
    assert coords(marked) == expected


@pytest.mark.parametrize("angle,expected", [
    (90, {(13, 1), (15, 3)}),     # (x, y) -> (15 - y, x)
    (180, {(14, 13), (12, 15)}),  # (x, y) -> (15 - x, 15 - y)
    (270, {(2, 14), (0, 12)}),    # (x, y) -> (y, 15 - x)
])
def test_rotate(marked, angle, expected):
    ok(run(transform.rotate_layer(marked, "paint", 1, angle)))
    assert coords(marked) == expected


def test_flip_and_rotate_need_a_cel(blank):
    fails(transform.flip_layer(blank, "paint", 2), AsepriteError, "No cel")
    fails(transform.rotate_layer(blank, "paint", 2), AsepriteError, "No cel")


# ── resize / crop ─────────────────────────────────────────────────────

def test_resize_scales_content(blank):
    dots(blank, [(1, 1, RED)])
    ok(run(transform.resize_canvas(blank, 32, 32)))
    assert (info(blank)["width"], info(blank)["height"]) == (32, 32)
    assert coords(blank) == {(2, 2), (3, 2), (2, 3), (3, 3)}


def test_crop(blank):
    dots(blank, [(3, 3, RED)])
    ok(run(transform.crop_canvas(blank, 2, 2, 4, 4)))
    assert (info(blank)["width"], info(blank)["height"]) == (4, 4)
    assert coords(blank) == {(1, 1)}


def test_crop_fully_outside_fails(blank):
    fails(transform.crop_canvas(blank, 99, 99, 4, 4), AsepriteError, "fully outside")


# ── behaviour changed by the move to ops (failed before) ──────────────

def _push_off_canvas(path):
    """A 3x3 red block whose cel is moved two pixels off the left edge."""
    ok(run(drawing.draw_rectangle_at(path, "paint", 1, 0, 0, 3, 3, RED, True)))
    ok(run(animation.offset_cel_positions(path, "paint", 1, 1, -2, 0)))
    assert (-2, 0) in coords(path)


@pytest.mark.parametrize("tool", ["move", "copy", "erase"])
def test_region_tools_keep_cel_content_that_hangs_off_canvas(blank, tool):
    _push_off_canvas(blank)
    call = {
        "move": lambda: selection.move_region(blank, "paint", 1, 8, 8, 2, 2, 10, 10),
        "copy": lambda: selection.copy_region(blank, "paint", 1, 0, 0, 1, 1, 10, 10),
        "erase": lambda: selection.erase_region(blank, "paint", 1, 8, 8, 2, 2),
    }[tool]
    ok(run(call()))
    assert (-2, 0) in coords(blank)
