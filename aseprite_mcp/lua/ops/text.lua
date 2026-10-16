-- Text drawing (tools/text.py). Glyphs are rasterised in Python, since the
-- Lua API has no text drawing; this op blits the finished stamp.
--
-- The stamp is `width` x `height` with its top-left at (x, y) in sprite
-- coordinates; `pixels` are [sx, sy, colour_index] within it, and `colors`
-- the [r, g, b, a] each index stands for. Pixels landing off the canvas are
-- dropped. The stamp is blended over what is there.
local lib = ...

lib.edit("text.draw", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  local layer
  if a.layer then
    layer = lib.find_layer(sprite, a.layer)
    if not layer then
      if not a.create then lib.fail("LayerNotFound", "Layer not found") end
      layer = sprite:newLayer()
      layer.name = a.layer
    end
  else
    layer = lib.default_target(sprite)
  end

  local colors = {}
  for i, c in ipairs(a.colors) do colors[i] = lib.color(c) end
  local stamp = Image(a.width, a.height, ColorMode.RGB)
  for _, p in ipairs(a.pixels) do
    local x, y = a.x + p[1], a.y + p[2]
    if x >= 0 and y >= 0 and x < sprite.width and y < sprite.height then
      stamp:putPixel(p[1], p[2], colors[p[3]])
    end
  end

  local cel = lib.paint_cel(sprite, layer, frame, true)
  cel.image:drawImage(stamp, Point(a.x - cel.position.x, a.y - cel.position.y), 255, BlendMode.NORMAL)
end)
