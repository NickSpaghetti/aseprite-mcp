"""Behaviour of the export (export.py) and text (text.py) tools, read back from the files written."""
import json
import os
import time

import pytest
from conftest import BASE, fails, ok, run
from PIL import Image

from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import animation, canvas, drawing, export, text

from test_drawing_ops import coords, pixels
from test_text import bitmap_font  # noqa: F401  (fixture)

_counter = 0


@pytest.fixture
def two_frames(base_dir):
    """8x8, 2 frames: red dot at (1,1) on frame 1, green dot at (2,2) on frame 2, layer 'paint'."""
    global _counter
    _counter += 1
    path = f"{BASE}/export_{_counter}.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    ok(run(canvas.add_layer(path, "paint")))
    ok(run(animation.add_frames(path, 1)))
    ok(run(animation.clear_cel(path, "paint", 2)))
    ok(run(drawing.draw_pixels_at(path, "paint", 1, [{"x": 1, "y": 1, "color": "#FF0000"}])))
    ok(run(drawing.draw_pixels_at(path, "paint", 2, [{"x": 2, "y": 2, "color": "#00FF00"}])))
    return path


@pytest.fixture
def out_dir(base_dir):
    global _counter
    _counter += 1
    path = f"{BASE}/out_{_counter}"
    os.makedirs(path)
    return path


def rgba(path, x, y):
    return Image.open(path).convert("RGBA").getpixel((x, y))


# ── exports ───────────────────────────────────────────────────────────

def test_export_frame_picks_the_frame_and_scales(two_frames, out_dir):
    out = f"{out_dir}/f2.png"
    ok(run(export.export_frame(two_frames, 2, out, 3)))
    img = Image.open(out)
    assert img.size == (24, 24)
    assert rgba(out, 6, 6) == (0, 255, 0, 255) and rgba(out, 3, 3)[3] == 0


def test_export_sprite_png_and_gif(two_frames, out_dir):
    ok(run(export.export_sprite(two_frames, f"{out_dir}/anim", "gif")))
    assert Image.open(f"{out_dir}/anim.gif").n_frames == 2
    ok(run(export.export_sprite(two_frames, f"{out_dir}/still", "png")))
    assert any(name.startswith("still") and name.endswith(".png") for name in os.listdir(out_dir))


def test_export_sprite_unwritable_format(two_frames, out_dir):
    fails(export.export_sprite(two_frames, f"{out_dir}/data", "json"), AsepriteError, "wrote no file")


def test_spritesheet_with_data_and_tag(two_frames, out_dir):
    ok(run(animation.set_tag(two_frames, "only2", 2, 2)))
    sheet, data = f"{out_dir}/sheet.png", f"{out_dir}/sheet.json"
    ok(run(export.export_spritesheet(two_frames, sheet, "horizontal", data, 1, 0, "", "json-hash", True)))
    assert Image.open(sheet).size == (16, 8)
    meta = json.loads(open(data).read())
    assert len(meta["frames"]) == 2 and meta["meta"]["frameTags"][0]["name"] == "only2"
    tagged = f"{out_dir}/tagged.png"
    ok(run(export.export_spritesheet(two_frames, tagged, "horizontal", "", 1, 0, "only2")))
    assert Image.open(tagged).size == (8, 8) and rgba(tagged, 2, 2) == (0, 255, 0, 255)
    fails(export.export_spritesheet(two_frames, f"{out_dir}/x.png", tag_name="nope"), AsepriteError, "Tag not found")


def test_export_layers(two_frames, out_dir):
    out = ok(run(export.export_layers(two_frames, f"{out_dir}/layers")))
    assert "paint" in out


def test_export_tag(two_frames, out_dir):
    ok(run(animation.set_tag(two_frames, "both", 1, 2)))
    ok(run(export.export_tag(two_frames, "both", f"{out_dir}/both.gif", 2)))
    assert Image.open(f"{out_dir}/both.gif").size == (16, 16)
    fails(export.export_tag(two_frames, "nope", f"{out_dir}/nope.gif"), AsepriteError, "Tag not found")


def test_copy_sprite(two_frames, out_dir):
    target = f"{out_dir}/copy"
    ok(run(export.copy_sprite(two_frames, target)))
    assert coords(f"{target}.aseprite") == {(1, 1)}
    fails(export.copy_sprite(two_frames, target), InputError, "already exists")
    ok(run(export.copy_sprite(two_frames, target, overwrite=True)))


def test_import_image(two_frames, out_dir):
    src = f"{out_dir}/src.png"
    img = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    img.putpixel((0, 0), (0, 0, 255, 255))
    img.putpixel((1, 0), (0, 0, 255, 128))
    img.save(src)
    ok(run(export.import_image_as_layer(two_frames, src, "ref", 1, 4, 5)))
    assert pixels(two_frames, "ref") == {(4, 5): "#0000ffff", (5, 5): "#0000ff80"}
    fails(export.import_image_as_layer(two_frames, f"{out_dir}/missing.png", "ref"), InputError, "not found")


# ── text ──────────────────────────────────────────────────────────────



def test_text_missing_layer(two_frames, bitmap_font):
    ok(run(text.draw_text(two_frames, "A", 0, 0, bitmap_font, layer_name="made")))
    assert coords(two_frames, "made")
    fails(text.draw_text(two_frames, "A", 0, 0, bitmap_font, layer_name="nope", create_if_missing=False),
          AsepriteError, "Layer not found")


def test_text_blends_translucent_colour(two_frames, bitmap_font):
    ok(run(drawing.draw_rectangle_at(two_frames, "paint", 1, 0, 0, 8, 8, "#0000FF", True)))
    ok(run(text.draw_text(two_frames, "O", 0, 0, bitmap_font, color="#FF000080", layer_name="paint")))
    blended = pixels(two_frames)[(1, 0)]                  # 'O' has ink at (1,0)
    assert blended not in ("#0000ffff", "#ff000080") and blended.endswith("ff")


def test_text_offcanvas_is_clipped(two_frames, bitmap_font):
    ok(run(text.draw_text(two_frames, "O", -2, -2, bitmap_font, layer_name="paint", color="#FFFFFF")))
    assert all(0 <= x < 8 and 0 <= y < 8 for x, y in coords(two_frames))


# ── behaviour changed by the move to ops (failed before) ──────────────

def _touch_stale(path):
    open(path, "wb").write(b"stale")
    old = time.time() - 3600
    os.utime(path, (old, old))


def test_export_sprite_ignores_stale_files(two_frames, out_dir):
    _touch_stale(f"{out_dir}/out-old.json")
    fails(export.export_sprite(two_frames, f"{out_dir}/out", "json"), AsepriteError, "wrote no file")


def test_export_layers_lists_only_this_export(two_frames, out_dir):
    layers_dir = f"{out_dir}/layers"
    os.makedirs(layers_dir)
    _touch_stale(f"{layers_dir}/leftover.png")
    out = ok(run(export.export_layers(two_frames, layers_dir)))
    assert "leftover" not in out


def test_export_sprite_rejects_traversal(two_frames, out_dir, monkeypatch):
    os.makedirs(f"{out_dir}/inner")
    monkeypatch.chdir(f"{out_dir}/inner")
    fails(export.export_sprite(two_frames, "../escaped", "png"), InputError, "traversal")
    assert not os.path.exists(f"{out_dir}/escaped.png")


def test_export_paths_with_glob_characters(two_frames, out_dir):
    # Two frames to PNG writes numbered siblings, found by glob; '[1]' used to
    # be read as a character class, so the export was reported as failed.
    ok(run(export.export_sprite(two_frames, f"{out_dir}/odd[1]", "png")))
    assert any(name.startswith("odd[1]") for name in os.listdir(out_dir))


def test_text_keeps_cel_content_that_hangs_off_canvas(two_frames, bitmap_font):
    ok(run(drawing.draw_rectangle_at(two_frames, "paint", 1, 0, 0, 3, 3, "#FF0000", True)))
    ok(run(animation.offset_cel_positions(two_frames, "paint", 1, 1, -2, 0)))
    assert (-2, 0) in coords(two_frames)
    ok(run(text.draw_text(two_frames, "A", 4, 2, bitmap_font, layer_name="paint")))
    assert (-2, 0) in coords(two_frames)


# ── stamp composition (pure Python, no Aseprite) ──────────────────────

def test_stamp_outline_four_way():
    s = text._compose_stamp({(0, 0)}, [1, 1, 1, 255], outline=[0, 0, 0, 255], outline_diagonal=False)
    assert (s["left"], s["top"], s["width"], s["height"]) == (-1, -1, 3, 3)
    assert s["colors"] == [[0, 0, 0, 255], [1, 1, 1, 255]]
    rim = {(x, y) for x, y, c in s["pixels"] if c == 1}
    assert rim == {(0, 1), (2, 1), (1, 0), (1, 2)}
    assert [p for p in s["pixels"] if p[2] == 2] == [[1, 1, 2]]


def test_stamp_shadow_sits_behind_the_outline():
    s = text._compose_stamp({(0, 0)}, [9, 9, 9, 255], outline=[0, 0, 0, 255], shadow=[5, 5, 5, 255],
                            shadow_dx=2, shadow_dy=2)
    assert s["colors"][0] == [5, 5, 5, 255]
    shadow = {(x + s["left"], y + s["top"]) for x, y, c in s["pixels"] if c == 1}
    assert shadow == {(2, 2)}                         # (1,1) is outline, so only the far corner shows


def test_stamp_without_effects_is_just_the_ink():
    s = text._compose_stamp({(3, -2), (4, -2)}, [1, 2, 3, 4])
    assert (s["left"], s["top"], s["width"], s["height"]) == (3, -2, 2, 1)
    assert s["pixels"] == [[0, 0, 1], [1, 0, 1]] and s["colors"] == [[1, 2, 3, 4]]
