"""Behaviour of every drawing tool, read back pixel by pixel from the saved file.

Shapes are checked against hand-worked pixel sets (Bresenham steps, inclusive
rectangle corners, square brushes) rather than a recorded previous run.
"""
import json

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.commands import run_script
from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import animation, canvas, drawing

RED, GREEN = "#FF0000", "#00FF00"

# Opaque pixels of one layer/frame, in sprite coordinates, as {"x,y": "#rrggbbaa"}.
PIXELS = """
local spr = app.activeSprite
local layer
for _, l in ipairs(spr.layers) do if l.name == "%s" then layer = l end end
local out = {}
local cel = layer:cel(%d)
if cel then
  for it in cel.image:pixels() do
    local v = it()
    local a = app.pixelColor.rgbaA(v)
    if a > 0 then
      out[(it.x + cel.position.x) .. "," .. (it.y + cel.position.y)] = string.format("#%%02x%%02x%%02x%%02x",
        app.pixelColor.rgbaR(v), app.pixelColor.rgbaG(v), app.pixelColor.rgbaB(v), a)
    end
  end
end
print(json.encode(out))
"""


def pixels(path, layer="paint", frame=1):
    raw = json.loads(run(run_script(PIXELS % (layer, frame), path))) or {}
    return {tuple(map(int, k.split(","))): v for k, v in raw.items()}


def coords(path, layer="paint", frame=1):
    return set(pixels(path, layer, frame))


_counter = 0


@pytest.fixture
def blank(base_dir):
    """A fresh 16x16 sprite whose top layer 'paint' has no cel yet."""
    global _counter
    _counter += 1
    path = f"{BASE}/draw_{_counter}.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    ok(run(canvas.add_layer(path, "paint")))
    return path


def square(cx, cy, r):
    return {(x, y) for x in range(cx - r, cx + r + 1) for y in range(cy - r, cy + r + 1)}


# ── explicit layer/frame tools ────────────────────────────────────────

def test_pixels_at(blank):
    ok(run(drawing.draw_pixels_at(blank, "paint", 1, [
        {"x": 1, "y": 2, "color": RED}, {"x": 3, "y": 4, "color": "#00FF0080"}])))
    assert pixels(blank) == {(1, 2): "#ff0000ff", (3, 4): "#00ff0080"}


def test_line_at_bresenham(blank):
    ok(run(drawing.draw_line_at(blank, "paint", 1, 0, 0, 4, 2, RED)))
    assert coords(blank) == {(0, 0), (1, 1), (2, 1), (3, 2), (4, 2)}


def test_line_at_thick_uses_a_square_brush(blank):
    ok(run(drawing.draw_line_at(blank, "paint", 1, 5, 5, 5, 5, RED, thickness=3)))
    assert coords(blank) == square(5, 5, 1)


def test_path(blank):
    ok(run(drawing.draw_path(blank, "paint", 1, [{"x": 0, "y": 0}, {"x": 3, "y": 0}, {"x": 3, "y": 2}], RED)))
    assert coords(blank) == {(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2)}


def test_rectangle_outline_and_fill(blank):
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 2, 3, 4, 3, RED)))
    outline = coords(blank)
    assert outline == {(x, y) for x in range(2, 6) for y in range(3, 6)} - {(3, 4), (4, 4)}
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 2, 3, 4, 3, RED, fill=True)))
    assert coords(blank) == {(x, y) for x in range(2, 6) for y in range(3, 6)}


def test_circle_and_ellipse_fill(blank):
    ok(run(drawing.draw_circle_at(blank, "paint", 1, 8, 8, 3, RED, fill=True)))
    c = coords(blank)
    assert (8, 8) in c and (5, 8) in c and (11, 8) in c and (5, 5) not in c
    ok(run(drawing.draw_ellipse_at(blank, "paint", 1, 8, 2, 4, 1, GREEN, fill=True)))
    assert pixels(blank)[(8, 2)] == "#00ff00ff"


def test_fill_area_at_stays_inside_an_outline(blank):
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 2, 2, 6, 6, RED)))
    ok(run(drawing.fill_area_at(blank, "paint", 1, 4, 4, GREEN)))
    p = pixels(blank)
    assert p[(4, 4)] == "#00ff00ff" and p[(2, 2)] == "#ff0000ff" and (0, 0) not in p


def test_polygon_fill_and_outline(blank):
    tri = [{"x": 2, "y": 2}, {"x": 10, "y": 2}, {"x": 2, "y": 10}]
    ok(run(drawing.draw_polygon(blank, "paint", 1, tri, RED)))
    outline = coords(blank)
    assert (2, 2) in outline and (10, 2) in outline and (4, 4) not in outline
    ok(run(drawing.draw_polygon(blank, "paint", 1, tri, RED, fill=True)))
    assert (4, 4) in coords(blank)


def test_gradient_endpoints(blank):
    ok(run(drawing.apply_gradient_rect(blank, "paint", 1, 0, 0, 3, 1, "#000000", "#FF0000")))
    p = pixels(blank)
    assert (p[(0, 0)], p[(1, 0)], p[(2, 0)]) == ("#000000ff", "#800000ff", "#ff0000ff")


def test_offcanvas_writes_are_dropped_without_error(blank):
    ok(run(drawing.draw_pixels_at(blank, "paint", 1, [{"x": -3, "y": 1, "color": RED}, {"x": 1, "y": 1, "color": RED}])))
    assert coords(blank) == {(1, 1)}


def test_hostile_layer_name(blank):
    name = 'p "x" ]] --\n'
    ok(run(canvas.add_layer(blank, name)))
    ok(run(drawing.draw_rectangle_at(blank, name, 1, 0, 0, 2, 2, RED, fill=True)))


def test_missing_layer_and_frame(blank):
    fails(drawing.draw_rectangle_at(blank, "NOPE", 1, 0, 0, 2, 2, RED), AsepriteError, "Layer not found")
    fails(drawing.draw_line_at(blank, "paint", 9, 0, 0, 2, 2, RED), AsepriteError, "Frame index out of range")


def test_bad_colours_are_rejected(blank):
    fails(drawing.draw_line_at(blank, "paint", 1, 0, 0, 2, 2, "red"), InputError, "Invalid color value")
    fails(drawing.apply_gradient_rect(blank, "paint", 1, 0, 0, 2, 2, "#000", "nope"), InputError, "Invalid color_end")









# ── behaviour changed by the move to ops (these failed before) ────────

@pytest.mark.parametrize("bad", ["3", 1.5, True, None, '0, 0, Color(0,0,0)) print("x") img:putPixel(0'])
def test_non_integer_coordinates_are_rejected(blank, bad):
    fails(drawing.draw_pixels_at(blank, "paint", 1, [{"x": bad, "y": 0, "color": RED}]), InputError, "integer")
    fails(drawing.draw_path(blank, "paint", 1, [{"x": 0, "y": 0}, {"x": bad, "y": 1}]), InputError, "integer")


def test_writes_beyond_a_small_offset_cel_are_kept(blank):
    # A 2x2 cel at (6,6); drawing at (1,1) used to fall outside its image and vanish.
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 6, 6, 2, 2, RED, fill=True)))
    ok(run(animation.set_cel_position(blank, "paint", 1, 6, 6)))
    ok(run(drawing.draw_pixels_at(blank, "paint", 1, [{"x": 1, "y": 1, "color": GREEN}])))
    ok(run(drawing.draw_line_at(blank, "paint", 1, 0, 14, 2, 14, GREEN)))
    assert {(1, 1), (0, 14), (1, 14), (2, 14)} <= coords(blank)


def test_painting_keeps_cel_content_that_hangs_off_canvas(blank):
    # A cel pushed partly off-canvas used to be cropped by normalize_cel.
    ok(run(drawing.draw_rectangle_at(blank, "paint", 1, 0, 0, 4, 4, RED, fill=True)))
    ok(run(animation.offset_cel_positions(blank, "paint", 1, 1, -2, 0)))
    before = coords(blank)
    assert (-2, 0) in before
    ok(run(drawing.draw_path(blank, "paint", 1, [{"x": 10, "y": 10}, {"x": 11, "y": 10}], GREEN)))
    assert before <= coords(blank)


@pytest.mark.parametrize("tool", ["pixels", "line", "rectangle", "circle", "ellipse", "fill", "polygon", "path", "gradient"])
def test_no_cel_and_no_create_fails(blank, tool):
    common = (blank, "paint", 1)
    call = {
        "pixels": lambda: drawing.draw_pixels_at(*common, [{"x": 1, "y": 1, "color": RED}], False),
        "line": lambda: drawing.draw_line_at(*common, 0, 0, 2, 2, RED, 1, False),
        "rectangle": lambda: drawing.draw_rectangle_at(*common, 0, 0, 2, 2, RED, False, False),
        "circle": lambda: drawing.draw_circle_at(*common, 4, 4, 2, RED, False, False),
        "ellipse": lambda: drawing.draw_ellipse_at(*common, 4, 4, 2, 1, RED, False, False),
        "fill": lambda: drawing.fill_area_at(*common, 1, 1, RED, False),
        "polygon": lambda: drawing.draw_polygon(*common, [{"x": 0, "y": 0}, {"x": 3, "y": 0}, {"x": 0, "y": 3}], RED, False, False),
        "path": lambda: drawing.draw_path(*common, [{"x": 0, "y": 0}, {"x": 3, "y": 0}], RED, 1, False),
        "gradient": lambda: drawing.apply_gradient_rect(*common, 0, 0, 2, 2, "#000", "#FFF", True, False),
    }[tool]
    fails(call(), AsepriteError, "No cel")
    assert coords(blank) == set()
