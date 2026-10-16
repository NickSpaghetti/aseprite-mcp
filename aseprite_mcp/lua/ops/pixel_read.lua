-- Pixel reads (tools/pixel_read.py). Coordinates are sprite coordinates; a
-- pixel outside the source reads as transparent black. Results are rows of
-- [x, y, r, g, b, a], row by row.
local lib = ...

local function rect(get, a)
  local pixels = {}
  for y = a.y, a.y + a.height - 1 do
    for x = a.x, a.x + a.width - 1 do
      local c = lib.rgba(get(x, y))
      pixels[#pixels + 1] = { x, y, c[1], c[2], c[3], c[4] }
    end
  end
  return { pixels = pixels }
end

-- One cel. With no `layer`, the default target's cel on `frame`.
lib.read("pixel_read.cel", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  local cel
  if a.layer then
    cel = lib.cel(lib.layer(sprite, a.layer), frame)
  else
    cel = (lib.default_target(sprite)):cel(frame) or lib.fail("NoCel", "No active cel")
  end
  return rect(lib.reader(sprite, cel), a)
end)

-- What is visible: every visible layer composited.
lib.read("pixel_read.composite", function(sprite, a)
  local image = lib.composite(sprite, lib.frame(sprite, a.frame).frameNumber)
  return rect(function(x, y)
    if x < 0 or y < 0 or x >= image.width or y >= image.height then return 0 end
    return image:getPixel(x, y)
  end, a)
end)
