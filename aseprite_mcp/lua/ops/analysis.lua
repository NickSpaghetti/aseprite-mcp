-- Visual feedback ops (tools/analysis.py). All work on lib.composite, so
-- they see what the player sees.
local lib = ...

local function composite(sprite, index)
  return lib.composite(sprite, lib.frame(sprite, index).frameNumber)
end

-- Two pixels differ unless both are fully transparent or both are identical.
lib.read("analysis.compare", function(sprite, a)
  local image_a, image_b = composite(sprite, a.frame_a), composite(sprite, a.frame_b)
  local changed, min_x, min_y, max_x, max_y = 0, nil, nil, nil, nil
  local A = app.pixelColor.rgbaA
  for y = 0, image_a.height - 1 do
    for x = 0, image_a.width - 1 do
      local va, vb = image_a:getPixel(x, y), image_b:getPixel(x, y)
      if va ~= vb and (A(va) > 0 or A(vb) > 0) then
        changed = changed + 1
        min_x, min_y = math.min(min_x or x, x), math.min(min_y or y, y)
        max_x, max_y = math.max(max_x or x, x), math.max(max_y or y, y)
      end
    end
  end
  local result = { changed = changed, total = image_a.width * image_a.height }
  if changed > 0 then
    result.bounds = { x = min_x, y = min_y, width = max_x - min_x + 1, height = max_y - min_y + 1 }
  end
  return result
end)

-- Opaque pixels counted by RGB colour (alpha ignored).
lib.read("analysis.color_stats", function(sprite, a)
  local counts, opaque = {}, 0
  for it in composite(sprite, a.frame):pixels() do
    local c = lib.rgba(it())
    if c[4] > 0 then
      opaque = opaque + 1
      local hex = string.format("#%02X%02X%02X", c[1], c[2], c[3])
      counts[hex] = (counts[hex] or 0) + 1
    end
  end
  local colors = {}
  for hex, count in pairs(counts) do colors[#colors + 1] = { color = hex, count = count } end
  return { opaque = opaque, colors = colors }
end)

-- The frame over white, with ghosts of neighbouring frames (oldest first, so
-- nearer frames land on top), scaled up by an integer factor and saved as PNG.
lib.read("analysis.onion_skin", function(sprite, a)
  local index = lib.frame(sprite, a.frame).frameNumber
  local comp = Image(sprite.width, sprite.height, ColorMode.RGB)
  comp:clear(Color(255, 255, 255))
  for offset = a.before, 1, -1 do
    if index - offset >= 1 then
      comp:drawImage(lib.composite(sprite, index - offset), Point(0, 0), a.ghost_opacity, BlendMode.NORMAL)
    end
  end
  for offset = a.after, 1, -1 do
    if index + offset <= #sprite.frames then
      comp:drawImage(lib.composite(sprite, index + offset), Point(0, 0), a.ghost_opacity, BlendMode.NORMAL)
    end
  end
  comp:drawImage(lib.composite(sprite, index), Point(0, 0), 255, BlendMode.NORMAL)

  lib.scale_image(comp, a.scale):saveAs(a.output)
end)
