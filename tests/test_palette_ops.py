"""Behaviour of the palette tools, read back from the saved file."""
import colorsys
import json

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import animation, canvas, drawing, palette, pixel_read

from test_drawing_ops import pixels

_counter = 0


@pytest.fixture
def blank(base_dir):
    """A fresh 8x8 RGB sprite with 2 frames and an empty top layer 'paint'."""
    global _counter
    _counter += 1
    path = f"{BASE}/pal_{_counter}.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    ok(run(canvas.add_layer(path, "paint")))
    ok(run(animation.add_frames(path, 1)))
    return path


def dot(path, x, y, color, layer="paint", frame=1):
    ok(run(drawing.draw_pixels_at(path, layer, frame, [{"x": x, "y": y, "color": color}])))


def hex_at(path, x, y, layer, frame=1):
    """#rrggbbaa via the layer-path-aware reader (works for grouped layers)."""
    out = run(pixel_read.get_pixel_color(path, x, y, layer, frame))
    r, g, b, a = (int(out.split(f"{k}=")[1].split(",")[0].rstrip(")")) for k in "rgba")
    return f"#{r:02x}{g:02x}{b:02x}{a:02x}"


# ── get / set / presets ───────────────────────────────────────────────

def test_set_then_get_palette(blank):
    ok(run(palette.set_palette(blank, ["#ff0000", "#0F0", "#0000FF80"])))
    assert json.loads(run(palette.get_palette(blank))) == ["#FF0000", "#00FF00", "#0000FF"]


def test_set_palette_rejects_bad_colour(blank):
    fails(palette.set_palette(blank, ["#FF0000", "red"]), InputError)
    fails(palette.set_palette(blank, []), InputError, "cannot be empty")


def test_apply_preset(blank):
    out = ok(run(palette.apply_palette_preset(blank, "gameboy")))
    assert "(4 colors)" in out
    assert json.loads(run(palette.get_palette(blank))) == palette.PALETTE_PRESETS["gameboy"]


# ── remap ─────────────────────────────────────────────────────────────

def test_remap_across_frames_keeps_alpha(blank):
    dot(blank, 1, 1, "#FF000080", frame=1)
    dot(blank, 2, 2, "#FF0000", frame=2)
    dot(blank, 3, 3, "#00FF00", frame=2)
    ok(run(palette.remap_colors_in_cel_range(blank, "paint", 1, 2, [{"from": "#FF0000", "to": "#0000FF"}])))
    assert pixels(blank, frame=1)[(1, 1)] == "#0000ff80"
    assert pixels(blank, frame=2)[(2, 2)] == "#0000ffff"
    assert pixels(blank, frame=2)[(3, 3)] == "#00ff00ff"


def test_remap_first_matching_mapping_wins(blank):
    dot(blank, 1, 1, "#FF0000")
    ok(run(palette.remap_colors_in_cel_range(blank, "paint", 1, 1, [
        {"from": "#FF0000", "to": "#0000FF"}, {"from": "#FF0000", "to": "#00FF00"}])))
    assert pixels(blank)[(1, 1)] == "#0000ffff"


def test_remap_creates_missing_cels_from_source(blank):
    dot(blank, 1, 1, "#FF0000", frame=1)
    ok(run(animation.clear_cel(blank, "paint", 2)))
    ok(run(palette.remap_colors_in_cel_range(blank, "paint", 1, 2, [{"from": "#FF0000", "to": "#0000FF"}],
                                             create_missing_cels=True, source_frame_index=1)))
    assert pixels(blank, frame=2)[(1, 1)] == "#0000ffff"


def test_remap_errors(blank):
    m = [{"from": "#FF0000", "to": "#0000FF"}]
    fails(palette.remap_colors_in_cel_range(blank, "paint", 1, 9, m), AsepriteError, "out of bounds")
    fails(palette.remap_colors_in_cel_range(blank, "NOPE", 1, 1, m), AsepriteError, "Layer not found")
    fails(palette.remap_colors_in_cel_range(blank, "paint", 1, 1, m, source_frame_index=9),
          AsepriteError, "Source frame out of range")
    fails(palette.remap_colors_in_cel_range(blank, "paint", 1, 1, [{"from": "#FF0000"}]), InputError)


# ── quantize ──────────────────────────────────────────────────────────

def test_quantize_snaps_to_nearest_and_counts(blank):
    ok(run(palette.set_palette(blank, ["#000000", "#FFFFFF"])))
    dot(blank, 1, 1, "#303030")
    dot(blank, 2, 2, "#D0D0D080")
    dot(blank, 3, 3, "#FFFFFF")
    out = ok(run(palette.quantize_to_palette(blank, "paint", 1, 1)))
    assert "Quantized 2 pixels" in out
    p = pixels(blank)
    assert (p[(1, 1)], p[(2, 2)], p[(3, 3)]) == ("#000000ff", "#ffffff80", "#ffffffff")


def test_quantize_one_layer_only(blank):
    ok(run(palette.set_palette(blank, ["#000000", "#FFFFFF"])))
    dot(blank, 1, 1, "#303030")
    dot(blank, 1, 1, "#303030", layer="Layer 1")
    ok(run(palette.quantize_to_palette(blank, "paint")))
    assert pixels(blank, "Layer 1")[(1, 1)] == "#303030ff"


def test_quantize_frame_range(blank):
    fails(palette.quantize_to_palette(blank, "", 2, 5), AsepriteError, "out of bounds")


# ── colour mode ───────────────────────────────────────────────────────

@pytest.mark.parametrize("mode,reported", [("indexed", "indexed"), ("grayscale", "gray"), ("rgb", "rgb")])
def test_set_color_mode(blank, mode, reported):
    ok(run(palette.set_color_mode(blank, mode)))
    assert json.loads(run(animation.get_sprite_info(blank)))["color_mode"] == reported


# ── ramp (pure Python) ────────────────────────────────────────────────

def test_ramp_is_centred_on_the_base_and_runs_dark_to_light():
    ramp = json.loads(run(palette.generate_color_ramp("#D04648", 5)))
    assert len(ramp) == 5 and ramp[2] == "#D04648"
    lightness = [colorsys.rgb_to_hls(*(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)))[1] for c in ramp]
    assert lightness == sorted(lightness)


# ── behaviour changed by the move to ops (failed before) ──────────────

def test_quantize_all_layers_includes_layers_in_groups(blank):
    ok(run(palette.set_palette(blank, ["#000000", "#FFFFFF"])))
    ok(run(canvas.add_group(blank, "grp")))
    ok(run(canvas.add_layer(blank, "arm", group="grp")))
    dot(blank, 1, 1, "#303030", layer="grp/arm")
    ok(run(palette.quantize_to_palette(blank)))
    assert hex_at(blank, 1, 1, "grp/arm") == "#000000ff"
