"""Behaviour of the quality (quality.py) and scene (scene.py) tools."""
import json

import pytest
from conftest import BASE, fails, ok, run

from aseprite_mcp.core.commands import run_script
from aseprite_mcp.core.errors import AsepriteError, InputError
from aseprite_mcp.tools import animation, canvas, quality, scene

_counter = 0

# 16x16, 3 frames. Top-level: Layer 1 (empty), a, b, c, group g.
#   a: 4x4 cels at (0,0) on frames 1 and 2
#   b: 4x4 cels at (2,2) on frame 1 and (10,10) on frame 2
#   c: no cels
#   g/inner: 2x2 cels at (12,12) on frames 1-3
SCENE = """
local s = Sprite(16, 16)
s:newFrame() s:newFrame()
for _, f in ipairs(s.frames) do
  local c = s.layers[1]:cel(f) if c then s:deleteCel(c) end
end
local function layer(name, parent)
  local l = s:newLayer() l.name = name if parent then l.parent = parent end return l
end
local function cel(l, frame, x, y, w, h)
  local img = Image(w, h) img:clear(Color(255, 0, 0)) s:newCel(l, frame, img, Point(x, y))
end
local a, b, c = layer("a"), layer("b"), layer("c")
local g = s:newGroup() g.name = "g"
local inner = layer("inner", g)
cel(a, 1, 0, 0, 4, 4) cel(a, 2, 0, 0, 4, 4)
cel(b, 1, 2, 2, 4, 4) cel(b, 2, 10, 10, 4, 4)
for f = 1, 3 do cel(inner, f, 12, 12, 2, 2) end
s:saveAs("%s")
"""

CELS = """
local out = {}
local function walk(layers, prefix)
  for _, l in ipairs(layers) do
    if l.isGroup then walk(l.layers, prefix .. l.name .. "/") else
      local frames = {}
      for i, f in ipairs(app.activeSprite.frames) do
        local c = l:cel(f)
        if c then frames[#frames + 1] = { frame = i, opacity = c.opacity } end
      end
      out[prefix .. l.name] = frames
    end
  end
end
walk(app.activeSprite.layers, "")
print(json.encode(out))
"""


def cels(path):
    return {k: {c["frame"]: c["opacity"] for c in v} for k, v in json.loads(run(run_script(CELS, path))).items()}


@pytest.fixture
def scene_file(base_dir):
    global _counter
    _counter += 1
    path = f"{BASE}/quality_{_counter}.aseprite"
    run(run_script(SCENE % path))
    return path


ABC = ["a", "b", "c"]


# ── ensure / validate ─────────────────────────────────────────────────

def test_ensure_layers_present(scene_file):
    ok(run(quality.ensure_layers_present(scene_file, ["a", "MISSING"])))
    assert set(cels(scene_file)["a"]) == {1, 2, 3}
    fails(quality.ensure_layers_present(scene_file, ["MISSING"]), AsepriteError, "No layers found")
    fails(quality.ensure_layers_present(scene_file, ["a"], 2, 9), AsepriteError, "out of bounds")


def test_validate_scene(scene_file):
    result = json.loads(run(quality.validate_scene(scene_file, ABC + ["zzz"])))
    assert result == {
        "frames": 3, "range": {"start": 1, "end": 3}, "missing_layers": ["zzz"],
        "missing_cels": [{"layer": "a", "frame": 3}, {"layer": "b", "frame": 3},
                         {"layer": "c", "frame": 1}, {"layer": "c", "frame": 2}, {"layer": "c", "frame": 3}]}


# ── audit ─────────────────────────────────────────────────────────────

def test_audit(scene_file):
    result = json.loads(run(quality.audit_animation(scene_file, layer_names=ABC, overlap_pairs=["a,b"],
                                                    layer_frame_ranges=["b:1-1"])))
    assert result == {
        "frames": {"start": 1, "end": 3},
        "summary": {"total_layers": 5, "layers_checked": 3, "total_cels": 4, "overlaps": 1,
                    "overlaps_total": 1, "overlaps_truncated": False, "out_of_range": 1},
        "overlaps": [{"frame": 1, "a": "a", "b": "b"}],
        "out_of_range": [{"frame": 2, "layer": "b"}]}


def test_audit_bounds_cels_and_limits(scene_file):
    result = json.loads(run(quality.audit_animation(scene_file, 1, 2, layer_names=["a", "b"], overlap_pairs=["a:b"],
                                                    report_cels=True, report_bounds=True, max_overlaps=0)))
    assert result["overlaps"] == [] and result["summary"]["overlaps_truncated"] is True
    assert result["summary"]["overlaps_total"] == 1
    assert result["cels"] == [
        {"frame": 1, "cels": [{"layer": "a", "x": 0, "y": 0, "w": 4, "h": 4}, {"layer": "b", "x": 2, "y": 2, "w": 4, "h": 4}]},
        {"frame": 2, "cels": [{"layer": "a", "x": 0, "y": 0, "w": 4, "h": 4}, {"layer": "b", "x": 10, "y": 10, "w": 4, "h": 4}]}]
    with_bounds = json.loads(run(quality.audit_animation(scene_file, 1, 1, layer_names=["a", "b"],
                                                         overlap_pairs=["a,b"], report_bounds=True)))
    assert with_bounds["overlaps"] == [{"frame": 1, "a": "a", "b": "b", "a_bounds": [0, 0, 4, 4], "b_bounds": [2, 2, 4, 4]}]


# ── sanitize ──────────────────────────────────────────────────────────

SANITIZE = dict(layer_names=ABC, layer_frame_ranges=["b:1-1"], overlap_pairs=["a,b"], ignore_full_canvas_overlaps=False)


def test_sanitize_report_only_changes_nothing(scene_file):
    before = cels(scene_file)
    result = json.loads(run(quality.animation_sanitize(scene_file, report_only=True, **SANITIZE)))
    assert result == {
        "frames": {"start": 1, "end": 3}, "reordered": False, "ensured": 0, "out_of_range": 1,
        "opacity_set": 0, "deleted": 0,
        "analysis": {"total_layers": 5, "layers_checked": 3, "total_cels": 4, "empty_frames": 1, "overlaps": 1,
                     "overlaps_total": 1, "overlaps_truncated": False, "inactive_layers": ["c"]},
        "layer_stats": {
            "a": {"frames_active": 2, "cel_count": 2, "full_canvas_cels": 0, "bounds": [0, 0, 4, 4]},
            "b": {"frames_active": 2, "cel_count": 2, "full_canvas_cels": 0, "bounds": [2, 2, 14, 14]},
            "c": {"frames_active": 0, "cel_count": 0, "full_canvas_cels": 0, "bounds": None}},
        "alerts": ["empty_frames_detected", "cels_out_of_range"],
        "overlap_samples": [{"frame": 1, "a": "a", "b": "b"}]}
    assert cels(scene_file) == before


@pytest.mark.parametrize("action,expected", [("set_opacity_zero", {1: 255, 2: 0}), ("delete_cels", {1: 255})])
def test_sanitize_fixes_out_of_range_cels(scene_file, action, expected):
    result = json.loads(run(quality.animation_sanitize(scene_file, out_of_range_action=action, **SANITIZE)))
    assert (result["opacity_set"], result["deleted"]) == ((1, 0) if action == "set_opacity_zero" else (0, 1))
    assert cels(scene_file)["b"] == expected


def test_sanitize_ensures_cels(scene_file):
    result = json.loads(run(quality.animation_sanitize(scene_file, layer_names=ABC, ensure_layers=["c"])))
    assert result["ensured"] == 3 and set(cels(scene_file)["c"]) == {1, 2, 3}


def test_sanitize_reorders_only_without_groups(scene_file, base_dir):
    # Behaviour change: the old code reported reordered=True and changed nothing,
    # because it tracked layers in a table keyed by layer userdata (see DESIGN.md).
    assert json.loads(run(quality.animation_sanitize(scene_file, layer_names=ABC, layer_order=["c"])))["reordered"] is False
    flat = f"{base_dir}/quality_flat_{_counter}.aseprite"
    ok(run(canvas.create_canvas(8, 8, flat)))
    ok(run(canvas.add_layer(flat, "x")))
    ok(run(canvas.add_layer(flat, "y")))
    assert json.loads(run(quality.animation_sanitize(flat, layer_order=["y"])))["reordered"] is True
    info = json.loads(run(animation.get_sprite_info(flat)))
    assert [layer["name"] for layer in info["layers"]] == ["y", "Layer 1", "x"]


def test_quality_input_checks(scene_file):
    fails(quality.audit_animation(scene_file, start_frame=0), InputError, ">= 1")
    fails(quality.animation_sanitize(scene_file, out_of_range_action="explode"), InputError, "Unsupported")


# ── scene ─────────────────────────────────────────────────────────────

def test_copy_layers_between_sprites(scene_file, base_dir):
    target = f"{base_dir}/quality_target_{_counter}.aseprite"
    ok(run(canvas.create_canvas(16, 16, target)))
    out = ok(run(scene.copy_layers_between_sprites(scene_file, target, ["a", "g/inner", "nope"])))
    assert "skipped missing layers: nope" in out
    copied = cels(target)
    assert set(copied["a"]) == {1, 2} and set(copied["g/inner"] if "g/inner" in copied else copied["inner"]) == {1, 2, 3}
    fails(scene.copy_layers_between_sprites(scene_file, target, ["nope"]), AsepriteError, "None of the requested")


# ── behaviour changed by the move to ops (failed before) ──────────────

def test_layers_inside_groups_are_found(scene_file):
    validated = json.loads(run(quality.validate_scene(scene_file, ["inner"])))
    assert validated["missing_layers"] == [] and validated["missing_cels"] == []
    ok(run(quality.ensure_layers_present(scene_file, ["g/inner"])))
    audit = json.loads(run(quality.audit_animation(scene_file, layer_names=["inner"], layer_frame_ranges=["inner:1-1"])))
    assert audit["summary"]["layers_checked"] == 1 and len(audit["out_of_range"]) == 2


def test_default_targets_include_layers_inside_groups(scene_file):
    audit = json.loads(run(quality.audit_animation(scene_file)))
    assert audit["summary"]["layers_checked"] == 5          # Layer 1, a, b, c, inner


def test_names_with_quotes_and_colons(scene_file):
    ok(run(canvas.add_layer(scene_file, 'arm "L":v2')))
    ok(run(animation.create_cel(scene_file, 'arm "L":v2', 2)))
    audit = json.loads(run(quality.audit_animation(scene_file, layer_names=['arm "L":v2', "a"],
                                                   overlap_pairs=['arm "L":v2,a'],
                                                   layer_frame_ranges=['arm "L":v2:1-1'])))
    assert audit["out_of_range"] == [{"frame": 2, "layer": 'arm "L":v2'}]
    validated = json.loads(run(quality.validate_scene(scene_file, ['missing "q"'])))
    assert validated["missing_layers"] == ['missing "q"']


@pytest.mark.parametrize("bad", ["b:1-x", "b", "b:3-1", ":1-2"])
def test_malformed_ranges_are_rejected(scene_file, bad):
    fails(quality.audit_animation(scene_file, layer_frame_ranges=[bad]), InputError)


@pytest.mark.parametrize("bad", ["a", "a,", ",b"])
def test_malformed_pairs_are_rejected(scene_file, bad):
    fails(quality.audit_animation(scene_file, overlap_pairs=[bad]), InputError)
