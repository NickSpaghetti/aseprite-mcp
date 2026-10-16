-- Drawing ops (tools/drawing.py).
--
-- Every op takes either `layer` + `frame` (the *_at tools) or neither (the
-- older tools, which draw on lib.default_target, the sprite's only layer,
-- and never create a cel).
-- Coordinates are sprite coordinates. Colours arrive as [r, g, b, a].
--
-- Two ways of putting pixels down:
--   * Pixel ops (pixels, path, polygon, gradient) write through lib.painter
--     on a cel from lib.paint_cel, so nothing outside a small cel is lost.
--   * Shape ops (rectangle, ellipse, fill) use app.useTool, so the result
--     matches Aseprite's own tools, bucket-fill rules included.
local lib = ...

local function target(sprite, a)
  if a.layer then return lib.layer(sprite, a.layer), lib.frame(sprite, a.frame) end
  return lib.default_target(sprite)
end

local function painter(sprite, a)
  local layer, frame = target(sprite, a)
  -- paint_cel returns nil only when there is no cel and none may be created;
  -- lib.cel then raises NoCel.
  local cel = lib.paint_cel(sprite, layer, frame, a.create) or lib.cel(layer, frame)
  return lib.painter(sprite, cel)
end

-- A square brush of side `size` (1 = a single pixel).
local function stamp(put, x, y, color, size)
  local r = math.max(0, math.floor(size / 2))
  if size <= 1 then r = 0 end
  for oy = -r, r do
    for ox = -r, r do put(x + ox, y + oy, color) end
  end
end

-- Bresenham from (x0, y0) to (x1, y1), inclusive.
local function line(put, x0, y0, x1, y1, color, size)
  local dx = math.abs(x1 - x0)
  local sx = x0 < x1 and 1 or -1
  local dy = -math.abs(y1 - y0)
  local sy = y0 < y1 and 1 or -1
  local err = dx + dy
  while true do
    stamp(put, x0, y0, color, size)
    if x0 == x1 and y0 == y1 then break end
    local e2 = 2 * err
    if e2 >= dy then err = err + dy; x0 = x0 + sx end
    if e2 <= dx then err = err + dx; y0 = y0 + sy end
  end
end

-- Even-odd scanline fill between polygon edges.
local function fill_polygon(put, points, color)
  local min_y, max_y = points[1][2], points[1][2]
  for _, p in ipairs(points) do
    min_y = math.min(min_y, p[2])
    max_y = math.max(max_y, p[2])
  end
  for y = min_y, max_y do
    local nodes = {}
    local j = #points
    for i = 1, #points do
      local xi, yi = points[i][1], points[i][2]
      local xj, yj = points[j][1], points[j][2]
      if (yi < y and yj >= y) or (yj < y and yi >= y) then
        nodes[#nodes + 1] = xi + (y - yi) * (xj - xi) / (yj - yi)
      end
      j = i
    end
    table.sort(nodes)
    for k = 1, #nodes - 1, 2 do
      for x = math.floor(nodes[k] + 0.5), math.floor(nodes[k + 1] + 0.5) do put(x, y, color) end
    end
  end
end

local function use_tool(sprite, a, tool, points)
  local layer, frame = target(sprite, a)
  if not layer:cel(frame) then
    if not a.create then lib.cel(layer, frame) end  -- raises NoCel
    sprite:newCel(layer, frame, Image(sprite.width, sprite.height, sprite.colorMode), Point(0, 0))
  end
  app.activeLayer = layer
  app.activeFrame = frame
  app.useTool { tool = tool, color = lib.color(a.color), points = points }
end

-- ── pixel ops ────────────────────────────────────────────────────────

lib.edit("drawing.pixels", function(sprite, a)
  local put = painter(sprite, a)
  for _, p in ipairs(a.pixels) do put(p[1], p[2], lib.color(p[3])) end
end)

-- An open polyline; a line is a path of two points.
lib.edit("drawing.path", function(sprite, a)
  local put, color, pts = painter(sprite, a), lib.color(a.color), a.points
  for i = 1, #pts - 1 do
    line(put, pts[i][1], pts[i][2], pts[i + 1][1], pts[i + 1][2], color, a.thickness)
  end
end)

lib.edit("drawing.polygon", function(sprite, a)
  local put, color, pts = painter(sprite, a), lib.color(a.color), a.points
  if a.fill then fill_polygon(put, pts, color) end
  for i = 1, #pts do
    local n = i % #pts + 1
    line(put, pts[i][1], pts[i][2], pts[n][1], pts[n][2], color, 1)
  end
end)

lib.edit("drawing.gradient", function(sprite, a)
  local put = painter(sprite, a)
  local from, to = a.color_start, a.color_end
  for iy = 0, a.height - 1 do
    for ix = 0, a.width - 1 do
      local t
      if a.horizontal then
        t = a.width > 1 and ix / (a.width - 1) or 0
      else
        t = a.height > 1 and iy / (a.height - 1) or 0
      end
      local c = {}
      for k = 1, 4 do c[k] = math.floor(from[k] + (to[k] - from[k]) * t + 0.5) end
      put(a.x + ix, a.y + iy, lib.color(c))
    end
  end
end)

-- ── shape ops (Aseprite's tools) ─────────────────────────────────────

-- Both corners are inclusive.
lib.edit("drawing.rectangle", function(sprite, a)
  use_tool(sprite, a, a.fill and "filled_rectangle" or "rectangle",
           { Point(a.x, a.y), Point(a.x + a.width - 1, a.y + a.height - 1) })
end)

lib.edit("drawing.ellipse", function(sprite, a)
  use_tool(sprite, a, a.fill and "filled_ellipse" or "ellipse",
           { Point(a.cx - a.rx, a.cy - a.ry), Point(a.cx + a.rx, a.cy + a.ry) })
end)

lib.edit("drawing.fill", function(sprite, a)
  use_tool(sprite, a, "paint_bucket", { Point(a.x, a.y) })
end)
