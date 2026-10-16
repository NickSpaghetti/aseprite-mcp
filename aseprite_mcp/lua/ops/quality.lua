-- Animation consistency ops (tools/quality.py).
--
-- Layers are named by the caller and resolved once with lib.find_layer, so
-- layers inside groups count. With no names, every image layer is a target.
-- Targets are kept in a list and compared with `==`: Aseprite hands out a new
-- userdata wrapper on every read, so a table keyed by layer never matches.
--
-- `ranges` arrive as [[name, [[first, last], ...]], ...] and `pairs` as
-- [[name_a, name_b], ...], both already parsed and checked in Python.
local lib = ...

local function frames(sprite, a)
  return lib.frame_range(sprite, a.first, a.last or #sprite.frames)
end

local function index_of(list, layer)
  for i, item in ipairs(list) do
    if item == layer then return i end
  end
  return nil
end

local function targets(sprite, names)
  if not names then return lib.image_layers(sprite) end
  local list = {}
  for _, name in ipairs(names) do
    local layer = lib.find_layer(sprite, name)
    if layer and not index_of(list, layer) then list[#list + 1] = layer end
  end
  return list
end

-- Spans per target index, from the parsed ranges. Unknown names are ignored.
local function ranges_by_target(sprite, list, ranges)
  local by_index = {}
  for _, entry in ipairs(ranges or {}) do
    local i = index_of(list, lib.find_layer(sprite, entry[1]))
    if i then by_index[i] = entry[2] end
  end
  return function(i, frame)
    local spans = by_index[i]
    if not spans then return true end
    for _, span in ipairs(spans) do
      if frame >= span[1] and frame <= span[2] then return true end
    end
    return false
  end
end

-- Pairs of target indexes; pairs naming a non-target layer are ignored.
local function target_pairs(sprite, list, pairs)
  local resolved = {}
  for _, p in ipairs(pairs or {}) do
    local i, j = index_of(list, lib.find_layer(sprite, p[1])), index_of(list, lib.find_layer(sprite, p[2]))
    if i and j then resolved[#resolved + 1] = { i, j } end
  end
  return resolved
end

local function bounds(cel)
  return { cel.position.x, cel.position.y, cel.image.width, cel.image.height }
end

local function overlap(ra, rb)
  return ra[1] < rb[1] + rb[3] and ra[1] + ra[3] > rb[1] and ra[2] < rb[2] + rb[4] and ra[2] + ra[4] > rb[2]
end

local function full_canvas(sprite, cel)
  return cel.image.width == sprite.width and cel.image.height == sprite.height
end

-- ── ensure / validate ────────────────────────────────────────────────

lib.edit("quality.ensure_layers", function(sprite, a)
  local first, last = frames(sprite, a)
  local list = {}
  for _, layer in ipairs(targets(sprite, a.names)) do
    if not layer.isGroup then list[#list + 1] = layer end
  end
  if #list == 0 then lib.fail("NoLayersFound", "No layers found") end
  for index = first, last do
    for _, layer in ipairs(list) do
      lib.ensure_cel(sprite, layer, sprite.frames[index], true, index)
    end
  end
end)

lib.read("quality.validate", function(sprite, a)
  local first, last = frames(sprite, a)
  local missing_layers, missing_cels = {}, {}
  for _, name in ipairs(a.names) do
    local layer = lib.find_layer(sprite, name)
    if not layer then
      missing_layers[#missing_layers + 1] = name
    else
      for index = first, last do
        if not layer:cel(sprite.frames[index]) then
          missing_cels[#missing_cels + 1] = { layer = name, frame = index }
        end
      end
    end
  end
  return { frames = #sprite.frames, first = first, last = last,
           missing_layers = missing_layers, missing_cels = missing_cels }
end)

-- ── audit ────────────────────────────────────────────────────────────

lib.read("quality.audit", function(sprite, a)
  local first, last = frames(sprite, a)
  local list = targets(sprite, a.names)
  local in_range = ranges_by_target(sprite, list, a.ranges)
  local pair_list = target_pairs(sprite, list, a.pairs)
  local overlaps, overlaps_total, truncated = {}, 0, false
  local out_of_range, cel_entries, total_cels = {}, {}, 0

  for index = first, last do
    local frame = sprite.frames[index]
    local frame_cels = {}
    for i, layer in ipairs(list) do
      local cel = layer:cel(frame)
      if cel then
        total_cels = total_cels + 1
        if a.report_cels then
          local entry = { layer = layer.name }
          if a.report_bounds then
            local b = bounds(cel)
            entry.x, entry.y, entry.w, entry.h = b[1], b[2], b[3], b[4]
          end
          frame_cels[#frame_cels + 1] = entry
        end
        if not in_range(i, index) and #out_of_range < a.max_out_of_range then
          out_of_range[#out_of_range + 1] = { frame = index, layer = layer.name }
        end
      end
    end
    if a.report_cels then cel_entries[#cel_entries + 1] = { frame = index, cels = frame_cels } end

    for _, p in ipairs(pair_list) do
      local cel_a, cel_b = list[p[1]]:cel(frame), list[p[2]]:cel(frame)
      if cel_a and cel_b and overlap(bounds(cel_a), bounds(cel_b)) then
        overlaps_total = overlaps_total + 1
        if #overlaps < a.max_overlaps then
          local entry = { frame = index, a = list[p[1]].name, b = list[p[2]].name }
          if a.report_bounds then entry.a_bounds, entry.b_bounds = bounds(cel_a), bounds(cel_b) end
          overlaps[#overlaps + 1] = entry
        else
          truncated = true
        end
      end
    end
  end

  return { first = first, last = last, total_layers = #sprite.layers, layers_checked = #list,
           total_cels = total_cels, overlaps = overlaps, overlaps_total = overlaps_total,
           overlaps_truncated = truncated, out_of_range = out_of_range,
           cels = a.report_cels and cel_entries or nil }
end)

-- ── sanitize ─────────────────────────────────────────────────────────

-- Reorders top-level layers so the named ones come first (bottom of the
-- stack). Skipped when the sprite has groups.
local function reorder(sprite, names, apply)
  for _, layer in ipairs(sprite.layers) do
    if layer.isGroup then return false end
  end
  if apply then
    local ordered = {}
    for _, name in ipairs(names) do
      for _, layer in ipairs(sprite.layers) do
        if layer.name == name and not index_of(ordered, layer) then
          ordered[#ordered + 1] = layer
          break
        end
      end
    end
    for _, layer in ipairs(sprite.layers) do
      if not index_of(ordered, layer) then ordered[#ordered + 1] = layer end
    end
    for i, layer in ipairs(ordered) do layer.stackIndex = i end
  end
  return true
end

-- With `apply` false nothing is changed; the counts say what would be.
local function sanitize(sprite, a, apply)
  local first, last = frames(sprite, a)
  local list = targets(sprite, a.names)
  local in_range = ranges_by_target(sprite, list, a.ranges)
  local pair_list = target_pairs(sprite, list, a.pairs)
  local result = { first = first, last = last, reordered = false, ensured = 0, out_of_range = 0,
                   opacity_set = 0, deleted = 0, empty_frames = 0, overlaps = 0, overlaps_truncated = false,
                   overlap_samples = {} }

  if a.order then result.reordered = reorder(sprite, a.order, apply) end

  for _, name in ipairs(a.ensure or {}) do
    local layer = lib.find_layer(sprite, name)
    if layer and not layer.isGroup then
      for index = first, last do
        if not layer:cel(sprite.frames[index]) then
          result.ensured = result.ensured + 1
          if apply then lib.ensure_cel(sprite, layer, sprite.frames[index], true, index) end
        end
      end
    end
  end

  local stats = {}
  for i, layer in ipairs(list) do
    stats[i] = { name = layer.name, frames_active = 0, cel_count = 0, full_canvas_cels = 0 }
  end
  local total_cels = 0

  for index = first, last do
    local frame = sprite.frames[index]
    local any_cel = false
    for i, layer in ipairs(list) do
      local cel = layer:cel(frame)
      if cel then
        any_cel = true
        total_cels = total_cels + 1
        local s, b = stats[i], bounds(cel)
        s.cel_count = s.cel_count + 1
        s.frames_active = s.frames_active + 1
        if full_canvas(sprite, cel) then s.full_canvas_cels = s.full_canvas_cels + 1 end
        if s.bounds then
          s.bounds = { math.min(s.bounds[1], b[1]), math.min(s.bounds[2], b[2]),
                       math.max(s.bounds[3], b[1] + b[3]), math.max(s.bounds[4], b[2] + b[4]) }
        else
          s.bounds = { b[1], b[2], b[1] + b[3], b[2] + b[4] }
        end
        if not in_range(i, index) then
          result.out_of_range = result.out_of_range + 1
          if apply and a.action == "delete_cels" then
            sprite:deleteCel(cel)
            result.deleted = result.deleted + 1
          elseif apply and a.action == "set_opacity_zero" then
            cel.opacity = a.opacity
            result.opacity_set = result.opacity_set + 1
          end
        end
      end
    end
    if not any_cel then result.empty_frames = result.empty_frames + 1 end

    for _, p in ipairs(pair_list) do
      local cel_a, cel_b = list[p[1]]:cel(frame), list[p[2]]:cel(frame)
      local skip = a.ignore_full_canvas and cel_a and cel_b
        and (full_canvas(sprite, cel_a) or full_canvas(sprite, cel_b))
      if cel_a and cel_b and not skip and overlap(bounds(cel_a), bounds(cel_b)) then
        result.overlaps = result.overlaps + 1
        if #result.overlap_samples < a.max_overlaps then
          local entry = { frame = index, a = list[p[1]].name, b = list[p[2]].name }
          if a.report_bounds then entry.a_bounds, entry.b_bounds = bounds(cel_a), bounds(cel_b) end
          result.overlap_samples[#result.overlap_samples + 1] = entry
        else
          result.overlaps_truncated = true
        end
      end
    end
  end

  result.total_layers, result.layers_checked, result.total_cels = #sprite.layers, #list, total_cels
  result.stats = stats
  return result
end

lib.edit("quality.sanitize", function(sprite, a) return sanitize(sprite, a, true) end)
lib.read("quality.sanitize_report", function(sprite, a) return sanitize(sprite, a, false) end)
