-- Palette and colour-mode ops (tools/palette.py). Colours arrive as [r, g, b, a].
local lib = ...

local rgba, R, G, B, A = app.pixelColor.rgba, app.pixelColor.rgbaR, app.pixelColor.rgbaG,
  app.pixelColor.rgbaB, app.pixelColor.rgbaA

local function rgb_key(r, g, b) return (r << 16) | (g << 8) | b end

lib.read("palette.get", function(sprite)
  local palette, colors = sprite.palettes[1], {}
  for i = 0, #palette - 1 do
    local c = palette:getColor(i)
    colors[#colors + 1] = string.format("#%02X%02X%02X", c.red, c.green, c.blue)
  end
  return { colors = colors }
end)

-- Palette entries are opaque; any alpha in the colours is ignored.
lib.edit("palette.set", function(sprite, a)
  local palette = Palette(#a.colors)
  for i, c in ipairs(a.colors) do palette:setColor(i - 1, Color(c[1], c[2], c[3])) end
  sprite:setPalette(palette)
end)

-- Rewrites matching RGB values across the frame range, keeping each pixel's
-- alpha. When one colour has several mappings, the first one listed wins.
lib.edit("palette.remap", function(sprite, a)
  local first, last = lib.frame_range(sprite, a.first, a.last)
  local layer = lib.layer(sprite, a.layer)
  local source_index = a.source_frame or first
  lib.frame(sprite, source_index, "Source frame out of range")
  local to = {}
  for _, m in ipairs(a.mappings) do
    local key = rgb_key(m[1][1], m[1][2], m[1][3])
    if to[key] == nil then to[key] = m[2] end
  end
  for index = first, last do
    local cel = lib.ensure_cel(sprite, layer, sprite.frames[index], a.create_missing, source_index)
    if cel then
      for it in cel.image:pixels() do
        local v = it()
        local alpha = A(v)
        if alpha > 0 then
          local c = to[rgb_key(R(v), G(v), B(v))]
          if c then it(rgba(c[1], c[2], c[3], alpha)) end
        end
      end
    end
  end
end)

-- Snaps every opaque pixel to the nearest palette colour (RGB distance),
-- keeping alpha. With no `layer`, every image layer, groups included.
lib.edit("palette.quantize", function(sprite, a)
  local palette = sprite.palettes[1]
  if #palette == 0 then lib.fail("NoPalette", "No palette") end
  local last = a.last
  if last < 1 then last = #sprite.frames end
  local first
  first, last = lib.frame_range(sprite, a.first, last)
  local layers = a.layer and { lib.layer(sprite, a.layer) } or lib.image_layers(sprite)

  local colors = {}
  for i = 0, #palette - 1 do
    local c = palette:getColor(i)
    colors[#colors + 1] = { c.red, c.green, c.blue }
  end
  local cache = {}
  local function nearest(r, g, b)
    local key = rgb_key(r, g, b)
    local hit = cache[key]
    if hit then return hit end
    local best, best_d = colors[1], math.huge
    for _, c in ipairs(colors) do
      local dr, dg, db = r - c[1], g - c[2], b - c[3]
      local d = dr * dr + dg * dg + db * db
      if d < best_d then best, best_d = c, d end
    end
    cache[key] = best
    return best
  end

  local count = 0
  for _, layer in ipairs(layers) do
    for index = first, last do
      local cel = layer:cel(sprite.frames[index])
      if cel then
        for it in cel.image:pixels() do
          local v = it()
          local alpha = A(v)
          if alpha > 0 then
            local r, g, b = R(v), G(v), B(v)
            local c = nearest(r, g, b)
            if c[1] ~= r or c[2] ~= g or c[3] ~= b then
              it(rgba(c[1], c[2], c[3], alpha))
              count = count + 1
            end
          end
        end
      end
    end
  end
  return { count = count }
end)

lib.edit("palette.set_color_mode", function(_, a)
  app.command.ChangePixelFormat { format = a.mode }
end)
