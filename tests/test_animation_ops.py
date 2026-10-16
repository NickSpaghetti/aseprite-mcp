"""Behaviour of every animation tool, read back from the saved file.

Expected values are worked out by hand from each tool's documented maths
(linear and eased tweens, sine oscillation, centred scaling), not recorded
from a previous run.
"""
import json
import math

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.commands import run_script
from aseprite_mcp.core.errors import AsepriteError
from aseprite_mcp.tools import animation, canvas, drawing

STATE = """
local spr = app.activeSprite
local out = { durations = {}, layers = {}, tags = {} }
for i, f in ipairs(spr.frames) do out.durations[i] = math.floor(f.duration * 1000 + 0.5) end
local function walk(layers, prefix)
  for _, l in ipairs(layers) do
    local name = prefix .. l.name
    if l.isGroup then
      walk(l.layers, name .. "/")
    else
      local cels = {}
      for i, f in ipairs(spr.frames) do
        local c = l:cel(f)
        if c then
          cels[tostring(i)] = { x = c.position.x, y = c.position.y,
                                w = c.image.width, h = c.image.height, opacity = c.opacity }
        end
      end
      out.layers[name] = { visible = l.isVisible, opacity = l.opacity, cels = cels }
    end
  end
end
walk(spr.layers, "")
for _, t in ipairs(spr.tags) do
  out.tags[t.name] = { from = t.fromFrame.frameNumber, to = t.toFrame.frameNumber }
end
print(json.encode(out))
"""


def state(path):
    s = json.loads(run(run_script(STATE, path)))
    for layer in s["layers"].values():
        layer["cels"] = {int(k): v for k, v in (layer["cels"] or {}).items()}
    s["tags"] = s["tags"] or {}
    return s


def cels(path, layer="body"):
    return state(path)["layers"][layer]["cels"]


_counter = 0


@pytest.fixture
def sprite5(base_dir):
    """A fresh 16x16 sprite with 5 frames and a 'body' layer holding one cel, on frame 1."""
    global _counter
    _counter += 1
    path = f"{BASE}/anim_{_counter}.aseprite"
    ok(run(canvas.create_canvas(16, 16, path)))
    ok(run(canvas.add_layer(path, "body")))
    ok(run(drawing.draw_rectangle_at(path, "body", 1, 4, 4, 4, 4, "#FF0000", True)))
    ok(run(animation.add_frames(path, 4)))
    # newFrame() copies the previous frame's cels, so clear them to leave one cel.
    for frame in range(2, 6):
        ok(run(animation.clear_cel(path, "body", frame)))
    assert sorted(cels(path)) == [1]
    return path


# ── frames ────────────────────────────────────────────────────────────

def test_add_frames_with_duration(sprite5):
    ok(run(animation.add_frames(sprite5, 2, 250)))
    assert state(sprite5)["durations"] == [100, 100, 100, 100, 100, 250, 250]


def test_set_frame_duration_all(sprite5):
    ok(run(animation.set_frame_duration_all(sprite5, 80)))
    assert state(sprite5)["durations"] == [80] * 5


def test_delete_frame(sprite5):
    ok(run(animation.delete_frame(sprite5, 2)))
    assert len(state(sprite5)["durations"]) == 4


def test_delete_only_frame_fails(base_dir):
    path = f"{BASE}/anim_single.aseprite"
    ok(run(canvas.create_canvas(8, 8, path)))
    fails(animation.delete_frame(path, 1), AsepriteError, "only frame")


def test_duplicate_frame_range_rejects_bad_range(sprite5):
    fails(animation.duplicate_frame_range(sprite5, 4, 9), AsepriteError, "out of bounds")


# ── layers ────────────────────────────────────────────────────────────

def test_layer_visibility_and_opacity(sprite5):
    ok(run(animation.set_layer_visibility(sprite5, "body", False)))
    ok(run(animation.set_layer_opacity(sprite5, "body", 90)))
    body = state(sprite5)["layers"]["body"]
    assert (body["visible"], body["opacity"]) == (False, 90)


# ── single cels ───────────────────────────────────────────────────────

def test_set_cel_position_moves_existing_cel(sprite5):
    ok(run(animation.set_cel_position(sprite5, "body", 1, 3, 2)))
    assert (cels(sprite5)[1]["x"], cels(sprite5)[1]["y"]) == (3, 2)


def test_set_cel_position_creates_from_source(sprite5):
    ok(run(animation.set_cel_position(sprite5, "body", 3, 5, 6, create_if_missing=True, source_frame_index=1)))
    c = cels(sprite5)[3]
    assert (c["x"], c["y"], c["w"]) == (5, 6, cels(sprite5)[1]["w"])


def test_create_and_clear_cel(sprite5):
    ok(run(animation.create_cel(sprite5, "body", 2, 1, 1)))
    assert 2 in cels(sprite5)
    ok(run(animation.clear_cel(sprite5, "body", 2)))
    assert 2 not in cels(sprite5)


def test_copy_cel(sprite5):
    ok(run(animation.copy_cel(sprite5, "body", 1, 4)))
    assert cels(sprite5)[4]["w"] == cels(sprite5)[1]["w"]


def test_set_cel_opacity(sprite5):
    ok(run(animation.set_cel_opacity(sprite5, "body", 1, 77)))
    assert cels(sprite5)[1]["opacity"] == 77


def test_set_cel_opacity_needs_a_cel(sprite5):
    fails(animation.set_cel_opacity(sprite5, "body", 2, 77), AsepriteError, "No cel")


# ── whole frames ──────────────────────────────────────────────────────

def test_copy_frame_appends(sprite5):
    ok(run(animation.copy_frame(sprite5, 1)))
    s = state(sprite5)
    assert len(s["durations"]) == 6 and 6 in s["layers"]["body"]["cels"]


def test_copy_frame_overwrites_target(sprite5):
    ok(run(animation.create_cel(sprite5, "body", 3, 9, 9)))
    ok(run(animation.copy_frame(sprite5, 1, 3)))
    assert (cels(sprite5)[3]["x"], cels(sprite5)[3]["w"]) == (cels(sprite5)[1]["x"], cels(sprite5)[1]["w"])


def test_propagate_frame_to_range(sprite5):
    ok(run(animation.propagate_frame_to_range(sprite5, 1, 2, 4)))
    assert sorted(cels(sprite5)) == [1, 2, 3, 4]


def test_propagate_cels(sprite5):
    ok(run(animation.propagate_cels(sprite5, ["body", "MISSING"], 1, 1, 5)))
    assert sorted(cels(sprite5)) == [1, 2, 3, 4, 5]


def test_propagate_cels_needs_one_real_layer(sprite5):
    fails(animation.propagate_cels(sprite5, ["MISSING"], 1, 1, 5), AsepriteError, "No layers found")


# ── tweens ────────────────────────────────────────────────────────────

def _positions(path, axis="x"):
    return [cels(path)[i][axis] for i in range(1, 6)]


def test_tween_linear(sprite5):
    ok(run(animation.tween_cel_positions(sprite5, "body", 1, 5, 0, 0, 10, 20, create_missing_cels=True)))
    # t = 0, .25, .5, .75, 1 -> round(10t), round(20t)
    assert _positions(sprite5) == [0, 3, 5, 8, 10]
    assert _positions(sprite5, "y") == [0, 5, 10, 15, 20]


@pytest.mark.parametrize("easing,expected", [
    ("linear", [0, 3, 5, 8, 10]),
    ("ease_in", [0, 1, 3, 6, 10]),          # t^2
    ("ease_out", [0, 4, 8, 9, 10]),         # 1-(1-t)^2
    ("ease_in_out", [0, 1, 5, 9, 10]),      # 2t^2 | 1-(-2t+2)^2/2
    ("smoothstep", [0, 2, 5, 8, 10]),       # t^2(3-2t)
])
def test_tween_eased(sprite5, easing, expected):
    ok(run(animation.tween_cel_positions_eased(
        sprite5, "body", 1, 5, 0, 0, 10, 0, easing=easing, create_missing_cels=True)))
    assert _positions(sprite5) == expected


def test_offset_cel_positions(sprite5):
    ok(run(animation.propagate_cels(sprite5, ["body"], 1, 1, 5)))
    ok(run(animation.offset_cel_positions(sprite5, "body", 2, 3, 2, -1)))
    xs, ys = _positions(sprite5), _positions(sprite5, "y")
    assert xs[1] == xs[0] + 2 and ys[2] == ys[0] - 1 and xs[3] == xs[0]


def test_oscillate(sprite5):
    ok(run(animation.propagate_cels(sprite5, ["body"], 1, 1, 5)))
    base = cels(sprite5)[1]["x"]
    ok(run(animation.oscillate_cel_positions(sprite5, "body", 1, 5, amplitude_x=4, cycles=1)))
    # angle = 2*pi*t; dx = round(4 sin(angle))
    expected = [base + math.floor(4 * math.sin(2 * math.pi * t) + 0.5) for t in (0, .25, .5, .75, 1)]
    assert _positions(sprite5) == expected


def test_tween_opacity(sprite5):
    ok(run(animation.tween_cel_opacity_eased(
        sprite5, "body", 1, 5, 255, 55, easing="linear", create_missing_cels=True)))
    assert [cels(sprite5)[i]["opacity"] for i in range(1, 6)] == [255, 205, 155, 105, 55]


def test_tween_scale_centred(sprite5):
    src = cels(sprite5)[1]
    ok(run(animation.tween_cel_scale_eased(sprite5, "body", 1, 2, 1.0, 0.5, easing="linear")))
    c1, c2 = cels(sprite5)[1], cels(sprite5)[2]
    assert (c1["w"], c1["h"]) == (src["w"], src["h"])
    half_w = math.floor(src["w"] * 0.5 + 0.5)
    assert c2["w"] == half_w
    assert c2["x"] == math.floor(src["x"] + src["w"] / 2 - half_w / 2 + 0.5)


# ── tags ──────────────────────────────────────────────────────────────

def test_set_and_update_and_delete_tag(sprite5):
    ok(run(animation.set_tag(sprite5, "walk", 1, 3, "pingpong")))
    ok(run(animation.set_tag(sprite5, "walk", 2, 5)))
    assert state(sprite5)["tags"] == {"walk": {"from": 2, "to": 5}}
    info = json.loads(run(animation.get_sprite_info(sprite5)))
    assert info["tags"] == [{"name": "walk", "from": 2, "to": 5, "direction": "forward"}]
    ok(run(animation.delete_tag(sprite5, "walk")))
    assert state(sprite5)["tags"] == {}


# ── behaviour changed by the move to ops (these failed before) ────────

def test_sprite_info_is_valid_json_for_any_layer_name(sprite5):
    name = 'line1\nline2 "quoted" \\ back'
    ok(run(canvas.add_layer(sprite5, name)))
    info = json.loads(run(animation.get_sprite_info(sprite5)))
    assert name in [layer["name"] for layer in info["layers"]]


def test_frame_copies_include_layers_inside_groups(sprite5):
    ok(run(canvas.add_group(sprite5, "grp")))
    ok(run(canvas.add_layer(sprite5, "arm", group="grp")))
    ok(run(drawing.draw_rectangle_at(sprite5, "grp/arm", 1, 0, 0, 2, 2, "#00FF00", True)))
    ok(run(animation.copy_frame(sprite5, 1, 2)))
    ok(run(animation.propagate_frame_to_range(sprite5, 1, 3, 3)))
    ok(run(animation.duplicate_frame_range(sprite5, 1, 1)))
    assert sorted(cels(sprite5, "grp/arm")) == [1, 2, 3, 6]


def test_bad_source_frame_fails_instead_of_doing_nothing(sprite5):
    fails(animation.set_cel_position(sprite5, "body", 3, 1, 1, create_if_missing=True, source_frame_index=99),
          AsepriteError, "out of range")


def test_duplicated_empty_frames_stay_empty(sprite5):
    # Frames used to be appended with newFrame(), which copies the previous
    # frame's cels, so the copy of empty frame 2 came out holding frame 1's cel.
    ok(run(animation.duplicate_frame_range(sprite5, 1, 2, times=2)))
    s = state(sprite5)
    assert len(s["durations"]) == 9
    assert sorted(s["layers"]["body"]["cels"]) == [1, 6, 8]


def test_copy_frame_append_copies_only_the_source(sprite5):
    # The last frame has a cel and the source frame doesn't; the new frame
    # must match the source, not inherit from the frame it was appended after.
    ok(run(animation.create_cel(sprite5, "body", 5)))
    ok(run(animation.copy_frame(sprite5, 2)))
    assert sorted(cels(sprite5)) == [1, 5]


def test_duplicated_frames_keep_their_duration(sprite5):
    ok(run(animation.add_frames(sprite5, 1, 300)))               # frame 6 lasts 300 ms
    ok(run(animation.duplicate_frame_range(sprite5, 1, 1)))       # copy of frame 1 (100 ms) after frame 6
    ok(run(animation.copy_frame(sprite5, 6)))                     # copy of frame 6 (300 ms)
    assert state(sprite5)["durations"][-2:] == [100, 300]
