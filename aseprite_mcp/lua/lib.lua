-- Shared helpers and the op registry. Loaded once by the worker before the op
-- files; every op file receives this `lib` table.
--
-- An op is registered as one of three kinds. The kind, not the op, owns opening,
-- saving and transactions:
--
--   lib.edit(name, fn(sprite, args))  file opened; fn runs in a transaction;
--                                     the sprite is saved only if fn succeeds
--   lib.read(name, fn(sprite, args))  file opened; never saved
--   lib.free(name, fn(args))          no file opened; fn manages its own files
--
-- fn returns a table (sent back as JSON) or nothing. Failures are raised with
-- lib.fail(code, message) and reach Python as AsepriteError.

local lib, OPS = ...

function lib.edit(name, fn) OPS[name] = { kind = "edit", fn = fn } end
function lib.read(name, fn) OPS[name] = { kind = "read", fn = fn } end
function lib.free(name, fn) OPS[name] = { kind = "free", fn = fn } end

function lib.fail(code, message)
  error({ code = code, message = message }, 0)
end

-- Resolve a layer by name, searching inside groups.
--
--   1. An exact full-name match (including any "/") is tried first, breadth-
--      first, so a shallower layer wins over a deeper namesake and a layer or
--      group whose own name contains "/" is reachable directly.
--   2. Otherwise the name is read as a "group/child" path. Aseprite allows "/"
--      inside names, so segments are matched longest-prefix-first with
--      backtracking: "abc/x/y" resolves a group named "abc/x" then child "y",
--      yet a genuine "abc" -> "x" -> "y" hierarchy still resolves because a
--      dead-end longer prefix falls back to the shorter one.
function lib.find_layer(sprite, name)
  local queue = {}
  for _, layer in ipairs(sprite.layers) do queue[#queue + 1] = layer end
  local head = 1
  while head <= #queue do
    local layer = queue[head]
    head = head + 1
    if layer.name == name then return layer end
    if layer.isGroup then
      for _, child in ipairs(layer.layers) do queue[#queue + 1] = child end
    end
  end
  if not string.find(name, "/", 1, true) then return nil end
  local segs = {}
  for segment in string.gmatch(name, "[^/]+") do segs[#segs + 1] = segment end
  local function resolve(layers, i)
    for j = #segs, i, -1 do
      local candidate = table.concat(segs, "/", i, j)
      for _, layer in ipairs(layers) do
        if layer.name == candidate then
          if j == #segs then return layer end
          if layer.isGroup then
            local found = resolve(layer.layers, j + 1)
            if found then return found end
          end
        end
      end
    end
    return nil
  end
  return resolve(sprite.layers, 1)
end

function lib.layer(sprite, name, message)
  return lib.find_layer(sprite, name) or lib.fail("LayerNotFound", message or "Layer not found")
end

function lib.group(sprite, name, not_found_message)
  local group = lib.find_layer(sprite, name)
  if not group then lib.fail("GroupNotFound", not_found_message or "Group not found") end
  if not group.isGroup then lib.fail("NotAGroup", "Target is not a group") end
  return group
end

function lib.frame(sprite, index, message)
  return sprite.frames[index] or lib.fail("FrameOutOfRange", message or "Frame index out of range")
end

-- The existing cel on layer/frame.
function lib.cel(layer, frame)
  return layer:cel(frame) or lib.fail("NoCel", "No cel at that layer/frame")
end

-- The cel on layer/frame. When there is none and `create` is set, make one:
-- a copy of the cel on `source_index` if that frame has one, else an empty
-- canvas-sized cel. Returns nil when there is none and `create` is not set.
function lib.ensure_cel(sprite, layer, frame, create, source_index)
  local cel = layer:cel(frame)
  if cel or not create then return cel end
  local source = layer:cel(lib.frame(sprite, source_index, "Source frame out of range"))
  if source then
    return sprite:newCel(layer, frame, source.image:clone(), source.position)
  end
  return sprite:newCel(layer, frame, Image(sprite.width, sprite.height, sprite.colorMode), Point(0, 0))
end

-- Validates an inclusive 1-based range and returns its bounds.
function lib.frame_range(sprite, first, last)
  if first < 1 or last > #sprite.frames or first > last then
    lib.fail("FrameRangeOutOfBounds", "Frame range out of bounds")
  end
  return first, last
end

function lib.find_tag(sprite, name)
  for _, tag in ipairs(sprite.tags) do
    if tag.name == name then return tag end
  end
  return nil
end

-- Every layer that can hold cels, including those inside groups, bottom to top.
function lib.image_layers(sprite)
  local found = {}
  local function walk(layers)
    for _, layer in ipairs(layers) do
      if layer.isGroup then walk(layer.layers) else found[#found + 1] = layer end
    end
  end
  walk(sprite.layers)
  return found
end

-- A Color from the [r, g, b, a] list that tools send.
function lib.color(c)
  return Color { r = c[1], g = c[2], b = c[3], a = c[4] }
end

-- The cel on layer/frame, ready for drawing in sprite coordinates.
--
-- The cel image is grown so it covers the whole canvas. Content that already
-- hangs off the canvas is kept (the image grows to the union of both), so
-- nothing is cropped. Creates an empty canvas-sized cel when there is none
-- and `create` is set; returns nil when there is none and it is not.
function lib.paint_cel(sprite, layer, frame, create)
  local cel = layer:cel(frame)
  if not cel then
    if not create then return nil end
    return sprite:newCel(layer, frame, Image(sprite.width, sprite.height, sprite.colorMode), Point(0, 0))
  end
  local x, y = cel.position.x, cel.position.y
  local left, top = math.min(0, x), math.min(0, y)
  local right = math.max(sprite.width, x + cel.image.width)
  local bottom = math.max(sprite.height, y + cel.image.height)
  if left ~= x or top ~= y or right - left ~= cel.image.width or bottom - top ~= cel.image.height then
    local image = Image(right - left, bottom - top, sprite.colorMode)
    image:drawImage(cel.image, Point(x - left, y - top), 255, BlendMode.SRC)
    cel.image = image
    cel.position = Point(left, top)
  end
  return cel
end

-- put(x, y, color) for sprite coordinates on a cel from paint_cel. Pixels
-- outside the canvas are skipped.
function lib.painter(sprite, cel)
  local image, ox, oy = cel.image, cel.position.x, cel.position.y
  local width, height = sprite.width, sprite.height
  return function(x, y, color)
    if x >= 0 and y >= 0 and x < width and y < height then image:putPixel(x - ox, y - oy, color) end
  end
end

-- get(x, y) for sprite coordinates on `cel`: the pixel value there, or 0
-- (transparent) outside the canvas or outside the cel's image.
function lib.reader(sprite, cel)
  local image, ox, oy = cel.image, cel.position.x, cel.position.y
  local width, height = sprite.width, sprite.height
  return function(x, y)
    if x < 0 or y < 0 or x >= width or y >= height then return 0 end
    local ix, iy = x - ox, y - oy
    if ix < 0 or iy < 0 or ix >= image.width or iy >= image.height then return 0 end
    return image:getPixel(ix, iy)
  end
end

-- Calls fn(r, g, b, a) for every opaque pixel of `cel`; when fn returns a
-- pixel value the pixel is set to it. Returns how many pixels were set.
function lib.map_opaque(cel, fn)
  local pc = app.pixelColor
  local count = 0
  for it in cel.image:pixels() do
    local v = it()
    local alpha = pc.rgbaA(v)
    if alpha > 0 then
      local new = fn(pc.rgbaR(v), pc.rgbaG(v), pc.rgbaB(v), alpha)
      if new then
        it(new)
        count = count + 1
      end
    end
  end
  return count
end

-- True when (r, g, b) is within `tolerance` of `target` on every channel.
function lib.near(r, g, b, target, tolerance)
  return math.abs(r - target[1]) <= tolerance and math.abs(g - target[2]) <= tolerance
    and math.abs(b - target[3]) <= tolerance
end

-- The layer for tools called without one: the sprite's only image layer
-- (groups don't count), and frame 1. With several image layers there is no
-- right answer, so the caller has to name one.
function lib.default_target(sprite)
  local layers = lib.image_layers(sprite)
  if #layers ~= 1 then
    local names = {}
    for i, layer in ipairs(layers) do names[i] = layer.name end
    lib.fail("LayerRequired", string.format(
      "Sprite has %d layers (%s); name the layer to use. Tools without a layer argument only work on single-layer sprites",
      #layers, table.concat(names, ", ")))
  end
  return layers[1], sprite.frames[1]
end

-- What frame `index` looks like: every visible layer composited into a new
-- canvas-sized RGB image (hidden layers, opacity and blend modes respected).
function lib.composite(sprite, index)
  local image = Image(sprite.width, sprite.height, ColorMode.RGB)
  image:drawSprite(sprite, index)
  return image
end

-- `image` scaled up by a whole number, nearest neighbour.
function lib.scale_image(image, k)
  if k == 1 then return image end
  local out = Image(image.width * k, image.height * k, image.colorMode)
  for y = 0, image.height - 1 do
    for x = 0, image.width - 1 do
      local v = image:getPixel(x, y)
      for oy = 0, k - 1 do
        for ox = 0, k - 1 do out:putPixel(x * k + ox, y * k + oy, v) end
      end
    end
  end
  return out
end

-- A pixel value as {r, g, b, a}.
function lib.rgba(v)
  local pc = app.pixelColor
  return { pc.rgbaR(v), pc.rgbaG(v), pc.rgbaB(v), pc.rgbaA(v) }
end
