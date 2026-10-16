-- Tilemap ops (tools/tilemap.py).
--
-- A tileset holds #tileset entries; index 0 is the reserved empty tile, so
-- real tiles are 1 .. #tileset - 1. A tilemap cel's image has one pixel per
-- grid cell holding a tile index.
local lib = ...

local function tilemap_layer(sprite, name)
  local layer = lib.layer(sprite, name)
  if not layer.isTilemap then lib.fail("NotATilemap", "Layer is not a tilemap layer") end
  return layer
end

-- Grid cell size and map size in cells.
local function grid(sprite)
  local g = sprite.gridBounds
  return g.width, g.height, math.ceil(sprite.width / g.width), math.ceil(sprite.height / g.height)
end

-- Duplicate-name guard is top-level only: the new layer is created at the
-- root, and Aseprite permits the same name inside a different group.
lib.edit("tilemap.create_layer", function(sprite, a)
  for _, layer in ipairs(sprite.layers) do
    if layer.name == a.name then lib.fail("LayerExists", "Layer with that name already exists") end
  end
  sprite.gridBounds = Rectangle(0, 0, a.tile_width, a.tile_height)
  app.command.NewLayer { tilemap = true }
  app.activeLayer.name = a.name
end)

-- Pixels are tile-local; drawing on index #tileset appends a new tile.
lib.edit("tilemap.draw_on_tile", function(sprite, a)
  local tileset = tilemap_layer(sprite, a.layer).tileset or lib.fail("NoTileset", "Layer has no tileset")
  if a.index > #tileset then
    lib.fail("TileOutOfRange", string.format("tile_index out of range (tileset has %d real tiles; pass %d to append)",
                                             #tileset - 1, #tileset))
  end
  if a.index == #tileset then sprite:newTile(tileset) end
  local tile = tileset:tile(a.index)
  local image = tile.image:clone()
  for _, p in ipairs(a.pixels) do
    local x, y = p[1], p[2]
    if x >= 0 and y >= 0 and x < image.width and y < image.height then
      image:putPixel(x, y, lib.color(p[3]))
    end
  end
  tile.image = image
end)

-- Every entry is checked before any is written. The cel image is rebuilt to
-- cover the whole map at (0, 0) when it doesn't already.
lib.edit("tilemap.set_tiles", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  local layer = tilemap_layer(sprite, a.layer)
  local tileset = layer.tileset
  local tw, th, cols, rows = grid(sprite)
  for _, t in ipairs(a.tiles) do
    local col, row, index = t[1], t[2], t[3]
    if col < 0 or col >= cols or row < 0 or row >= rows then
      lib.fail("OutsideMap", string.format("Tile position (%d,%d) outside the %dx%d map", col, row, cols, rows))
    end
    if index < 0 or index >= #tileset then
      lib.fail("TileOutOfRange", string.format("tile_index %d out of range (tileset has %d real tiles)",
                                               index, #tileset - 1))
    end
  end

  local cel = layer:cel(frame)
  local image
  if cel and cel.image.width == cols and cel.image.height == rows
     and cel.position.x == 0 and cel.position.y == 0 then
    image = cel.image
  else
    image = Image(cols, rows, ColorMode.TILEMAP)
    if cel then
      local old, ox, oy = cel.image, cel.position.x // tw, cel.position.y // th
      for y = 0, old.height - 1 do
        for x = 0, old.width - 1 do
          local nx, ny = x + ox, y + oy
          if nx >= 0 and ny >= 0 and nx < cols and ny < rows then image:putPixel(nx, ny, old:getPixel(x, y)) end
        end
      end
    end
    cel = sprite:newCel(layer, frame, image, Point(0, 0))
  end
  for _, t in ipairs(a.tiles) do image:putPixel(t[1], t[2], t[3]) end
  cel.image = image
end)

lib.read("tilemap.tile_at", function(sprite, a)
  local frame = lib.frame(sprite, a.frame)
  local cel = tilemap_layer(sprite, a.layer):cel(frame)
  local index = 0
  if cel then
    local tw, th = grid(sprite)
    local cx, cy = a.col - cel.position.x // tw, a.row - cel.position.y // th
    if cx >= 0 and cy >= 0 and cx < cel.image.width and cy < cel.image.height then
      index = app.pixelColor.tileI(cel.image:getPixel(cx, cy))
    end
  end
  return { tile_index = index }
end)

lib.read("tilemap.info", function(sprite, a)
  local tileset = tilemap_layer(sprite, a.layer).tileset
  local tw, th, cols, rows = grid(sprite)
  return { tile_width = tw, tile_height = th, tile_count = #tileset - 1, map_cols = cols, map_rows = rows }
end)
