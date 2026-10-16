-- Rectangular region ops (tools/selection.py). Coordinates are sprite
-- coordinates; reads and writes outside the canvas are ignored.
local lib = ...

-- The pixels of the region as rows of values, read before anything is written
-- so overlapping source and destination behave.
local function grab(get, a)
  local rows = {}
  for ry = 0, a.height - 1 do
    local row = {}
    for rx = 0, a.width - 1 do row[rx] = get(a.x + rx, a.y + ry) end
    rows[ry] = row
  end
  return rows
end

-- Writes the grabbed pixels at (x, y); transparent ones leave the destination alone.
local function paste(put, rows, a, x, y)
  for ry = 0, a.height - 1 do
    for rx = 0, a.width - 1 do
      local v = rows[ry][rx]
      if app.pixelColor.rgbaA(v) > 0 then put(x + rx, y + ry, v) end
    end
  end
end

local function each_in_region(a, fn)
  for y = a.y, a.y + a.height - 1 do
    for x = a.x, a.x + a.width - 1 do fn(x, y) end
  end
end

local function existing_paint_cel(sprite, a)
  local layer, frame = lib.layer(sprite, a.layer), lib.frame(sprite, a.frame)
  return lib.paint_cel(sprite, layer, frame, false) or lib.cel(layer, frame)
end

lib.edit("selection.move", function(sprite, a)
  local cel = existing_paint_cel(sprite, a)
  local get, put = lib.reader(sprite, cel), lib.painter(sprite, cel)
  local rows = grab(get, a)
  each_in_region(a, function(x, y) put(x, y, 0) end)
  paste(put, rows, a, a.dest_x, a.dest_y)
end)

-- Reads the source cel without changing it; creates the destination cel.
lib.edit("selection.copy", function(sprite, a)
  local source_frame = lib.frame(sprite, a.frame, "Source frame index out of range")
  local target_frame = lib.frame(sprite, a.target_frame, "Target frame index out of range")
  local source_layer = lib.layer(sprite, a.layer, "Source layer not found")
  local target_layer = lib.layer(sprite, a.target_layer, "Target layer not found")
  local source = source_layer:cel(source_frame) or lib.fail("NoCel", "No cel at source layer/frame")
  local rows = grab(lib.reader(sprite, source), a)
  local target = lib.paint_cel(sprite, target_layer, target_frame, true)
  paste(lib.painter(sprite, target), rows, a, a.dest_x, a.dest_y)
end)

lib.edit("selection.erase", function(sprite, a)
  local put = lib.painter(sprite, existing_paint_cel(sprite, a))
  each_in_region(a, function(x, y) put(x, y, 0) end)
end)

lib.edit("selection.erase_color", function(sprite, a)
  local cel = lib.cel(lib.layer(sprite, a.layer), lib.frame(sprite, a.frame))
  local count = lib.map_opaque(cel, function(r, g, b)
    if lib.near(r, g, b, a.color, a.tolerance) then return 0 end
  end)
  return { count = count }
end)
