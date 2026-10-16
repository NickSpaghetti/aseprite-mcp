"""Behaviour of the effect tools (fx.py, native_fx.py), read back from the saved file.

Expectations are worked out by hand: outline neighbour sets, Bayer 4x4
thresholds, HSL round trips, and pixel-exact inversion.
"""
import json

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.commands import run_script
from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import animation, canvas, drawing, fx, native_fx

from test_drawing_ops import pixels, coords

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]

_counter = 0


@pytest.fixture
def blank(base_dir):
    """A fresh 16x16 sprite whose top layer 'paint' has no cel yet."""
    global _counter
    _counter += 1
    path = f"{BASE}/fx_{_counter}.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    ok(run(canvas.add_layer(path, "paint")))
    return path


def dot(path, x, y, color="#FF0000", layer="paint"):
    ok(run(drawing.draw_pixels_at(path, layer, 1, [{"x": x, "y": y, "color": color}])))


# ── outline_cel ───────────────────────────────────────────────────────

def test_outline_four_neighbours(blank):
    dot(blank, 5, 5)
    ok(run(fx.outline_cel(blank, "paint", 1, "#000000")))
    p = pixels(blank)
    assert {k for k, v in p.items() if v == "#000000ff"} == {(4, 5), (6, 5), (5, 4), (5, 6)}


def test_outline_with_diagonals(blank):
    dot(blank, 5, 5)
    ok(run(fx.outline_cel(blank, "paint", 1, "#000000", include_diagonals=True)))
    assert coords(blank) == {(x, y) for x in (4, 5, 6) for y in (4, 5, 6)}


def test_outline_needs_a_cel(blank):
    fails(fx.outline_cel(blank, "paint", 1), AsepriteError, "No cel")


# ── replace_color / adjust_hsl ────────────────────────────────────────

def test_replace_color_exact_and_counted(blank):
    dot(blank, 1, 1, "#FF000080")
    dot(blank, 2, 2, "#FE0000")
    out = ok(run(fx.replace_color(blank, "paint", 1, "#FF0000", "#0000FF")))
    assert "Replaced 1 pixels" in out
    p = pixels(blank)
    assert (p[(1, 1)], p[(2, 2)]) == ("#0000ff80", "#fe0000ff")      # alpha kept; near-miss untouched


def test_replace_color_tolerance(blank):
    dot(blank, 2, 2, "#FE0000")
    ok(run(fx.replace_color(blank, "paint", 1, "#FF0000", "#0000FF", 1)))
    assert pixels(blank)[(2, 2)] == "#0000ffff"


def test_adjust_hsl_hue_and_saturation(blank):
    dot(blank, 1, 1, "#FF0000")
    dot(blank, 2, 2, "#FF000080")
    ok(run(fx.adjust_hsl(blank, "paint", 1, 120, 0, 0)))
    assert (pixels(blank)[(1, 1)], pixels(blank)[(2, 2)]) == ("#00ff00ff", "#00ff0080")
    ok(run(fx.adjust_hsl(blank, "paint", 1, 0, -100, 0)))
    assert pixels(blank)[(1, 1)] == "#808080ff"          # s=0, l=.5 -> round(127.5) = 128


def test_effects_need_a_cel(blank):
    fails(fx.replace_color(blank, "paint", 1, "#FF0000", "#0000FF"), AsepriteError, "No cel")
    fails(fx.adjust_hsl(blank, "paint", 1, 10), AsepriteError, "No cel")


# ── dithering ─────────────────────────────────────────────────────────

def test_dither_gradient_vertical(blank):
    ok(run(fx.apply_dither_gradient(blank, "paint", 1, 0, 0, 1, 4, "#000000", "#FFFFFF")))
    # f = row/3; threshold = (BAYER[row][0] + .5) / 16 -> black, black, white, white
    p = pixels(blank)
    assert [p[(0, y)] for y in range(4)] == ["#000000ff", "#000000ff", "#ffffffff", "#ffffffff"]


def test_dither_pattern_density(blank):
    ok(run(fx.apply_dither_pattern(blank, "paint", 1, 0, 0, 4, 4, "#000000", "#FFFFFF", 0.5)))
    p = pixels(blank)
    white = {(x, y) for y in range(4) for x in range(4) if 0.5 > (BAYER[y][x] + 0.5) / 16}
    assert {k for k, v in p.items() if v == "#ffffffff"} == white and len(white) == 8


def test_dither_ignores_colour_alpha(blank):
    ok(run(fx.apply_dither_pattern(blank, "paint", 1, 0, 0, 1, 1, "#00000010", "#FFFFFF10", 0.0)))
    assert pixels(blank)[(0, 0)] == "#000000ff"


def test_dither_without_create_needs_a_cel(blank):
    fails(fx.apply_dither_pattern(blank, "paint", 1, 0, 0, 2, 2, "#000", "#FFF", 0.5, False), AsepriteError, "No cel")


# ── native commands ───────────────────────────────────────────────────

def test_invert_exact(blank):
    dot(blank, 3, 3, "#204060")
    ok(run(native_fx.invert_colors(blank, "paint", 1)))
    assert pixels(blank)[(3, 3)] == "#dfbf9fff"


def test_invert_region_only(blank):
    dot(blank, 1, 1, "#000000")
    dot(blank, 8, 8, "#000000")
    ok(run(native_fx.invert_colors(blank, "paint", 1, 0, 0, 4, 4)))
    p = pixels(blank)
    assert (p[(1, 1)], p[(8, 8)]) == ("#ffffffff", "#000000ff")


def test_native_outline(blank):
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 4, 4, 4, 4, "#FF0000", True)))
    ok(run(native_fx.outline_native(blank, "paint", 1, "#00FF00", "outside", "square")))
    assert pixels(blank)[(3, 3)] == "#00ff00ff"


def test_native_hsl_and_brightness_change_pixels(blank):
    dot(blank, 3, 3, "#804020")
    ok(run(native_fx.adjust_hsl_native(blank, "paint", 1, 0, 0, 50)))
    lighter = pixels(blank)[(3, 3)]
    assert lighter != "#804020ff"
    ok(run(native_fx.adjust_brightness_contrast(blank, "paint", 1, -50, 0)))
    assert pixels(blank)[(3, 3)] != lighter


def test_convolution_blur_spreads(blank):
    dot(blank, 8, 8, "#FFFFFF")
    ok(run(native_fx.apply_convolution(blank, "blur-3x3", "paint", 1)))
    assert len(coords(blank)) > 1


def test_extract_palette(blank):
    dot(blank, 1, 1, "#FF0000")
    dot(blank, 2, 2, "#00FF00")
    result = json.loads(ok(run(native_fx.extract_palette(blank, 4))))
    assert result["count"] == len(result["colors"]) and "#FF0000" in result["colors"]




def test_native_missing_layer_and_frame(blank):
    fails(native_fx.invert_colors(blank, "NOPE", 1), AsepriteError, "Layer not found")
    fails(native_fx.invert_colors(blank, "paint", 9), AsepriteError, "Frame index out of range")


def test_bad_inputs_rejected(blank):
    fails(native_fx.outline_native(blank, "paint", 1, "green"), InputError)
    fails(fx.replace_color(blank, "paint", 1, "#F00", "blue"), InputError)


# ── behaviour changed by the move to ops (these failed before) ────────

def test_outline_keeps_cel_content_that_hangs_off_canvas(blank):
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 0, 0, 3, 3, "#FF0000", True)))
    ok(run(animation.offset_cel_positions(blank, "paint", 1, 1, -2, 0)))
    before = coords(blank)
    assert (-2, 0) in before
    ok(run(fx.outline_cel(blank, "paint", 1, "#000000")))
    assert before <= coords(blank)


def test_dither_keeps_cel_content_that_hangs_off_canvas(blank):
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 0, 0, 3, 3, "#FF0000", True)))
    ok(run(animation.offset_cel_positions(blank, "paint", 1, 1, -2, 0)))
    ok(run(fx.apply_dither_pattern(blank, "paint", 1, 8, 8, 2, 2, "#000", "#FFF", 0.5)))
    assert (-2, 0) in coords(blank)
