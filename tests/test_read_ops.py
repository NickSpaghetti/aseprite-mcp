"""Behaviour of the read-only tools (pixel_read.py, analysis.py)."""
import json
import os

import pytest
from conftest import BASE, fails, ok, run
from PIL import Image

from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import analysis, animation, canvas, drawing, pixel_read

_counter = 0


@pytest.fixture
def scene(base_dir):
    """8x8, 2 frames. 'Layer 1' (bottom): red at (1,1) on frame 1.
    'top': blue at (1,1) and (2,2) on frame 1, nothing on frame 2."""
    global _counter
    _counter += 1
    path = f"{BASE}/read_{_counter}.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    ok(run(drawing.draw_pixels_at(path, "Layer 1", 1, [{"x": 1, "y": 1, "color": "#FF0000"}])))
    ok(run(canvas.add_layer(path, "top")))
    ok(run(drawing.draw_pixels_at(path, "top", 1, [{"x": 1, "y": 1, "color": "#0000FF"},
                                                   {"x": 2, "y": 2, "color": "#0000FF80"}])))
    ok(run(animation.add_frames(path, 1)))
    ok(run(animation.clear_cel(path, "top", 2)))
    ok(run(animation.clear_cel(path, "Layer 1", 2)))
    return path


# ── single cel reads ──────────────────────────────────────────────────

def test_pixel_color_format(scene):
    assert run(pixel_read.get_pixel_color(scene, 2, 2, "top")) == "#0000ff (r=0, g=0, b=255, a=128)"
    assert run(pixel_read.get_pixel_color(scene, 5, 5, "top")).endswith("a=0)")




def test_pixel_reads_follow_cel_offsets(scene):
    ok(run(animation.offset_cel_positions(scene, "top", 1, 1, 3, 0)))
    assert run(pixel_read.get_pixel_color(scene, 4, 1, "top")).startswith("#0000ff")


def test_pixels_rect_row_major(scene):
    px = json.loads(run(pixel_read.get_pixels_rect(scene, 1, 1, 2, 2, "top")))
    assert [(p["x"], p["y"], p["hex"], p["a"]) for p in px] == [
        (1, 1, "#0000ff", 255), (2, 1, "#000000", 0), (1, 2, "#000000", 0), (2, 2, "#0000ff", 128)]
    assert set(px[0]) == {"x", "y", "hex", "r", "g", "b", "a"}


def test_read_errors(scene):
    fails(pixel_read.get_pixel_color(scene, 0, 0, "NOPE"), AsepriteError, "Layer not found")
    fails(pixel_read.get_pixel_color(scene, 0, 0, "top", 2), AsepriteError, "No cel")
    fails(pixel_read.get_pixel_color(scene, 0, 0, "top", 9), AsepriteError, "Frame index out of range")
    fails(pixel_read.get_pixels_rect(scene, 0, 0, 0, 1), InputError)


# ── composite reads ───────────────────────────────────────────────────

def test_composite_pixel_top_wins_and_blends(scene):
    assert run(pixel_read.get_composite_pixel(scene, 1, 1)).startswith("#0000ff")
    assert run(pixel_read.get_composite_pixel(scene, 0, 0)).endswith("a=0)")
    assert run(pixel_read.get_composite_pixel(scene, 99, 99)).endswith("a=0)")


def test_composite_rect(scene):
    px = json.loads(run(pixel_read.get_composite_rect(scene, 0, 0, 2, 2)))
    assert [(p["x"], p["y"], p["a"]) for p in px] == [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 255)]


# ── analysis ──────────────────────────────────────────────────────────

def test_compare_frames(scene):
    diff = json.loads(run(analysis.compare_frames(scene, 1, 2)))
    assert diff == {"frame_a": 1, "frame_b": 2, "changed_pixels": 2, "total_pixels": 64,
                    "percent_changed": 3.12, "changed_bounds": {"x": 1, "y": 1, "width": 2, "height": 2}}
    same = json.loads(run(analysis.compare_frames(scene, 2, 2)))
    assert same["changed_pixels"] == 0 and "changed_bounds" not in same
    fails(analysis.compare_frames(scene, 1, 9), AsepriteError, "out of range")


def test_color_stats(scene):
    # Colours are counted by RGB; the half-transparent blue counts as blue.
    ok(run(drawing.draw_pixels_at(scene, "Layer 1", 1, [{"x": x, "y": x, "color": "#FF0000"} for x in (4, 5, 6)])))
    stats = json.loads(run(analysis.get_color_stats(scene, 1)))
    assert stats["unique_colors"] == 2 and stats["opaque_pixels"] == 5
    assert stats["top_colors"] == [{"color": "#FF0000", "count": 3}, {"color": "#0000FF", "count": 2}]
    assert len(json.loads(run(analysis.get_color_stats(scene, 1, 1)))["top_colors"]) == 1


def test_onion_skin_ghost_blend(scene, base_dir):
    out = f"{base_dir}/onion_{os.path.basename(scene)}.png"
    ok(run(analysis.render_onion_skin(scene, 2, out, before=1, after=0, scale=2, ghost_opacity=100)))
    img = Image.open(out).convert("RGBA")
    assert img.size == (16, 16)
    # frame 2 is empty; frame 1's blue at (1,1) ghosts over white at 100/255
    r, g, b, _ = img.getpixel((2, 2))
    expected = round(255 * (1 - 100 / 255))
    assert abs(r - expected) <= 1 and abs(g - expected) <= 1 and b == 255
    assert img.getpixel((0, 0))[:3] == (255, 255, 255)


# ── behaviour changed by the move to ops (failed before) ──────────────

@pytest.fixture
def hidden_top(scene):
    ok(run(animation.set_layer_visibility(scene, "top", False)))
    return scene


def test_composite_ignores_hidden_layers(hidden_top):
    assert run(pixel_read.get_composite_pixel(hidden_top, 1, 1)).startswith("#ff0000")
    px = json.loads(run(pixel_read.get_composite_rect(hidden_top, 2, 2, 1, 1)))
    assert px[0]["a"] == 0


def test_analysis_ignores_hidden_layers(hidden_top, base_dir):
    assert json.loads(run(analysis.compare_frames(hidden_top, 1, 2)))["changed_pixels"] == 1
    stats = json.loads(run(analysis.get_color_stats(hidden_top, 1)))
    assert stats["top_colors"] == [{"color": "#FF0000", "count": 1}]
    out = f"{base_dir}/onion_hidden_{os.path.basename(hidden_top)}.png"
    ok(run(analysis.render_onion_skin(hidden_top, 1, out, before=0, after=0, scale=1)))
    assert Image.open(out).convert("RGB").getpixel((1, 1)) == (255, 0, 0)
