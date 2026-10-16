"""Tools called without a layer use the sprite's only image layer.

With several image layers they fail and ask for the layer by name, instead of
silently picking the bottom one (P03).
"""
import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.errors import AsepriteError
from aseprite_mcp.tools import animation, canvas, drawing, native_fx, pixel_read, text

from test_drawing_ops import coords, pixels
from test_text import bitmap_font  # noqa: F401  (fixture)

_counter = 0


def _new_sprite(kind):
    global _counter
    _counter += 1
    path = f"{BASE}/target_{kind}_{_counter}.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    return path


@pytest.fixture
def single(base_dir):
    """8x8 with only 'Layer 1' (a new sprite's Layer 1 already has an empty cel)."""
    return _new_sprite("single")


@pytest.fixture
def several(base_dir):
    """8x8 with 'Layer 1' and 'top'; a separate file from `single`."""
    path = _new_sprite("several")
    ok(run(canvas.add_layer(path, "top")))
    return path


def _legacy_calls(path):
    return {
        "draw_pixels": lambda: drawing.draw_pixels(path, [{"x": 1, "y": 1, "color": "#FF0000"}]),
        "draw_line": lambda: drawing.draw_line(path, 0, 4, 2, 4, "#FF0000"),
        "draw_rectangle": lambda: drawing.draw_rectangle(path, 0, 6, 2, 2, "#FF0000", True),
        "draw_circle": lambda: drawing.draw_circle(path, 5, 5, 1, "#FF0000", True),
        "fill_area": lambda: drawing.fill_area(path, 0, 0, "#FF0000"),
    }


LEGACY = list(_legacy_calls("").keys())


@pytest.mark.parametrize("tool", LEGACY)
def test_legacy_drawing_needs_a_single_layer(several, tool):
    fails(_legacy_calls(several)[tool](), AsepriteError, "name the layer")
    assert coords(several, "Layer 1") == set() and coords(several, "top") == set()


@pytest.mark.parametrize("tool", LEGACY)
def test_legacy_drawing_on_a_single_layer_sprite(single, tool):
    ok(run(_legacy_calls(single)[tool]()))
    assert coords(single, "Layer 1")


def test_native_filters(several, single):
    fails(native_fx.invert_colors(several, "", 1), AsepriteError, "name the layer")
    ok(run(drawing.draw_pixels_at(single, "Layer 1", 1, [{"x": 1, "y": 1, "color": "#000000"}])))
    ok(run(native_fx.invert_colors(single, "", 1)))
    assert pixels(single, "Layer 1")[(1, 1)] == "#ffffffff"


def test_pixel_reads(several, single):
    fails(pixel_read.get_pixel_color(several, 1, 1), AsepriteError, "name the layer")
    fails(pixel_read.get_pixels_rect(several, 0, 0, 2, 2), AsepriteError, "name the layer")
    ok(run(drawing.draw_pixels_at(single, "Layer 1", 1, [{"x": 1, "y": 1, "color": "#FF0000"}])))
    assert run(pixel_read.get_pixel_color(single, 1, 1)).startswith("#ff0000")


def test_text(several, single, bitmap_font):
    fails(text.draw_text(several, "A", 0, 0, bitmap_font), AsepriteError, "name the layer")
    ok(run(text.draw_text(single, "A", 0, 0, bitmap_font)))
    assert coords(single, "Layer 1")


def test_groups_do_not_count_as_layers(single):
    ok(run(canvas.add_group(single, "grp")))
    ok(run(drawing.draw_pixels(single, [{"x": 2, "y": 2, "color": "#FF0000"}])))
    assert (2, 2) in coords(single, "Layer 1")


def test_the_message_names_the_layers(several):
    message = fails(drawing.draw_pixels(several, [{"x": 1, "y": 1, "color": "#FF0000"}]), AsepriteError)
    assert "2 layers" in message and "Layer 1" in message and "top" in message


def test_the_single_layer_still_needs_a_cel(single):
    ok(run(animation.clear_cel(single, "Layer 1", 1)))
    fails(drawing.draw_pixels(single, [{"x": 1, "y": 1, "color": "#FF0000"}]), AsepriteError, "No cel")
