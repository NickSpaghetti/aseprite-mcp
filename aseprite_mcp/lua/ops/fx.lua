-- Hand-rolled pixel effects (tools/fx.py). Colours arrive as [r, g, b, a].
local lib = ...

local rgba, R, G, B, A = app.pixelColor.rgba, app.pixelColor.rgbaR, app.pixelColor.rgbaG,
  app.pixelColor.rgbaB, app.pixelColor.rgbaA

-- RGB <-> HSL. h in [0, 360), s and l in [0, 1].
local function rgb_to_hsl(r, g, b)
  r, g, b = r / 255, g / 255, b / 255
  local maxc, minc = math.max(r, g, b), math.min(r, g, b)
  local l = (maxc + minc) / 2
  if maxc == minc then return 0, 0, l end
  local d = maxc - minc
  local s = l > 0.5 and d / (2 - maxc - minc) or d / (maxc + minc)
  local h
  if maxc == r then
    h = (g - b) / d
    if g < b then h = h + 6 end
  elseif maxc == g then
    h = (b - r) / d + 2
  else
    h = (r - g) / d + 4
  end
  return h * 60, s, l
end

local function hsl_to_rgb(h, s, l)
  h = h % 360
  if s <= 0 then
    local v = math.floor(l * 255 + 0.5)
    return v, v, v
  end
  local c = (1 - math.abs(2 * l - 1)) * s
  local hp = h / 60
  local x = c * (1 - math.abs(hp % 2 - 1))
  local r1, g1, b1
  if hp < 1 then r1, g1, b1 = c, x, 0
  elseif hp < 2 then r1, g1, b1 = x, c, 0
  elseif hp < 3 then r1, g1, b1 = 0, c, x
  elseif hp < 4 then r1, g1, b1 = 0, x, c
  elseif hp < 5 then r1, g1, b1 = x, 0, c
  else r1, g1, b1 = c, 0, x end
  local m = l - c / 2
  return math.floor((r1 + m) * 255 + 0.5), math.floor((g1 + m) * 255 + 0.5), math.floor((b1 + m) * 255 + 0.5)
end

-- Calls fn(r, g, b, a) for every opaque pixel of the existing cel; when fn
-- returns r, g, b the pixel is rewritten with its alpha kept. Returns the
-- number of pixels rewritten.
local function map_opaque(sprite, a, fn)
  local cel = lib.cel(lib.layer(sprite, a.layer), lib.frame(sprite, a.frame))
  local count = 0
  for it in cel.image:pixels() do
    local v = it()
    local alpha = A(v)
    if alpha > 0 then
      local r, g, b = fn(R(v), G(v), B(v), alpha)
      if r then
        it(rgba(r, g, b, alpha))
        count = count + 1
      end
    end
  end
  return count
end

lib.edit("fx.replace_color", function(sprite, a)
  local from, to, tol = a.from_color, a.to_color, a.tolerance
  local count = map_opaque(sprite, a, function(r, g, b)
    if math.abs(r - from[1]) <= tol and math.abs(g - from[2]) <= tol and math.abs(b - from[3]) <= tol then
      return to[1], to[2], to[3]
    end
  end)
  return { count = count }
end)

lib.edit("fx.adjust_hsl", function(sprite, a)
  map_opaque(sprite, a, function(r, g, b)
    local h, s, l = rgb_to_hsl(r, g, b)
    s = math.min(1, math.max(0, s + a.saturation / 100))
    l = math.min(1, math.max(0, l + a.lightness / 100))
    return hsl_to_rgb(h + a.hue, s, l)
  end)
end)

-- Fills every transparent pixel that touches an opaque one (4 neighbours, or 8
-- with diagonals). Reads from a copy so new outline pixels don't spread.
lib.edit("fx.outline", function(sprite, a)
  local layer, frame = lib.layer(sprite, a.layer), lib.frame(sprite, a.frame)
  local cel = lib.paint_cel(sprite, layer, frame, false) or lib.cel(layer, frame)
  local image = cel.image
  local src = image:clone()
  local color = lib.color(a.color)
  local function opaque(x, y)
    return x >= 0 and y >= 0 and x < src.width and y < src.height and A(src:getPixel(x, y)) > 0
  end
  for y = 0, image.height - 1 do
    for x = 0, image.width - 1 do
      if not opaque(x, y) then
        local touch = opaque(x - 1, y) or opaque(x + 1, y) or opaque(x, y - 1) or opaque(x, y + 1)
        if not touch and a.diagonals then
          touch = opaque(x - 1, y - 1) or opaque(x + 1, y - 1) or opaque(x - 1, y + 1) or opaque(x + 1, y + 1)
        end
        if touch then image:putPixel(x, y, color) end
      end
    end
  end
end)

-- ── Bayer 4x4 ordered dithering ──────────────────────────────────────

local BAYER = {
  { 0, 8, 2, 10 },
  { 12, 4, 14, 6 },
  { 3, 11, 1, 9 },
  { 15, 7, 13, 5 },
}

-- Fills the rectangle, choosing color_b where pick(x, y, threshold) is true.
local function dither(sprite, a, color_a, color_b, pick)
  local layer, frame = lib.layer(sprite, a.layer), lib.frame(sprite, a.frame)
  local cel = lib.paint_cel(sprite, layer, frame, a.create) or lib.cel(layer, frame)
  local put = lib.painter(sprite, cel)
  local ca, cb = lib.color(color_a), lib.color(color_b)
  for y = a.y, a.y + a.height - 1 do
    for x = a.x, a.x + a.width - 1 do
      local threshold = (BAYER[y % 4 + 1][x % 4 + 1] + 0.5) / 16
      put(x, y, pick(x, y, threshold) and cb or ca)
    end
  end
end

-- Runs color_start (top/left) to color_end (bottom/right).
lib.edit("fx.dither_gradient", function(sprite, a)
  local span = math.max(1, (a.horizontal and a.width or a.height) - 1)
  dither(sprite, a, a.color_start, a.color_end, function(x, y, threshold)
    local along = a.horizontal and x - a.x or y - a.y
    return along / span >= threshold
  end)
end)

lib.edit("fx.dither_pattern", function(sprite, a)
  dither(sprite, a, a.color_a, a.color_b, function(_, _, threshold) return a.density > threshold end)
end)
