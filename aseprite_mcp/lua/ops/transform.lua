-- Flip, rotate, resize and crop ops (tools/transform.py).
--
-- Flip and rotate work on one cel's image in place: the image turns about its
-- own bounds and the cel keeps its top-left position.
local lib = ...

local function target_cel(sprite, a)
  return lib.cel(lib.layer(sprite, a.layer), lib.frame(sprite, a.frame))
end

-- Rebuilds `cel`'s image as a `w` x `h` image where pixel (x, y) comes from
-- source(x, y) of the original.
local function remap(cel, w, h, source)
  local old = cel.image:clone()
  local image = Image(w, h, old.colorMode)
  for y = 0, h - 1 do
    for x = 0, w - 1 do
      local sx, sy = source(x, y, old.width, old.height)
      image:putPixel(x, y, old:getPixel(sx, sy))
    end
  end
  cel.image = image
end

local FLIPS = {
  horizontal = function(x, y, w) return w - 1 - x, y end,
  vertical = function(x, y, _, h) return x, h - 1 - y end,
}

-- Clockwise. Each maps a pixel of the rotated image back to the original.
local ROTATIONS = {
  [90] = function(x, y, _, h) return y, h - 1 - x end,
  [180] = function(x, y, w, h) return w - 1 - x, h - 1 - y end,
  [270] = function(x, y, w) return w - 1 - y, x end,
}

lib.edit("transform.flip", function(sprite, a)
  local cel = target_cel(sprite, a)
  remap(cel, cel.image.width, cel.image.height, FLIPS[a.direction])
end)

lib.edit("transform.rotate", function(sprite, a)
  local cel = target_cel(sprite, a)
  local w, h = cel.image.width, cel.image.height
  if a.angle ~= 180 then w, h = h, w end
  remap(cel, w, h, ROTATIONS[a.angle])
end)

lib.edit("transform.resize", function(sprite, a)
  sprite:resize(a.width, a.height)
end)

lib.edit("transform.crop", function(sprite, a)
  if a.x >= sprite.width or a.y >= sprite.height or a.x + a.width <= 0 or a.y + a.height <= 0 then
    lib.fail("CropOutside", "Crop rect is fully outside the canvas")
  end
  sprite:crop(a.x, a.y, a.width, a.height)
end)
