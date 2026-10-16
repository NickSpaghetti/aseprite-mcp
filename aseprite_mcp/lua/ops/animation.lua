-- Frame, cel, tween and tag ops (tools/animation.py).
local lib = ...

-- Easing curves over t in [0, 1]. tools/animation.py validates names against
-- the same set.
local EASINGS = {
  linear = function(t) return t end,
  ease_in = function(t) return t * t end,
  ease_out = function(t) return 1 - (1 - t) * (1 - t) end,
  ease_in_out = function(t)
    if t < 0.5 then return 2 * t * t end
    local u = -2 * t + 2
    return 1 - (u * u) / 2
  end,
  smoothstep = function(t) return t * t * (3 - 2 * t) end,
}

local function round(v) return math.floor(v + 0.5) end

-- Position of frame `index` along [first, last], from 0 to 1.
local function progress(index, first, last)
  if last == first then return 0 end
  return (index - first) / (last - first)
end

-- The cel on layer/frame. When there is none and `create` is set, make one:
-- a copy of the cel on `source_index` if that frame has one, else an empty
-- canvas-sized cel.
local function ensure_cel(sprite, layer, frame, create, source_index)
  local cel = layer:cel(frame)
  if cel or not create then return cel end
  local source = layer:cel(lib.frame(sprite, source_index, "Source frame out of range"))
  if source then
    return sprite:newCel(layer, frame, source.image:clone(), source.position)
  end
  return sprite:newCel(layer, frame, Image(sprite.width, sprite.height, sprite.colorMode), Point(0, 0))
end

-- A new last frame with `source`'s duration.
local function append_frame_like(sprite, source)
  local frame = sprite:newEmptyFrame(#sprite.frames + 1)
  frame.duration = source.duration
  return frame
end

-- Replace every cel of `target` with copies of `source`'s cels, across all
-- image layers. `clear` removes target cels first even where source has none.
local function copy_frame_cels(sprite, source, target, clear)
  for _, layer in ipairs(lib.image_layers(sprite)) do
    if clear then
      local old = layer:cel(target)
      if old then sprite:deleteCel(old) end
    end
    local cel = layer:cel(source)
    if cel then sprite:newCel(layer, target, cel.image:clone(), cel.position) end
  end
end

-- ── frames ───────────────────────────────────────────────────────────

lib.edit("animation.add_frames", function(sprite, a)
  for _ = 1, a.count do
    sprite:newFrame()
    if a.duration_ms then sprite.frames[#sprite.frames].duration = a.duration_ms / 1000.0 end
  end
end)

lib.edit("animation.set_frame_duration_all", function(sprite, a)
  for _, frame in ipairs(sprite.frames) do frame.duration = a.duration_ms / 1000.0 end
end)

lib.edit("animation.delete_frame", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  if #sprite.frames <= 1 then lib.fail("OnlyFrame", "Cannot delete the only frame") end
  sprite:deleteFrame(frame)
end)

lib.edit("animation.duplicate_frame_range", function(sprite, a)
  local first, last = lib.frame_range(sprite, a.first, a.last)
  for _ = 1, a.times do
    for index = first, last do
      local source = sprite.frames[index]
      copy_frame_cels(sprite, source, append_frame_like(sprite, source), false)
    end
  end
end)

lib.edit("animation.copy_frame", function(sprite, a)
  local source = lib.frame(sprite, a.source, "Source frame out of range")
  if a.target then
    copy_frame_cels(sprite, source, lib.frame(sprite, a.target, "Target frame out of range"), a.overwrite)
  else
    copy_frame_cels(sprite, source, append_frame_like(sprite, source), false)
  end
end)

lib.edit("animation.propagate_frame_to_range", function(sprite, a)
  local source = lib.frame(sprite, a.source, "Source frame out of range")
  local first, last = lib.frame_range(sprite, a.first, a.last)
  for index = first, last do
    if index ~= a.source then copy_frame_cels(sprite, source, sprite.frames[index], a.overwrite) end
  end
end)

-- ── layers ───────────────────────────────────────────────────────────

lib.edit("animation.set_layer_visibility", function(sprite, a)
  lib.layer(sprite, a.name).isVisible = a.visible
end)

lib.edit("animation.set_layer_opacity", function(sprite, a)
  lib.layer(sprite, a.name).opacity = a.opacity
end)

-- ── cels ─────────────────────────────────────────────────────────────

lib.edit("animation.set_cel_position", function(sprite, a)
  local layer = lib.layer(sprite, a.name)
  local frame = lib.frame(sprite, a.frame)
  local cel = ensure_cel(sprite, layer, frame, a.create_if_missing, a.source_frame or a.frame)
  if cel then cel.position = Point(a.x, a.y) end
end)

lib.edit("animation.offset_cel_positions", function(sprite, a)
  local layer = lib.layer(sprite, a.name)
  local first, last = lib.frame_range(sprite, a.first, a.last)
  for index = first, last do
    local cel = layer:cel(sprite.frames[index])
    if cel then cel.position = Point(cel.position.x + a.dx, cel.position.y + a.dy) end
  end
end)

lib.edit("animation.create_cel", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  local layer = lib.layer(sprite, a.name)
  if not layer:cel(frame) then
    sprite:newCel(layer, frame, Image(sprite.width, sprite.height, sprite.colorMode), Point(a.x, a.y))
  end
end)

lib.edit("animation.clear_cel", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  local cel = lib.layer(sprite, a.name):cel(frame)
  if cel then sprite:deleteCel(cel) end
end)

lib.edit("animation.copy_cel", function(sprite, a)
  local source_frame = lib.frame(sprite, a.source, "Source frame out of range")
  local target_frame = lib.frame(sprite, a.target, "Target frame out of range")
  local layer = lib.layer(sprite, a.name)
  local source = layer:cel(source_frame)
  if not source then return end
  local existing = layer:cel(target_frame)
  if existing and not a.replace then return end
  if existing then sprite:deleteCel(existing) end
  sprite:newCel(layer, target_frame, source.image:clone(), source.position)
end)

lib.edit("animation.set_cel_opacity", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  lib.cel(lib.layer(sprite, a.name), frame).opacity = a.opacity
end)

lib.edit("animation.propagate_cels", function(sprite, a)
  local source = lib.frame(sprite, a.source, "Source frame out of range")
  local first, last = lib.frame_range(sprite, a.first, a.last)
  local layers = {}
  for _, name in ipairs(a.names) do layers[#layers + 1] = lib.find_layer(sprite, name) end
  if #layers == 0 then lib.fail("NoLayersFound", "No layers found") end
  for index = first, last do
    if index ~= a.source then
      local target = sprite.frames[index]
      for _, layer in ipairs(layers) do
        local cel = layer:cel(source)
        if cel then
          local existing = layer:cel(target)
          if existing and a.replace then sprite:deleteCel(existing) existing = nil end
          if not existing then sprite:newCel(layer, target, cel.image:clone(), cel.position) end
        end
      end
    end
  end
end)

-- ── tweens ───────────────────────────────────────────────────────────

-- Each tween walks [first, last], creating missing cels from source_frame
-- (default: first) when asked, and applies `step(cel, eased_t, raw_t)`.
local function tween(sprite, a, step)
  local layer = lib.layer(sprite, a.name)
  local first, last = lib.frame_range(sprite, a.first, a.last)
  local ease = EASINGS[a.easing or "linear"] or lib.fail("UnknownEasing", "Unsupported easing " .. tostring(a.easing))
  for index = first, last do
    local t = progress(index, first, last)
    local cel = ensure_cel(sprite, layer, sprite.frames[index], a.create_missing, a.source_frame or first)
    if cel then step(cel, ease(t), t) end
  end
end

lib.edit("animation.tween_position", function(sprite, a)
  tween(sprite, a, function(cel, e)
    cel.position = Point(round(a.start_x + (a.end_x - a.start_x) * e), round(a.start_y + (a.end_y - a.start_y) * e))
  end)
end)

lib.edit("animation.tween_opacity", function(sprite, a)
  tween(sprite, a, function(cel, e)
    cel.opacity = math.max(0, math.min(255, round(a.start_opacity + (a.end_opacity - a.start_opacity) * e)))
  end)
end)

lib.edit("animation.oscillate", function(sprite, a)
  local phase = a.phase_deg * math.pi / 180
  tween(sprite, a, function(cel, _, t)
    local angle = 2 * math.pi * a.cycles * t + phase
    cel.position = Point(cel.position.x + round(a.amplitude_x * math.sin(angle)),
                         cel.position.y + round(a.amplitude_y * math.cos(angle)))
  end)
end)

-- Rebuilds each frame's cel from a scaled copy of the source cel's image.
lib.edit("animation.tween_scale", function(sprite, a)
  local layer = lib.layer(sprite, a.name)
  local first, last = lib.frame_range(sprite, a.first, a.last)
  local ease = EASINGS[a.easing] or lib.fail("UnknownEasing", "Unsupported easing " .. tostring(a.easing))
  local source_index = a.source_frame or first
  local source = layer:cel(lib.frame(sprite, source_index, "Source frame out of range"))
    or lib.fail("NoSourceCel", "Source cel not found")
  local base = source.image:clone()
  local base_x, base_y, base_w, base_h = source.position.x, source.position.y, base.width, base.height
  for index = first, last do
    local scale = a.start_scale + (a.end_scale - a.start_scale) * ease(progress(index, first, last))
    local w = math.max(1, round(base_w * scale))
    local h = math.max(1, round(base_h * scale))
    local frame = sprite.frames[index]
    local existing = layer:cel(frame)
    if existing and a.replace then sprite:deleteCel(existing) existing = nil end
    if not existing and a.create_missing then
      local image = base:clone()
      image:resize(w, h)
      local x, y = base_x, base_y
      if a.anchor == "center" then
        x = round(base_x + base_w / 2 - w / 2)
        y = round(base_y + base_h / 2 - h / 2)
      end
      sprite:newCel(layer, frame, image, Point(x, y))
    end
  end
end)

-- ── tags ─────────────────────────────────────────────────────────────

lib.edit("animation.set_tag", function(sprite, a)
  local first, last = lib.frame_range(sprite, a.first, a.last)
  local tag = lib.find_tag(sprite, a.name)
  if tag then
    tag.fromFrame = sprite.frames[first]
    tag.toFrame = sprite.frames[last]
  else
    tag = sprite:newTag(first, last)
  end
  tag.name = a.name
  tag.aniDir = AniDir[a.direction]
end)

lib.edit("animation.delete_tag", function(sprite, a)
  sprite:deleteTag(lib.find_tag(sprite, a.name) or lib.fail("TagNotFound", "Tag not found"))
end)

-- ── inspection ───────────────────────────────────────────────────────

local COLOR_MODES = { [ColorMode.RGB] = "rgb", [ColorMode.INDEXED] = "indexed", [ColorMode.GRAY] = "gray" }
local DIRECTIONS = {
  [AniDir.FORWARD] = "forward", [AniDir.REVERSE] = "reverse",
  [AniDir.PING_PONG] = "pingpong", [AniDir.PING_PONG_REVERSE] = "pingpong_reverse",
}

lib.read("animation.sprite_info", function(sprite)
  local durations, layers, tags = {}, {}, {}
  for i, frame in ipairs(sprite.frames) do durations[i] = round(frame.duration * 1000) end
  -- Depth-first, so each group is followed by its children; `parent` is the
  -- immediate parent group's name (absent at the top level).
  local function walk(list, parent)
    for _, layer in ipairs(list) do
      layers[#layers + 1] = { name = layer.name, visible = layer.isVisible, opacity = layer.opacity or 255,
                              is_group = layer.isGroup, parent = parent }
      if layer.isGroup then walk(layer.layers, layer.name) end
    end
  end
  walk(sprite.layers, nil)
  for i, tag in ipairs(sprite.tags) do
    tags[i] = { name = tag.name, from = tag.fromFrame.frameNumber, to = tag.toFrame.frameNumber,
                direction = DIRECTIONS[tag.aniDir] or tostring(tag.aniDir) }
  end
  return { width = sprite.width, height = sprite.height, color_mode = COLOR_MODES[sprite.colorMode] or "unknown",
           frames = #sprite.frames, durations_ms = durations, layers = layers, tags = tags }
end)
